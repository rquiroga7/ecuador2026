# -*- coding: utf-8 -*-
"""
vivo/azure.py — Espejo incremental, rápido y robusto de la share de **Azure Files** del CNE.

Objetivo: seguir el escrutinio en **tiempo real**. Diseño:
  * REST directo con **SAS** (sin depender del SDK) → menos capas, más control.
  * `requests.Session` con **pool de conexiones** y **descargas en paralelo** (hilos).
  * **Incremental**: sólo baja ficheros nuevos/cambiados (por ETag/tamaño; si no, MD5).
    Manda `If-None-Match` para que el servidor responda 304 y no re-enviar.
  * **Robusto**: reintentos con **backoff exponencial + jitter** en 408/429/5xx y errores
    de red, respeta `Retry-After`, timeouts de (conexión, lectura), y reintenta el
    fichero completo si un trozo falla.
  * **Resumable**: escribe a `.part` y reanuda con `Range` si el servidor lo acepta;
    al terminar, `os.replace` (escritura atómica).
  * **Reanudable/repetible** entre corridas: registro `(ruta, capturado_en, etag, bytes,
    md5, ms)` en `vivo/azure_registro.csv`.
  * Devuelve la lista de ficheros **nuevos/cambiados** para que el ciclo los normalice.

SAS: `AZURE_SAS=https://<cuenta>.file.core.windows.net/<share>?<sas>` (o `--sas`).
Se puede acotar con `--ruta subcarpeta`, `--patron regex`, `--profundidad`.

Uso:
    python -m vivo.azure --listar --ruta resultados
    python -m vivo.azure --sincronizar --destino azure --workers 12
"""

import os
import re
import csv
import sys
import time
import random
import hashlib
import argparse
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter

import rutas_datos as rd

API_VERSION = "2024-11-04"
REINTENTABLES = {408, 425, 429, 500, 502, 503, 504}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
def _partes(sas_url):
    sas_url = sas_url.strip()
    if "?" not in sas_url:
        raise ValueError("La SAS debe incluir '?...'")
    base, query = sas_url.split("?", 1)
    base = base.rstrip("/")
    m = re.match(r"(https?://[^/]+)/(.+)", base)
    if not m:
        raise ValueError("URL de Azure inválida")
    cuenta, share = m.group(1), m.group(2).strip("/")
    return cuenta, share, query


def _session(workers):
    s = requests.Session()
    ad = HTTPAdapter(pool_connections=workers, pool_maxsize=workers,
                     max_retries=0)
    s.mount("https://", ad)
    s.headers.update({"User-Agent": "ecuador2026/1.0", "x-ms-version": API_VERSION})
    return s


def _backoff(intento, retry_after=None):
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(20.0, (0.5 * (2 ** intento)) + random.uniform(0, 0.5))


def _get(session, url, intentos=5, **kw):
    """GET con reintentos/backoff. Devuelve Response (o lanza)."""
    for i in range(intentos):
        try:
            r = session.get(url, **kw)
            if r.status_code in REINTENTABLES:
                ra = r.headers.get("Retry-After")
                time.sleep(_backoff(i, ra))
                continue
            return r
        except requests.RequestException:
            if i == intentos - 1:
                raise
            time.sleep(_backoff(i))
    return r


# ---------------------------------------------------------------------------
def listar_remoto(session, cuenta, share, sas, ruta="", profundidad=6,
                  patron=None):
    """Lista recursiva (Azure Files lista por directorio). Devuelve ficheros."""
    rx = re.compile(patron) if patron else None
    out = []
    cola = [(ruta.strip("/"), 0)]
    while cola:
        dir_actual, niv = cola.pop(0)
        marcador = ""
        while True:
            url = f"{cuenta}/{share}/{dir_actual}".rstrip("/") + "?" + sas
            url += f"&restype=directory&comp=list&include=timestamps&{marcador}"
            r = _get(session, url, timeout=(10, 60))
            r.raise_for_status()
            raiz = ET.fromstring(r.content)
            pref = raiz.tag.split("}")[0].strip("{") + ":" if "}" in raiz.tag else ""
            ns = {"f": pref[:-1]} if pref else {}

            def _find(el, tag):
                return el.find(f"f:{tag}", ns) if pref else el.find(tag)

            def _findall(el, tag):
                return el.findall(f".//f:{tag}", ns) if pref else el.findall(f".//{tag}")

            for f in _findall(raiz, "File"):
                nom = _find(f, "Name").text
                props = _find(f, "Properties")

                def g(tag, _p=props):
                    e = _find(_p, tag) if _p is not None else None
                    return e.text if e is not None else None
                rel = f"{dir_actual}/{nom}".strip("/")
                if rx and not rx.search(rel):
                    continue
                out.append({"ruta": rel, "bytes": int(g("Content-Length") or 0),
                            "etag": (g("Etag") or "").strip('"'),
                            "modificado": g("Last-Modified")})
            for d in _findall(raiz, "Directory"):
                nom = _find(d, "Name").text
                if niv + 1 <= profundidad:
                    cola.append((f"{dir_actual}/{nom}".strip("/"), niv + 1))
            mark = _find(raiz, "NextMarker")
            if mark is not None and mark.text:
                from urllib.parse import urlencode
                marcador = urlencode({"marker": mark.text})
            else:
                break
    return out


# ---------------------------------------------------------------------------
def _registro_path():
    return rd.ruta("vivo/azure_registro.csv")


def _registro():
    p = _registro_path()
    if not os.path.exists(p):
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["ruta"]: r for r in csv.DictReader(f)}


def _anotar(filas):
    if not filas:
        return
    p = _registro_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    nuevo = not os.path.exists(p)
    with _lock:
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(["ruta", "capturado_en", "etag", "bytes", "md5", "ms",
                            "archivo"])
            w.writerows(filas)


def _md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _descargar_uno(session, cuenta, share, sas, item, out_dir, etag_prev=None,
                   intentos=5):
    """Descarga un fichero con `.part` + `os.replace`. Devuelve fila de registro."""
    rel = item["ruta"]
    local = os.path.join(out_dir, rel.replace("/", "__"))
    tmp = local + ".part"
    url = f"{cuenta}/{share}/{rel}?" + sas
    t0 = time.time()
    for i in range(intentos):
        try:
            headers = {}
            if os.path.exists(tmp):
                headers["Range"] = f"bytes={os.path.getsize(tmp)}-"
            elif etag_prev:
                headers["If-None-Match"] = f'"{etag_prev}"'
            r = session.get(url, headers=headers, stream=True, timeout=(10, 120))
            if r.status_code == 304:
                return None
            if r.status_code in REINTENTABLES:
                time.sleep(_backoff(i, r.headers.get("Retry-After")))
                continue
            if r.status_code == 416 and os.path.exists(tmp):
                os.replace(tmp, local)      # ya estaba completo
                break
            r.raise_for_status()
            modo = "ab" if (headers.get("Range") and r.status_code == 206) else "wb"
            if modo == "wb" and os.path.exists(tmp):
                os.remove(tmp)
            with open(tmp, modo) as f:
                for chunk in r.iter_content(1 << 16):
                    if chunk:
                        f.write(chunk)
            os.replace(tmp, local)
            break
        except requests.RequestException:
            if i == intentos - 1:
                raise
            time.sleep(_backoff(i))
    ms = int((time.time() - t0) * 1000)
    return [rel, datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            item["etag"], item["bytes"], _md5(local), ms, local]


def sincronizar(sas_url, destino="azure", ruta="", workers=12, patron=None,
                profundidad=6, usar_md5=False):
    """Baja en paralelo todo lo nuevo/cambiado. Devuelve la lista de rutas bajadas."""
    cuenta, share, sas = _partes(sas_url)
    session = _session(workers)
    out_dir = rd.ruta_dir(destino)
    reg = _registro()

    t0 = time.time()
    remotos = listar_remoto(session, cuenta, share, sas, ruta, profundidad, patron)
    print(f"[i] listados {len(remotos)} ficheros remotos en {time.time()-t0:.1f}s")

    pendientes = []
    for it in remotos:
        prev = reg.get(it["ruta"])
        if prev and prev["etag"] == str(it["etag"]) and int(prev["bytes"]) == it["bytes"]:
            local = prev.get("archivo")
            if local and os.path.exists(local):
                continue
        pendientes.append(it)
    print(f"[i] {len(pendientes)} nuevos/cambiados de {len(remotos)}")

    t1 = time.time()
    filas, fallos = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_descargar_uno, session, cuenta, share, sas, it, out_dir,
                          (reg.get(it["ruta"], {}) or {}).get("etag")): it
                for it in pendientes}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                fila = fut.result()
                if fila:
                    filas.append(fila)
                    print(f"  [+] {it['ruta']} ({it['bytes']} B, {fila[5]} ms)")
            except Exception as e:
                fallos += 1
                print(f"  [!] {it['ruta']}: {e}")
    _anotar(filas)
    dt = time.time() - t1
    mb = sum(f[3] for f in filas) / 1e6
    tput = mb / dt if dt > 0 else 0
    print(f"[OK] {len(filas)} bajados ({mb:.2f} MB en {dt:.1f}s ≈ {tput:.1f} MB/s)"
          + (f" | {fallos} fallos" if fallos else ""))
    return [f[0] for f in filas]


def listar(sas_url, ruta="", patron=None):
    cuenta, share, sas = _partes(sas_url)
    s = _session(4)
    for it in listar_remoto(s, cuenta, share, sas, ruta, patron=patron):
        print(f"{'dir' if it['bytes'] < 0 else 'file':4} {it['bytes']:>12} {it['ruta']}")


def _creds():
    return os.environ.get("AZURE_SAS", "").strip() or None


def main():
    ap = argparse.ArgumentParser(description="Espejo rápido/robusto de Azure Files (CNE).")
    ap.add_argument("--sas", default=_creds(), help="SAS completa (o env AZURE_SAS).")
    ap.add_argument("--ruta", default="", help="subcarpeta dentro de la share")
    ap.add_argument("--destino", default="azure")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--profundidad", type=int, default=6)
    ap.add_argument("--patron", default=None, help="regex de nombre de fichero")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--sincronizar", action="store_true")
    args = ap.parse_args()
    if not args.sas:
        print("[-] Falta la SAS (--sas o AZURE_SAS). Consíguela vigente para 2026.")
        sys.exit(2)
    if args.listar:
        listar(args.sas, args.ruta, args.patron)
    if args.sincronizar:
        sincronizar(args.sas, args.destino, args.ruta, args.workers, args.patron,
                    args.profundidad)
    if not (args.listar or args.sincronizar):
        ap.print_help()


if __name__ == "__main__":
    main()

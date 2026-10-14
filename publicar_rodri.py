# -*- coding: utf-8 -*-
"""
publicar_rodri.py — Construye el paquete web y lo publica.

Lee los resultados del extrapolador/proyección y arma un JSON compacto con:
  * el último estado (escrutado, control, crudo, proyecciones, zonas)
  * la serie temporal completa (para dibujar la evolución en el navegador)

Siempre escribe 'datos_web.json' en local y luego lo publica por una de estas vías:

  A) Endpoint HTTP sin caché (opcional):
       PUBLISH_URL     p.ej. https://...workers.dev/datos
       PUBLISH_TOKEN   se envía como 'Authorization: Bearer ...'
       PUBLISH_METHOD  PUT (por defecto) o POST

  B) Git (GitHub-only, sin servicios externos):
       PUBLISH_MODE=git  (o PUBLISH_GIT=1)
       GIT_DATA_BRANCH   rama de datos (por defecto 'data')
       GIT_REMOTE        remoto (por defecto 'origin')
       GIT_FORCE         1 (por defecto) => commit huérfano único + force-push,
                         para que el historial NO crezca y no dispare builds de Pages.

El dashboard (GitHub Pages, estático) lee el JSON con cache-busting desde:
  https://raw.githubusercontent.com/<user>/<repo>/<rama>/datos_web.json
"""

import os
import csv
import json
import sys
import subprocess
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

import rutas_datos as rd

ARCHIVO_HISTORICO = rd.ruta("historico_proyecciones_2026.csv")
ARCHIVO_JSON = rd.ruta("datos_proyeccion_2026.json")
ARCHIVO_JSON_SWING = rd.ruta("datos_proyeccion_swing_2026.json")
ARCHIVO_JSON_SCHT = rd.ruta("datos_proyeccion_schteingart_2026.json")
ARCHIVO_JSON_V4 = rd.ruta("datos_proyeccion_v4_2026.json")
ARCHIVO_WEB = rd.ruta("datos_web.json")


def construir_serie():
    """Convierte el histórico CSV en una lista de puntos para Chart.js."""
    if not os.path.exists(ARCHIVO_HISTORICO):
        return []
    serie = {}
    with open(ARCHIVO_HISTORICO, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            t = fila["fecha_hora"]
            entrada = serie.setdefault(t, {
                "t": t,
                "escrutado": _num(fila.get("escrutado_pct")),
            })
            punto = {
                "lula": _num(fila.get("lula_pct")),
                "flavio": _num(fila.get("bolsonaro_pct")),
                "otros": _num(fila.get("otros_blancos_pct")),
                "lula_votos": int(_num(fila.get("lula_votos"))),
                "flavio_votos": int(_num(fila.get("bolsonaro_votos"))),
                "otros_votos": int(_num(fila.get("otros_blancos_votos"))),
            }
            if fila.get("tipo") == "crudo":
                entrada["crudo"] = punto
            elif fila.get("tipo") == "swing":
                entrada["swing"] = punto
            else:
                entrada["proyectado"] = punto
    return list(serie.values())


def _num(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _leer_json(archivo):
    if os.path.exists(archivo):
        try:
            with open(archivo, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def construir_payload():
    """Une la salida v1 (extrapolador), swing (v2) y v3 (zonas similares)."""
    v1 = _leer_json(ARCHIVO_JSON)
    swing = _leer_json(ARCHIVO_JSON_SWING)
    scht = _leer_json(ARCHIVO_JSON_SCHT)
    v4 = _leer_json(ARCHIVO_JSON_V4)

    nacional = swing.get("nacional")
    if not nacional:
        nacional = {"escrutado": v1.get("escrutado_pct"),
                    "v1": v1.get("proyectado"), "swing": v1.get("proyectado")}

    estados = swing.get("estados", [])
    # Añadir schteingart, schteingart sin gate y v4 al nacional y a cada estado.
    for metodo, data in (("schteingart", scht), ("v4", v4)):
        nat_m = (data.get("nacional") or {}).get(metodo)
        if nat_m:
            nacional[metodo] = nat_m
        por_uf = {e.get("uf"): e.get(metodo) for e in data.get("estados", [])}
        for e in estados:
            if por_uf.get(e.get("uf")):
                e[metodo] = por_uf[e["uf"]]
    nat_ng = (scht.get("nacional") or {}).get("schteingart_nogate")
    if nat_ng:
        nacional["scht_ng"] = nat_ng
    por_uf_ng = {e.get("uf"): e.get("schteingart_nogate") for e in scht.get("estados", [])}
    for e in estados:
        if por_uf_ng.get(e.get("uf")):
            e["scht_ng"] = por_uf_ng[e["uf"]]

    payload = {
        "actualizado": v1.get("actualizado") or swing.get("actualizado"),
        "escrutado_pct": v1.get("escrutado_pct", swing.get("escrutado_pct")),
        "estado_control": v1.get("estado_control", ""),
        "swing_disponible": swing.get("swing_disponible", False),
        "metodo_principal": swing.get("metodo_principal", "v1"),
        "crudo": v1.get("crudo"),
        "zonas": v1.get("zonas"),
        "nacional": nacional,
        "estados": estados,
        "serie": construir_serie(),
        "publicado": datetime.now().astimezone().isoformat(),
    }
    return payload


# --------------------------------------------------------------------------
# Publicación por HTTP (endpoint sin caché)
# --------------------------------------------------------------------------
def publicar_http(payload, url):
    headers = {"Content-Type": "application/json", "Cache-Control": "no-store"}
    token = os.environ.get("PUBLISH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    metodo = os.environ.get("PUBLISH_METHOD", "PUT").upper()
    try:
        r = requests.request(
            metodo, url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, timeout=20,
        )
        if r.status_code in (200, 201, 204):
            print(f"[✓] Publicado en {url} ({r.status_code})")
            return True
        print(f"[!] El endpoint respondió {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        print(f"[!] Error al publicar: {e}")
    return False


# --------------------------------------------------------------------------
# Publicación por Git (GitHub-only)
# --------------------------------------------------------------------------
def _git(*args, input=None):
    # Se pasan bytes (sin text=True) para que Windows NO traduzca '\n' a '\r\n':
    # eso corrompía el nombre del archivo en 'git mktree' (quedaba "datos_web.json\r").
    if isinstance(input, str):
        input = input.encode("utf-8")
    r = subprocess.run(["git", *args], input=input, capture_output=True)
    return subprocess.CompletedProcess(
        r.args, r.returncode,
        r.stdout.decode("utf-8", "replace"),
        r.stderr.decode("utf-8", "replace"),
    )


def publicar_git(archivo, branch="data", remote="origin", force=True):
    """Sube un único archivo a una rama, sin tocar el árbol de trabajo.

    Con force=True crea un commit huérfano (sin padre) y hace force-push: la rama
    queda con un solo commit, el historial no crece y no se disparan builds de
    GitHub Pages (esa rama no es la fuente del sitio)."""
    if not os.path.exists(".git"):
        print("[!] No hay repositorio git (.git). Ejecuta 'git init' primero.")
        return False

    r = _git("hash-object", "-w", archivo)
    if r.returncode != 0:
        print(f"[!] git hash-object falló: {r.stderr.strip()}")
        return False
    blob = r.stdout.strip()

    nombre = os.path.basename(archivo)
    r = _git("mktree", input=f"100644 blob {blob}\t{nombre}\n")
    if r.returncode != 0:
        print(f"[!] git mktree falló: {r.stderr.strip()}")
        return False
    tree = r.stdout.strip()

    args = ["commit-tree", tree]
    if not force:
        prev = _git("rev-parse", f"refs/heads/{branch}")
        if prev.returncode == 0 and prev.stdout.strip():
            args += ["-p", prev.stdout.strip()]
    args += ["-m", f"datos {datetime.now().astimezone().isoformat()}"]
    r = _git(*args)
    if r.returncode != 0:
        print(f"[!] git commit-tree falló: {r.stderr.strip()}")
        return False
    commit = r.stdout.strip()

    r = _git("update-ref", f"refs/heads/{branch}", commit)
    if r.returncode != 0:
        print(f"[!] git update-ref falló: {r.stderr.strip()}")
        return False

    push = ["push"]
    if force:
        push.append("--force")
    push += [remote, f"refs/heads/{branch}:refs/heads/{branch}"]
    r = _git(*push)
    if r.returncode == 0:
        print(f"[✓] {nombre} subido a {remote}/{branch}")
        return True
    print(f"[!] git push falló: {r.stderr.strip()[:300]}")
    return False


# --------------------------------------------------------------------------
def publicar(payload):
    with open(ARCHIVO_WEB, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[i] Paquete web local escrito: {ARCHIVO_WEB} "
          f"({len(payload.get('serie', []))} puntos de serie)")

    url = os.environ.get("PUBLISH_URL", "").strip()
    modo = os.environ.get("PUBLISH_MODE", "").strip().lower()
    hacer_git = modo == "git" or os.environ.get("PUBLISH_GIT", "") == "1"

    if not url and not hacer_git:
        print("[i] Sin PUBLISH_URL ni PUBLISH_MODE=git: solo se escribió en local.")
        return True

    ok = True
    if url:
        ok = publicar_http(payload, url) and ok
    if hacer_git:
        ok = publicar_git(
            ARCHIVO_WEB,
            branch=os.environ.get("GIT_DATA_BRANCH", "data"),
            remote=os.environ.get("GIT_REMOTE", "origin"),
            force=os.environ.get("GIT_FORCE", "1") == "1",
        ) and ok
    return ok


def main():
    payload = construir_payload()
    if not payload.get("actualizado"):
        print("[-] Todavía no hay datos de proyección (ejecuta antes el extrapolador).")
    ok = publicar(payload)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

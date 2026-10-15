# -*- coding: utf-8 -*-
"""
vivo/ciclo.py — Ciclo completo de operación (captura → instantánea → proyección →
publicación), modular para 2026 real o 2023 de prueba.

Fuentes (`--fuente`):
  * `replay` — simula el escrutinio de un año con órdenes de carga (probá el dashboard
               ya mismo, sin datos en vivo). Por defecto 2023 ← 2019.
  * `azure`  — espejo rápido/robusto de Azure Files (`vivo/azure.py`), normaliza los
               volcados y proyecta.
  * `portal` — captura del API del CNE (`vivo/scraper_cne.py`), normaliza y proyecta.

Publicación: escribe `web/datos_web.json`; si `--publicar` (o cfg.PUBLICAR / env
PUBLISH_*), lo sube a la rama de datos por HTTP o git (reusa `publicar_rodri`).

Uso:
    python -m vivo.ciclo --fuente replay --anio 2023 --referencia 2019 --fraccion 0.35
    python -m vivo.ciclo --fuente azure --ruta resultados --workers 16
    python -m vivo.ciclo --fuente replay --loop --intervalo 60
"""

import os
import sys
import json
import time
import argparse

import rutas_datos as rd
import config_eleccion as cfg


# ---------------------------------------------------------------------------
def snapshot_de(votos, totales):
    from vivo.instantaneas import COLS_VOTOS, COLS_TOTALES
    v = votos[[c for c in COLS_VOTOS if c in votos.columns]].copy()
    t = totales[[c for c in COLS_TOTALES if c in totales.columns]].copy()
    n = len(t)
    return {"votos": v, "totales": t, "n_juntas": n, "n_total": n,
            "pct_juntas": 100.0, "pct_votos": 100.0}


def snapshots_replay(anio, fraccion, orden, dignidades, seed=7):
    import numpy as np
    from vivo.instantaneas import cargar_base, instantanea, _orden
    rng = np.random.default_rng(seed)
    out = {}
    for dig in dignidades:
        base = cargar_base(dig, anio)
        o = _orden(base["mesas"], orden, rng)
        out[dig] = instantanea(base, o, 1.0 if fraccion >= 1 else fraccion)
    return out


def snapshots_azure(dignidades, ruta="", workers=12, patron=None):
    """Espeja Azure Files (rápido) y normaliza los volcados nuevos a instantáneas."""
    from vivo import azure
    sas = os.environ.get("AZURE_SAS", "").strip()
    if not sas:
        raise SystemExit("[-] Falta AZURE_SAS (SAS vigente 2026).")
    bajados = azure.sincronizar(sas, destino="azure", ruta=ruta, workers=workers,
                               patron=patron)
    return _normalizar_archivos(bajados, dignidades)


def snapshots_portal(dignidades, base, patron="post2021", token=None, provincias=None):
    from vivo import scraper_cne
    from vivo.instantaneas import desde_json
    host = base
    carpetas = scraper_cne.barrido(host, patron, dignidades, provincias or [-1],
                                   token=token, una_pasada=True)
    archivos = []
    for dirpath, _, files in os.walk(carpetas):
        archivos += [os.path.join(dirpath, f) for f in files if f.endswith(".json")]
    return _normalizar_archivos(archivos, dignidades)


def _normalizar_archivos(archivos, dignidades):
    """Best-effort: agrupa volcados por dignidad y arma una instantánea por dignidad."""
    from vivo.instantaneas import desde_cne_txt, desde_json
    if not archivos:
        return {}
    por_dig = {d: [] for d in dignidades}
    for p in archivos:
        base = os.path.basename(p).lower()
        for d in dignidades:
            if d in base or str(cfg.__dict__.get("COD_" + d.upper(), "")) in base:
                por_dig[d].append(p)
    out = {}
    for d, paths in por_dig.items():
        if not paths:
            continue
        votos, totales = [], []
        for p in paths:
            try:
                if p.lower().endswith(".json"):
                    v, t = desde_json(json.load(open(p, encoding="utf-8")))
                else:
                    v, t = desde_cne_txt(p, dignidad=d)
                votos.append(v); totales.append(t)
            except Exception as e:
                print(f"  [!] {os.path.basename(p)}: {e}")
        if votos:
            import pandas as pd
            out[d] = snapshot_de(pd.concat(votos, ignore_index=True),
                                 pd.concat(totales, ignore_index=True))
    return out


# ---------------------------------------------------------------------------
def correr(fuente=None, anio=None, referencia=None, fraccion=None, orden=None,
           metodo=None, salida=None, publicar=None, ruta_azure="", workers=12,
           forense=True):
    fuente = fuente or cfg.FUENTE
    anio = anio or cfg.ANIO_ELECCION
    referencia = referencia or cfg.ANIO_REFERENCIA
    fraccion = cfg.FRACCION_REPLAY if fraccion is None else fraccion
    orden = orden or cfg.ORDEN_REPLAY
    metodo = metodo or cfg.METODO
    dig = cfg.DIGNIDADES

    print(f"[ciclo] eleccion={cfg.ELECCION} fuente={fuente} anio={anio} "
          f"referencia={referencia} metodo={metodo}")
    if fuente == "replay":
        snaps = snapshots_replay(anio, fraccion, orden, dig)
    elif fuente == "azure":
        snaps = snapshots_azure(dig, ruta_azure, workers)
    elif fuente == "portal":
        snaps = snapshots_portal(dig, os.environ.get("CNE_BASE", ""))
    else:
        raise SystemExit(f"fuente desconocida: {fuente}")

    from modelo import proyectar
    refs = {d: proyectar.referencia_familias(d, referencia) for d in dig
            if d in snaps}
    destino = salida or os.path.join(rd.REPO, cfg.SALIDA_WEB)
    eleccion = cfg.ELECCION if anio == cfg.ANIO_ELECCION else \
        f"Seccionales Ecuador {anio} (prueba con referencia {referencia})"
    doc = proyectar.emitir(snaps, refs, metodo=metodo, eleccion=eleccion,
                           anio=anio, referencia=referencia, destino=destino,
                           simulado=(fuente == "replay"),
                           orden=(orden if fuente == "replay" else None))

    if forense:
        try:
            from forense import ranking as frac
            frac.exportar_web(digs=tuple(d for d in dig if d in snaps), anio=anio,
                              snaps=snaps)
        except Exception as e:
            print(f"[!] forense: {e}")
    return doc


def publicar_web(destino=None):
    destino = destino or os.path.join(rd.REPO, cfg.SALIDA_WEB)
    url = os.environ.get("PUBLISH_URL", "").strip()
    git = (os.environ.get("PUBLISH_MODE", "").lower() == "git"
           or os.environ.get("PUBLISH_GIT", "") == "1")
    if not url and not git:
        print("[i] Sin PUBLISH_URL/PUBLISH_GIT: sólo local.")
        return True
    import publicar_rodri
    ok = True
    if git:
        ok = publicar_rodri.publicar_git(
            destino, branch=os.environ.get("GIT_DATA_BRANCH", "data"),
            remote=os.environ.get("GIT_REMOTE", "origin"),
            force=os.environ.get("GIT_FORCE", "1") == "1") and ok
    if url:
        import requests
        try:
            with open(destino, "rb") as f:
                r = requests.put(url, data=f, headers={
                    "Content-Type": "application/json", "Cache-Control": "no-store"},
                    timeout=20)
            ok = r.status_code in (200, 201, 204) and ok
            print(f"[{'✓' if r.status_code in (200,201,204) else '!'}] PUT {url} ({r.status_code})")
        except Exception as e:
            print(f"[!] publicar: {e}"); ok = False
    return ok


def main():
    ap = argparse.ArgumentParser(description="Ciclo completo Ecuador 2026/2023.")
    ap.add_argument("--fuente", choices=["replay", "azure", "portal"], default=None)
    ap.add_argument("--anio", type=int, default=None)
    ap.add_argument("--referencia", type=int, default=None)
    ap.add_argument("--fraccion", type=float, default=None)
    ap.add_argument("--orden", default=None)
    ap.add_argument("--metodo", default=None)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--ruta-azure", default="")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--publicar", action="store_true")
    ap.add_argument("--sin-forense", action="store_true",
                    help="no recalcular el ranking forense de mesas")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=float, default=60.0)
    a = ap.parse_args()

    while True:
        correr(a.fuente, a.anio, a.referencia, a.fraccion, a.orden, a.metodo,
               a.salida, a.ruta_azure, a.workers, forense=not a.sin_forense)
        if a.publicar or cfg.PUBLICAR:
            publicar_web(a.salida)
        if not a.loop:
            break
        time.sleep(a.intervalo)


if __name__ == "__main__":
    main()

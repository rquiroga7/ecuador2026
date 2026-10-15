# -*- coding: utf-8 -*-
"""
vivo/instantaneas.py — Normaliza el escrutinio (histórico, crudo o replay) a
INSTANTÁNEAS por mesa con el **mismo esquema tidy** del histórico.

Idea (Frente B): el modelo debe consumir igual el histórico (2023) y lo vivo (2026).
Cada instante es un subconjunto de mesas ya escrutadas con sus votos por candidato y
los totales de la mesa. Con eso se construye la serie de progreso (`% actas`, votos por
bloque) y se alimenta la proyección (Frente C).

Fuentes de instantánea:
  * `cargar_base(dignidad, anio)` — base histórica tidy por mesa (2023).
  * `instantanea(base, orden, frac)` — replay: primeras `frac` mesas de un orden de carga.
  * `desde_cne_txt(ruta)` — volcado del CNE en formato pipe (mismo parser del histórico).
  * `desde_json(payload, mapa)` — respuesta cruda del API (mapeo de campos configurable).

Esquema tidy de votos:
    mesa_id · loc_id · cod_junta · cod_candidato · lista · familia · votos
Esquema tidy de totales (una fila por mesa):
    mesa_id · loc_id · cod_junta · votos_emitidos · votos_b · votos_n

CLI:
    python -m vivo.instantaneas --replay prefecto --orden aleatorio
    python -m vivo.instantaneas --snapshot D:\\...\\vivo\\crudo\\20261129-180000
"""

import os
import sys
import json
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import familia as _familia

COLS_VOTOS = ["mesa_id", "loc_id", "cod_junta", "cod_candidato", "lista", "familia",
              "votos"]
COLS_TOTALES = ["mesa_id", "loc_id", "cod_junta", "votos_emitidos", "votos_b",
                "votos_n"]
FRACCIONES = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.0]


# ---------------------------------------------------------------------------
# Base histórica tidy
# ---------------------------------------------------------------------------
def cargar_base(dignidad, anio=2023):
    """Devuelve {'votos', 'totales', 'mesas', 'dignidad', 'anio'} desde el histórico."""
    pv = rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz")
    pt = rd.ruta(f"mesas/mesas_{dignidad}_{anio}.csv.gz")
    if not (os.path.exists(pv) and os.path.exists(pt)):
        raise FileNotFoundError(f"falta la base {dignidad} {anio} ({pv} | {pt})")
    votos = pd.read_csv(pv, dtype=str)
    votos["votos"] = pd.to_numeric(votos["votos"], errors="coerce").fillna(0).astype(int)
    if "familia" not in votos.columns:
        votos["familia"] = votos["lista"].map(_familia)
    totales = pd.read_csv(pt, dtype=str)
    for c in ["votos_emitidos", "votos_b", "votos_n"]:
        if c in totales.columns:
            totales[c] = pd.to_numeric(totales[c], errors="coerce").fillna(0).astype(int)
    mesas = totales["mesa_id"].astype(str).tolist() if "mesa_id" in totales else []
    return {"votos": votos, "totales": totales, "mesas": mesas,
            "dignidad": dignidad, "anio": anio}


# ---------------------------------------------------------------------------
# Replay: órdenes de carga simulados
# ---------------------------------------------------------------------------
def _prioridad_2021(mesas):
    """Orden de carga real observado en la captura de Gaona (2021): por parroquia,
    minuto medio de publicación. Devuelve índices ordenados (o None si no hay archivo)."""
    p = rd.ruta("backtest/orden_parroquia_2021.csv")
    if not os.path.exists(p):
        return None
    o = pd.read_csv(p)
    d = dict(zip(o["loc_id"], o["min_medio"]))

    def loc3(m):
        q = str(m).split("-")
        return q[0] + "-" + q[1] + "-" + q[3] if len(q) >= 4 else str(m)

    pr = np.array([d.get(loc3(m), np.nan) for m in mesas], float)
    if np.isnan(pr).all():
        return None
    pr = np.where(np.isnan(pr), np.nanmedian(pr), pr)
    return list(np.argsort(pr, kind="stable"))


def _orden(mesas, modo, rng):
    U = len(mesas)
    if modo in ("prioridad2021", "prioridad_2021", "prioridad"):
        o = _prioridad_2021(mesas)
        if o is not None:
            return o
        print("[i] sin orden_parroquia_2021.csv: uso aleatorio")
    if modo == "aleatorio":
        return list(rng.permutation(U))
    if modo == "directo":
        return list(range(U))
    if modo == "inverso":
        return list(range(U - 1, -1, -1))
    return list(rng.permutation(U))


def instantanea(base, orden, frac):
    """Subconjunto tidy de las primeras `frac` mesas según `orden` (índices)."""
    votos, totales = base["votos"], base["totales"]
    mesas = base["mesas"]
    U = len(mesas)
    n = max(1, int(round(frac * U))) if frac < 1 else U
    idx = orden[:n]
    sel = [mesas[i] for i in idx]
    v = votos[votos["mesa_id"].isin(sel)].copy()
    t = totales[totales["mesa_id"].isin(sel)].copy()
    tot_votos = int(t["votos_emitidos"].sum()) if len(t) else 0
    tot_final = int(totales["votos_emitidos"].sum()) if len(totales) else 0
    return {
        "votos": v[COLS_VOTOS].reset_index(drop=True),
        "totales": t[COLS_TOTALES].reset_index(drop=True),
        "pct_juntas": round(100.0 * n / U, 2),
        "pct_votos": round(100.0 * tot_votos / tot_final, 2) if tot_final else 0.0,
        "n_juntas": n, "n_total": U,
    }


def serie_replay(dignidad, anio=2023, orden="aleatorio", fracciones=None, seed=42):
    """Lista de instantáneas (replay) con su fracción de juntas escrutadas."""
    base = cargar_base(dignidad, anio)
    rng = np.random.default_rng(seed)
    o = _orden(base["mesas"], orden, rng)
    frs = fracciones or FRACCIONES
    out = []
    for fr in frs:
        s = instantanea(base, o, fr)
        s["orden"] = orden
        out.append(s)
    return out


# ---------------------------------------------------------------------------
# Normalizadores de volcados reales (esquema vivo)
# ---------------------------------------------------------------------------
_MAPA_DEFECTO = {  # campo nuestro -> claves toleradas en el payload del CNE
    "mesa_id": ["mesa_id", "cod_junta", "codigo_junta", "id_junta", "junta"],
    "cod_candidato": ["cod_candidato", "codigo_candidato", "candidato_id"],
    "lista": ["lista", "cod_lista", "lis_partido", "num_partido"],
    "votos": ["votos", "voto", "votos_candidato", "total_votos"],
    "votos_emitidos": ["votos_emitidos", "sufragantes", "total_sufragantes", "votos"],
    "votos_b": ["votos_b", "blancos", "votos_blancos"],
    "votos_n": ["votos_n", "nulos", "votos_nulos"],
}


def _tomar(d, claves):
    for k in claves:
        if k in d and d[k] is not None:
            return d[k]
    return None


def desde_json(payload, mapa=None):
    """Normaliza una respuesta cruda del API a (votos, totales).

    Acepta payload = lista de registros o {clave: [registros]} (toma la primera
    lista). `mapa` permite adaptar los nombres de campo del CNE.
    """
    mapa = mapa or _MAPA_DEFECTO
    if isinstance(payload, dict):
        lista = next((v for v in payload.values() if isinstance(v, list)), None)
        if lista is None:
            lista = [payload]
    else:
        lista = payload
    filas = []
    for d in lista:
        if not isinstance(d, dict):
            continue
        filas.append({dest: _tomar(d, claves) for dest, claves in mapa.items()})
    df = pd.DataFrame(filas)
    if df.empty:
        return df, df
    if "mesa_id" not in df or df["mesa_id"].isna().all():
        raise ValueError("El payload no expone un identificador de mesa/junta.")
    cand = df[df["cod_candidato"].notna()].copy()
    for c in ["votos"]:
        cand[c] = pd.to_numeric(cand.get(c), errors="coerce").fillna(0).astype(int)
    cand["familia"] = cand.get("lista", pd.Series(index=cand.index)).map(_familia)
    cand = cand[[c for c in COLS_VOTOS if c in cand.columns]]
    tot = (df.groupby("mesa_id", as_index=False).agg(
        votos_emitidos=("votos_emitidos", "max"),
        votos_b=("votos_b", "max"), votos_n=("votos_n", "max")))
    tot = tot[[c for c in COLS_TOTALES if c in tot.columns]]
    return cand, tot


def desde_cne_txt(ruta, dignidad="prefecto", anio=2026):
    """Volcado del CNE en formato pipe (una sola mesa/dignidad) -> (votos, totales).

    Reutiliza el parser del histórico, aceptando un `.txt` suelto.
    """
    import zipfile
    import io
    from datos.parsear_resultados import COLUMNAS, _normalizar
    import datos.parsear_resultados as pr

    if ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as z:
            miembro = pr._miembro(z, pr.DIGNIDADES[dignidad])
            with z.open(miembro) as fh:
                df = pd.read_csv(fh, sep="|", header=None, names=COLUMNAS,
                                 dtype=str, encoding="latin-1",
                                 on_bad_lines="skip", na_filter=False)
    else:
        df = pd.read_csv(ruta, sep="|", header=None, names=COLUMNAS, dtype=str,
                         encoding="latin-1", on_bad_lines="skip", na_filter=False)
    for c in ["votos_emitidos", "votos_b", "votos_n", "votos_candidato"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    df = _normalizar(df)
    votos = df.groupby(["mesa_id", "cod_candidato"], sort=False).agg(
        votos=("votos_candidato", "sum"), lista=("lista", "first"),
        loc_id=("loc_id", "first"), cod_junta=("cod_junta", "first")).reset_index()
    votos["familia"] = votos["lista"].map(_familia)
    tot = df.groupby("mesa_id", sort=False).agg(
        loc_id=("loc_id", "first"), cod_junta=("cod_junta", "first"),
        votos_emitidos=("votos_emitidos", "max"), votos_b=("votos_b", "max"),
        votos_n=("votos_n", "max")).reset_index()
    return votos[COLS_VOTOS], tot[COLS_TOTALES]


# ---------------------------------------------------------------------------
# Persistencia y progreso
# ---------------------------------------------------------------------------
def guardar_snapshot(snap, etiqueta, dignidad, base_dir=None):
    d = base_dir or os.path.join(rd.ruta_dir("vivo"), "snapshots", dignidad)
    os.makedirs(d, exist_ok=True)
    pv = os.path.join(d, f"votos_{etiqueta}.csv.gz")
    pt = os.path.join(d, f"totales_{etiqueta}.csv.gz")
    snap["votos"].to_csv(pv, index=False, compression="gzip")
    snap["totales"].to_csv(pt, index=False, compression="gzip")
    return pv, pt


def progreso(snap):
    """Resumen de una instantánea: % juntas, % votos y votos por bloque."""
    v = snap["votos"]
    por_bloque = (v.groupby("lista")["votos"].sum().sort_values(ascending=False)
                  if len(v) else pd.Series(dtype=int))
    return {
        "capturado_en": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "n_juntas": snap["n_juntas"], "n_total": snap["n_total"],
        "pct_juntas": snap["pct_juntas"], "pct_votos": snap["pct_votos"],
        "votos_por_lista": {str(k): int(x) for k, x in por_bloque.head(30).items()},
    }


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Instantáneas por mesa (histórico/replay/vivo).")
    ap.add_argument("--dignidad", default="prefecto")
    ap.add_argument("--anio", type=int, default=2023)
    ap.add_argument("--replay", action="store_true", help="genera una serie de replay")
    ap.add_argument("--orden", default="aleatorio",
                    choices=["aleatorio", "directo", "inverso"])
    ap.add_argument("--snapshot", help="carpeta con volcados crudos a normalizar")
    args = ap.parse_args()

    if args.replay:
        snaps = serie_replay(args.dignidad, args.anio, args.orden)
        for s in snaps:
            etq = f"{args.orden}_{int(round(s['pct_juntas'])):03d}"
            guardar_snapshot(s, etq, args.dignidad)
            print(f"  {etq}: {s['pct_juntas']:5.1f}% juntas, "
                  f"{s['pct_votos']:5.1f}% votos, {s['n_juntas']} mesas")
        print("[OK] serie de replay guardada en vivo/snapshots/")
    elif args.snapshot:
        print(f"[i] normalizando volcados de {args.snapshot} (adaptador desde_json)")
        for f in sorted(os.listdir(args.snapshot)):
            if not f.endswith(".json"):
                continue
            payload = json.load(open(os.path.join(args.snapshot, f), encoding="utf-8"))
            try:
                votos, tot = desde_json(payload)
                print(f"  {f}: {len(votos)} filas candidato, {len(tot)} mesas")
            except Exception as e:
                print(f"  {f}: [!] {e}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
datos/candidatos.py — Registro de candidaturas (por año y dignidad) con su familia.

Objetivos:
  * **2023**: derivar el padrón de candidaturas (nombre, partido, lista, familia) de
    las bases tidy ya parseadas (`votos_<dignidad>_2023`). Sirve para el dashboard
    (mostrar nombres) y para el modelo.
  * **2026**: **instrumentar la carga** de la lista definitiva de candidaturas
    (se publica el 9-nov-2026). `cargar_2026()` normaliza un archivo del CNE
    (CSV/JSON; nombres de columna flexibles) a un esquema estable y agrega `familia`
    con `datos.familias`. Así, cuando salgan los candidatos, el pipeline ya los mapea.

Esquema canónico de salida (roster):
    cod_candidato · candidato · dignidad · cod_provincia · cod_canton ·
    partido · lista · familia

Uso:
    from datos import candidatos
    r23 = candidatos.roster(dig="prefecto", anio=2023)
    r26 = candidatos.cargar_2026(r"D:\\...\\candidatos_2026.csv")   # cuando exista

CLI:
    python -m datos.candidatos                       # roster 2023 (prefecto y alcalde)
    python -m datos.candidatos --2026 ruta.csv       # carga y normaliza la de 2026
"""

import os
import re
import sys
import json

import pandas as pd

import rutas_datos as rd
from datos.familias import familia as _familia, normalizar_lista

DIGNIDADES = {
    "11": "prefecto", "12": "concejal_rural", "13": "alcalde", "14": "concejal_urbano",
    "15": "vocal_junta", "16": "cpccs_mujeres", "17": "cpccs_hombres", "18": "cpccs",
}
DIGN_COD = {v: k for k, v in DIGNIDADES.items()}

# alias de columna tolerados al leer un archivo externo (p. ej. 2026)
ALIAS = {
    "cod_candidato": ["COD_CANDIDATO", "CANDIDATO_CODIGO", "codigo_candidato",
                      "id_candidato"],
    "candidato": ["NOM_CANDIDATO", "CANDIDATO_NOMBRE", "nombre", "nombres",
                  "CANDIDATO"],
    "cod_dignidad": ["COD_DIGNIDAD", "DIGNIDAD_CODIGO", "dignidad"],
    "dignidad": ["DIGNIDAD", "NOM_DIGNIDAD"],
    "cod_provincia": ["COD_PROVINCIA", "PROVINCIA_CODIGO", "provincia"],
    "cod_canton": ["COD_CANTON", "CANTON_CODIGO", "canton"],
    "partido": ["NOM_PARTIDO", "PARTIDO", "organizacion", "ORG_NOMBRE"],
    "lista": ["LIS_PARTIDO", "LISTA", "NUM_PARTIDO", "num_lista", "lista"],
}


def _buscar_col(df, claves):
    for c in claves:
        if c in df.columns:
            return c
    return None


def _normalizar_roster(df):
    """Renombra columnas a las canónicas y agrega `familia` (y `dignidad` si se puede)."""
    ren = {}
    for dest, claves in ALIAS.items():
        c = _buscar_col(df, claves)
        if c is not None and c != dest:
            ren[c] = dest
    df = df.rename(columns=ren)
    # dignidad legible
    if "dignidad" not in df.columns and "cod_dignidad" in df.columns:
        dd = pd.to_numeric(df["cod_dignidad"], errors="coerce").astype("Int64").astype(str)
        df["dignidad"] = dd.map(DIGNIDADES)
    # lista canónica + familia
    if "lista" in df.columns:
        df["lista_canonica"] = df["lista"].map(normalizar_lista)
        df["familia"] = df["lista"].map(_familia)
    else:
        df["familia"] = "LOCAL"
    return df


# ---------------------------------------------------------------------------
# 2023: roster derivado de las bases tidy
# ---------------------------------------------------------------------------
def roster(dig="prefecto", anio=2023):
    """Candidaturas únicas (con familia) a partir de las bases tidy del año."""
    p = rd.ruta(f"mesas/votos_{dig}_{anio}.csv.gz")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    v = pd.read_csv(p, dtype=str)
    cols = [c for c in ["cod_candidato", "candidato", "lista", "partido",
                        "loc_id"] if c in v.columns]
    r = v[cols].drop_duplicates("cod_candidato").reset_index(drop=True)
    r["dignidad"] = dig
    if "loc_id" in r.columns:
        r["cod_provincia"] = r["loc_id"].str.slice(0, 2)
        r["cod_canton"] = r["loc_id"].str.slice(3, 6)
    return _normalizar_roster(r)


# ---------------------------------------------------------------------------
# 2026: carga de la lista definitiva (cuando se publique)
# ---------------------------------------------------------------------------
def cargar_2026(ruta=None, guardar=True):
    """Normaliza la lista de candidaturas 2026 a un roster con familias.

    Acepta CSV, JSON o Excel. Si `ruta` es None, busca `raw/candidatos_2026.*`.
    Devuelve el DataFrame; si `guardar`, lo escribe en
    `catalogo/candidatos_2026.csv.gz`.
    """
    if ruta is None:
        raw = rd.ruta_dir("raw")
        cands = [f for f in os.listdir(raw)
                 if f.lower().startswith("candidatos_2026")
                 or f.lower().startswith("candidatos2026")]
        if not cands:
            raise FileNotFoundError(
                "No hay archivo de candidaturas 2026 en raw/. Pasá la ruta por "
                "parámetro cuando el CNE publique la lista (9-nov-2026).")
        ruta = os.path.join(raw, cands[0])

    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".json":
        df = pd.DataFrame(json.load(open(ruta, encoding="utf-8")))
    elif ext in (".xls", ".xlsx"):
        df = pd.read_excel(ruta, dtype=str)
    else:
        df = pd.read_csv(ruta, dtype=str, sep=None, engine="python")

    df = _normalizar_roster(df)
    if guardar:
        p = os.path.join(rd.ruta_dir("catalogo"), "candidatos_2026.csv.gz")
        df.to_csv(p, index=False, compression="gzip")
        print(f"[OK] roster 2026 -> {p} ({len(df)} filas, "
              f"{df['familia'].nunique()} familias)")
    return df


# ---------------------------------------------------------------------------
def _main():
    args = sys.argv[1:]
    if "--2026" in args:
        i = args.index("--2026")
        ruta = args[i + 1] if i + 1 < len(args) else None
        df = cargar_2026(ruta)
        print(df.head(20).to_string(index=False))
        return
    for dig in ["prefecto", "alcalde"]:
        try:
            r = roster(dig, 2023)
        except FileNotFoundError as e:
            print(f"[!] {dig}: {e}")
            continue
        print(f"\n=== {dig} 2023: {len(r)} candidaturas, "
              f"{r['familia'].nunique()} familias ===")
        print(r[["cod_candidato", "candidato", "partido", "lista", "familia"]]
              .head(15).to_string(index=False))


if __name__ == "__main__":
    _main()

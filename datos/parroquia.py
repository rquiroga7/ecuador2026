# -*- coding: utf-8 -*-
"""
datos/parroquia.py — Arma la base LOCAL a nivel parroquia × sexo para el backtest.

Une dos fuentes a la misma unidad (`loc_id` = provincia-cantón-parroquia, + sexo):
  * 2019 · `.sav` parroquial (dignidades: prefecto, alcalde, concejales, vocales)
  * 2023 · junta (nuestro `votos_<dignidad>_2023`) agregado a parroquia

La clave de partido es el **número de lista** (`partido`), que es comparable entre
elecciones (a diferencia del código interno del CNE).

Salidas (D:\\ecuador2026_data\\mesas\\):
    parr_partido_<dignidad>_<anio>.csv.gz   (loc_id, sexo, partido, votos)
    parr_totales_<dignidad>_<anio>.csv.gz   (loc_id, sexo, validos, sufragantes)

Uso:
    python -m datos.parroquia 2019
    python -m datos.parroquia 2023
"""

import os
import sys

import numpy as np
import pandas as pd

import rutas_datos as rd

RAW = rd.ruta_dir("raw")
DIGN_2019 = {"prefecto": 2, "alcalde": 4}


def _zfill_int(s, ancho):
    v = pd.to_numeric(s, errors="coerce").fillna(0).astype("int64").astype(str)
    return v.str.zfill(ancho)


# --------------------------------------------------------------------------
# 2019 (.sav parroquial)
# --------------------------------------------------------------------------
def _sav(nombre):
    cand = next((f for f in os.listdir(RAW) if f.lower().startswith(nombre.lower())), None)
    if cand is None:
        raise FileNotFoundError(f"no encuentro '{nombre}*' en {RAW}")
    return os.path.join(RAW, cand)


def _partido_2019():
    """op_codigo -> número de lista (ballot)."""
    op = pd.read_spss(_sav("organizaciones pol"))
    op = op.rename(columns={"OP_CODIGO": "op_codigo", "OP_LISTA": "partido",
                            "OP_SIGLAS": "siglas", "OP_NOMBRE": "op_nombre"})
    op["op_codigo"] = pd.to_numeric(op["op_codigo"], errors="coerce").astype("Int64")
    # la lista puede ser una alianza "21-100" -> cabeza = primer número
    op["partido"] = op["partido"].astype(str).str.split("-").str[0]
    op["partido"] = pd.to_numeric(op["partido"], errors="coerce").astype("Int64")
    return op[["op_codigo", "partido", "siglas", "op_nombre"]]


def _cand_2019():
    c = pd.read_spss(_sav("CANDIDATOS"))
    c = c.rename(columns={"CANDIDATO_CODIGO": "candidato_codigo",
                          "OP_CODIGO": "op_codigo",
                          "DIGNIDAD_CODIGO": "dignidad_codigo",
                          "CANDIDATO_NOMBRE": "candidato"})
    c["candidato_codigo"] = pd.to_numeric(c["candidato_codigo"], errors="coerce").astype("Int64")
    c["op_codigo"] = pd.to_numeric(c["op_codigo"], errors="coerce").astype("Int64")
    return c[["candidato_codigo", "op_codigo", "candidato"]]


def parroquia_2019(dignidad):
    v = pd.read_csv(rd.ruta(f"mesas/parr_votos_seccionales_2019.csv.gz"),
                    dtype=str)
    v = v[v["dignidad"] == dignidad].copy()
    v["votos"] = v["votos"].astype(int)
    v["candidato_codigo"] = pd.to_numeric(v["candidato_codigo"], errors="coerce").astype("Int64")
    v = v.drop(columns=[c for c in ["op_codigo"] if c in v.columns])
    v = v.merge(_cand_2019(), on="candidato_codigo", how="left")
    v = v.merge(_partido_2019(), on="op_codigo", how="left")
    v["loc_id"] = v["cod_provincia"].str.cat(
        [v["cod_canton"], v["cod_parroquia"]], sep="-")
    g = v.groupby(["loc_id", "sexo", "partido"], dropna=False, as_index=False)["votos"].sum()
    g = g[g["partido"].notna()]
    g["partido"] = g["partido"].astype(int)
    tot = v.groupby(["loc_id", "sexo"], as_index=False)["votos"].sum().rename(
        columns={"votos": "validos"})
    return g, tot


# --------------------------------------------------------------------------
# 2023 (junta -> parroquia)
# --------------------------------------------------------------------------
def parroquia_2023(dignidad):
    from modelo import bloques
    v = bloques.cargar_votos(dignidad, 2023)          # añade bloque (lista cabeza)
    # loc_id 2023 = prov-canton-circ-parroquia-zona-junta; la parroquia es la parte 3
    sp = v["loc_id"].str.split("-", expand=True)
    v["loc_id"] = sp[0].str.cat([sp[1], sp[3]], sep="-")
    v["sexo"] = v["mesa_id"].str.split("-").str[-1]
    v["partido"] = pd.to_numeric(v["bloque"], errors="coerce")
    g = v.dropna(subset=["partido"]).groupby(
        ["loc_id", "sexo", "partido"], as_index=False)["votos"].sum()
    g["partido"] = g["partido"].astype(int)
    tot = v.groupby(["loc_id", "sexo"], as_index=False)["votos"].sum().rename(
        columns={"votos": "validos"})
    return g, tot


def guardar(dignidad, anio, g, tot):
    d = rd.ruta_dir("mesas")
    pg = os.path.join(d, f"parr_partido_{dignidad}_{anio}.csv.gz")
    pt = os.path.join(d, f"parr_totales_{dignidad}_{anio}.csv.gz")
    g.to_csv(pg, index=False, compression="gzip")
    tot.to_csv(pt, index=False, compression="gzip")
    print(f"[OK] {dignidad} {anio}: filas={len(g)} parroquias={g['loc_id'].nunique()} "
          f"validos={int(tot['validos'].sum()):,} -> {pg}")
    return pg, pt


def main():
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
    for dignidad in ["prefecto", "alcalde"]:
        if anio == 2019:
            g, tot = parroquia_2019(dignidad)
        else:
            g, tot = parroquia_2023(dignidad)
        guardar(dignidad, anio, g, tot)


if __name__ == "__main__":
    main()

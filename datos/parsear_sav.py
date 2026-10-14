# -*- coding: utf-8 -*-
"""
datos/parsear_sav.py — Lee las bases .sav (SPSS) del CNE y las vuelve tidy.

Las bases .sav del CNE entregan resultados a nivel **parroquia × sexo** (la mesa
—junta— se agrega dentro de la parroquia; no hay número de junta). Unidad:
    unidad_id = provincia-cantón-circunscripción-parroquia-sexo

Dignidades 2019 (del catálogo `dignidades 2019.sav`):
    2 prefecto · 3 concejal rural · 4 alcalde · 5 concejal urbano · 6 vocales

Uso:
    python -m datos.parsear_sav "D:\\ecuador2026_data\\raw\\2019_...sav" --anio 2019 --nombre seccionales_2019
"""

import os
import sys

import pandas as pd

import rutas_datos as rd

ANCHOS = {"cod_provincia": 2, "cod_canton": 3, "cod_circunscripcion": 1,
          "cod_parroquia": 4}

DIGNIDAD_2019 = {2: "prefecto", 3: "concejal_rural", 4: "alcalde",
                 5: "concejal_urbano", 6: "vocales"}

SEXO = {"FEMENINO": "F", "MASCULINO": "M", "F": "F", "M": "M"}

# mapa flexible de nombres de columna del .sav -> canónica
RENOMBRE = {
    "PROVINCIA_CODIGO": "cod_provincia", "CANTON_CODIGO": "cod_canton",
    "CIRCUNSCRIPCION_CODIGO": "cod_circunscripcion",
    "PARROQUIA_CODIGO": "cod_parroquia", "JUNTA_SEXO": "sexo",
    "DIGNIDAD_CODIGO": "dignidad_codigo", "DIGNIDAD_NOMBRE": "dignidad_nombre",
    "OP_CODIGO": "op_codigo", "CANDIDATO_CODIGO": "candidato_codigo",
    "CANDIDATO_CODIGO_RESULTADOS": "candidato_codigo",
    "CANDIDATO_NOMBRE": "candidato", "SUFRAGANTES": "sufragantes",
    "BLANCOS": "blancos", "NULOS": "nulos", "VOTOS": "votos",
}


def _zfill_int(s, ancho):
    v = pd.to_numeric(s, errors="coerce").fillna(0).astype("int64").astype(str)
    return v.str.zfill(ancho)


def cargar(path, anio=None):
    """Lee un .sav y devuelve un DataFrame normalizado (parroquia × sexo)."""
    df = pd.read_spss(path)
    df = df.rename(columns=RENOMBRE)

    # dignidad: si sólo viene el nombre (2021) y es numérico, usarlo como código
    if "dignidad_codigo" not in df.columns:
        df["dignidad_codigo"] = df["dignidad_nombre"]
    df["dignidad_codigo"] = pd.to_numeric(df["dignidad_codigo"], errors="coerce").fillna(0)
    if anio == 2019:
        df["dignidad"] = df["dignidad_codigo"].map(DIGNIDAD_2019)
    else:
        df["dignidad"] = df.get("dignidad_nombre")

    for col, ancho in ANCHOS.items():
        df[col] = _zfill_int(df[col], ancho)
    df["sexo"] = df["sexo"].astype(str).str.strip().str.upper().map(SEXO).fillna(df["sexo"])
    if "op_codigo" in df.columns:
        df["op_codigo"] = pd.to_numeric(df["op_codigo"], errors="coerce")
    else:
        df["op_codigo"] = pd.NA
    if "candidato_codigo" not in df.columns:
        df["candidato_codigo"] = pd.NA
    if "candidato" not in df.columns:
        df["candidato"] = pd.NA

    df["loc_id"] = df["cod_provincia"].str.cat(
        [df["cod_canton"], df["cod_circunscripcion"], df["cod_parroquia"]], sep="-")
    df["unidad_id"] = df["loc_id"].str.cat(df["sexo"], sep="-")

    for c in ["sufragantes", "blancos", "nulos", "votos"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    return df


COLS = ["unidad_id", "loc_id", "cod_provincia", "cod_canton",
        "cod_circunscripcion", "cod_parroquia", "sexo", "dignidad",
        "dignidad_codigo", "op_codigo", "candidato_codigo", "candidato",
        "votos"]


def separar(df):
    """Devuelve (votos_largo, unidades). `votos` por (unidad, dignidad, candidato);
    `unidades` con sufragantes/blancos/nulos por (unidad, dignidad)."""
    clave = ["unidad_id", "loc_id", "cod_provincia", "cod_canton",
             "cod_circunscripcion", "cod_parroquia", "sexo", "dignidad",
             "dignidad_codigo"]
    votos = df[clave + ["op_codigo", "candidato_codigo", "candidato", "votos"]].copy()
    unid = df.groupby(clave, sort=False).agg(
        sufragantes=("sufragantes", "max"),
        blancos=("blancos", "max"),
        nulos=("nulos", "max"),
        n_candidatos=("votos", "size"),
    ).reset_index()
    return votos, unid


def guardar(votos, unidades, anio, nombre):
    d = rd.ruta_dir("mesas")
    pv = os.path.join(d, f"parr_votos_{nombre}_{anio}.csv.gz")
    pu = os.path.join(d, f"parr_unidades_{nombre}_{anio}.csv.gz")
    votos.to_csv(pv, index=False, compression="gzip")
    unidades.to_csv(pu, index=False, compression="gzip")
    print(f"[OK] {nombre} {anio}: votos={len(votos)} unidades={len(unidades)} -> {pv}")
    return pv, pu


def main():
    args = sys.argv[1:]
    path = next((a for a in args if a.lower().endswith(".sav")), None)
    if not path:
        print("uso: python -m datos.parsear_sav <archivo.sav> [--anio 2019] [--nombre X]")
        return
    anio = int(args[args.index("--anio") + 1]) if "--anio" in args else None
    nombre = args[args.index("--nombre") + 1] if "--nombre" in args else "sav"
    df = cargar(path, anio=anio)
    vo, un = separar(df)
    guardar(vo, un, anio or 0, nombre)
    print(vo.groupby("dignidad")["votos"].agg(["sum", "size"]).to_string())
    print("unidades:", len(un), "| suma sufragantes (todas las dignidades):",
          int(un["sufragantes"].sum()))


if __name__ == "__main__":
    main()

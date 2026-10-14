# -*- coding: utf-8 -*-
"""
datos/registro.py — Electores habilitados (N) por parroquia, por año.

Fuente: registros electorales del CNE (`.sav`, nivel parroquia × sexo × G_EDAD).
Se suman sexo y edad para obtener el padrón por parroquia (`loc_id` = prov-cantón-parroquia).

Años: 2019, 2021, 2023, 2025 (los que tenemos en `raw/`).

También expone sufragantes por parroquia (de los resultados presidenciales parseados,
`parr_unidades_nacional_<año>`), para calcular "No voto" = electores − sufragantes.
"""

import os
import pandas as pd

import rutas_datos as rd

ARCHIVOS = {
    2019: "registro electoral a nivel parroquial 2019.sav",
    2021: "registro_electoral_2021.sav",
    2023: "registro_electoral_parroquial_2023.sav",
    2025: "registro_electoral_parroquial_2025.sav",
}


def _zfill_int(s, ancho):
    v = pd.to_numeric(s, errors="coerce").fillna(0).astype("int64").astype(str)
    return v.str.zfill(ancho)


def electores_parroquia(anio):
    """Serie loc_id (prov-cantón-parroquia) -> electores habilitados."""
    ruta = rd.ruta(f"raw/{ARCHIVOS[anio]}")
    if not os.path.exists(ruta):
        # por si el archivo se guardó en otra carpeta
        ruta = os.path.join(rd.ruta_dir("raw"), os.path.basename(ARCHIVOS[anio]))
    df = pd.read_spss(ruta)
    df["loc_id"] = (_zfill_int(df["PROVINCIA_CODIGO"], 2) + "-"
                    + _zfill_int(df["CANTON_CODIGO"], 3) + "-"
                    + _zfill_int(df["PARROQUIA_CODIGO"], 4))
    df["ELECTORES"] = pd.to_numeric(df["ELECTORES"], errors="coerce").fillna(0)
    return df.groupby("loc_id")["ELECTORES"].sum()


def _loc3(loc4):
    p = loc4.astype(str).str.split("-")
    return p.str[0] + "-" + p.str[1] + "-" + p.str[3]


def sufragantes_parroquia(anio):
    """Serie loc_id -> sufragantes (presidencial) del año."""
    p = rd.ruta(f"mesas/parr_unidades_nacional_{anio}.csv.gz")
    if not os.path.exists(p):
        return pd.Series(dtype=float)
    u = pd.read_csv(p, dtype=str)
    u = u[u["dignidad"].str.contains("PRESID", case=False, na=False)].copy()
    u["sufragantes"] = pd.to_numeric(u["sufragantes"], errors="coerce").fillna(0)
    u["loc_id"] = _loc3(u["loc_id"])
    return u.groupby("loc_id")["sufragantes"].sum()


def no_voto(anio, electores=None, sufragantes=None):
    """Serie loc_id -> No voto = electores − sufragantes (≥0)."""
    E = electores if electores is not None else electores_parroquia(anio)
    S = sufragantes if sufragantes is not None else sufragantes_parroquia(anio)
    loc = E.index.intersection(S.index)
    return (E.reindex(loc) - S.reindex(loc)).clip(lower=0)


if __name__ == "__main__":
    for a in [2019, 2021, 2023, 2025]:
        try:
            E = electores_parroquia(a)
            print(f"{a}: parroquias={len(E)} electores={int(E.sum()):,}")
        except Exception as e:
            print(f"{a}: ERR {e}")
    for a in [2021, 2025]:
        E = electores_parroquia(a); S = sufragantes_parroquia(a)
        nv = no_voto(a, E, S)
        print(f"{a}: sufragantes={int(S.sum()):,} no_voto={int(nv.sum()):,} "
              f"participación={100*S.sum()/E.reindex(S.index).sum():.1f}%")

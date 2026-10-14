# -*- coding: utf-8 -*-
"""
datos/jerarquia.py — Jerarquía geográfica y nombres para las mesas.

Niveles (de la unidad más fina a la más gruesa):
    zona → parroquia → cantón → provincia → nacional

Los códigos ya vienen en las tablas de mesas (`datos/parsear_resultados.py`); aquí
se cargan los catálogos y se añaden los **nombres** para el análisis y las salidas.

Uso:
    from datos import jerarquia as j
    cats = j.cargar()
    mesas = j.etiquetar(mesas_df, cats)      # añade nombre_provincia, ...
"""

import os

import pandas as pd

import rutas_datos as rd


def cargar(destino=None):
    """Carga los catálogos guardados como CSV.gz ({nombre: DataFrame})."""
    destino = destino or rd.ruta_dir("catalogo")
    cats = {}
    for nombre in ["provincia", "canton", "parroquia", "zona", "junta",
                   "circunscripcion", "dignidad", "partido", "candidatos"]:
        p = os.path.join(destino, f"{nombre}.csv.gz")
        if os.path.exists(p):
            cats[nombre] = pd.read_csv(p, dtype=str)
    return cats


def _zfill(s, ancho):
    s = s.astype(str).str.strip().str.lstrip("0")
    return s.where(s != "", "0").str.zfill(ancho)


def etiquetar(df, cats):
    """Añade nombre_provincia, nombre_canton y nombre_parroquia a un DataFrame con
    las columnas cod_provincia / cod_canton / cod_parroquia."""
    out = df.copy()
    prov = cats.get("provincia")
    if prov is not None:
        prov = prov.rename(columns={"COD_PROVINCIA": "cod_provincia",
                                    "NOM_PROVINCIA": "nombre_provincia"})
        prov["cod_provincia"] = _zfill(prov["cod_provincia"], 2)
        out = out.merge(prov[["cod_provincia", "nombre_provincia"]],
                        on="cod_provincia", how="left")
    cant = cats.get("canton")
    if cant is not None:
        cant = cant.rename(columns={"COD_CANTON": "cod_canton",
                                    "NOM_CANTON": "nombre_canton"})
        cant["cod_canton"] = _zfill(cant["cod_canton"], 3)
        cant = cant.drop_duplicates("cod_canton")
        out = out.merge(cant[["cod_canton", "nombre_canton"]],
                        on="cod_canton", how="left")
    parr = cats.get("parroquia")
    if parr is not None:
        parr = parr.rename(columns={"COD_PARROQUIA": "cod_parroquia",
                                    "NOM_PARROQUIA": "nombre_parroquia"})
        parr["cod_parroquia"] = _zfill(parr["cod_parroquia"], 4)
        parr = parr.drop_duplicates("cod_parroquia")
        out = out.merge(parr[["cod_parroquia", "nombre_parroquia"]],
                        on="cod_parroquia", how="left")
    return out


def niveles():
    """Lista de columnas que definen cada nivel de la jerarquía (para shrinkage)."""
    return {
        "nacional": [],
        "provincia": ["cod_provincia"],
        "canton": ["cod_provincia", "cod_canton"],
        "parroquia": ["cod_provincia", "cod_canton", "cod_parroquia"],
        "zona": ["cod_provincia", "cod_canton", "cod_parroquia", "cod_zona"],
    }

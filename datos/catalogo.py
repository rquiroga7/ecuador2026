# -*- coding: utf-8 -*-
"""
datos/catalogo.py — Carga los catálogos (dimensiones) del CNE.

Las bases descargadas del CNE (p. ej. DATOS2023CNE.zip) traen un `CATALOGO.zip`
anidado con las tablas de dimensión:
  PROVINCIA, CANTON, PARROQUIA, ZONA, JUNTA, CIRCUNSCRIPCION, DIGNIDAD,
  PARTIDO, CANDIDATOS.

Uso:
    from datos import catalogo
    cats = catalogo.cargar(zip_path)
    cats["provincia"]           # DataFrame
    catalogo.guardar(cats)      # CSV.gz en D:\\ecuador2026_data\\catalogo\\
"""

import io
import os
import zipfile

import pandas as pd

import rutas_datos as rd

# nombre lógico -> nombre del miembro dentro de CATALOGO.zip
MIEMBROS = {
    "provincia": "PROVINCIA.xls",
    "canton": "CANTON.xls",
    "parroquia": "PARROQUIA.xls",
    "zona": "ZONA.xls",
    "junta": "JUNTA.xls",
    "circunscripcion": "CIRCUNSCRIPCION.xls",
    "dignidad": "DIGNIDAD.xls",
    "partido": "PARTIDO.xls",
    "candidatos": "CANDIDATOS.xls",
}


def _leer_xls(data):
    return pd.read_excel(io.BytesIO(data), dtype=str)


def cargar(zip_path):
    """Devuelve {nombre: DataFrame} leyendo el CATALOGO.zip anidado en `zip_path`."""
    with zipfile.ZipFile(zip_path) as z:
        cat_name = next(
            (n for n in z.namelist() if os.path.basename(n).upper() == "CATALOGO.ZIP"),
            None,
        )
        if cat_name is None:
            raise FileNotFoundError(f"No hay CATALOGO.zip dentro de {zip_path}")
        interior = io.BytesIO(z.read(cat_name))

    out = {}
    with zipfile.ZipFile(interior) as zc:
        for nombre, archivo in MIEMBROS.items():
            miembro = next(
                (n for n in zc.namelist()
                 if os.path.basename(n).upper() == archivo.upper()),
                None,
            )
            if miembro is None:
                print(f"[!] falta {archivo} en el catálogo")
                continue
            out[nombre] = _leer_xls(zc.read(miembro))
    return out


def guardar(cats, destino=None):
    """Guarda cada catálogo como CSV.gz en la carpeta de catálogos."""
    destino = destino or rd.ruta_dir("catalogo")
    rutas = {}
    for nombre, df in cats.items():
        p = os.path.join(destino, f"{nombre}.csv.gz")
        df.to_csv(p, index=False, compression="gzip")
        rutas[nombre] = p
        print(f"[OK] {nombre:<16} {df.shape[0]:>7} filas -> {p}")
    return rutas


def _main():
    import sys
    zip_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        rd.REPO, "DATOS2023CNE.zip")
    print(f"[*] Leyendo catálogos de {zip_path}")
    cats = cargar(zip_path)
    for nombre, df in cats.items():
        print(f"  {nombre:<16} {df.shape[0]:>7} filas  cols={list(df.columns)}")
    guardar(cats)


if __name__ == "__main__":
    _main()

# -*- coding: utf-8 -*-
"""
rutas_datos.py — Dónde viven los datos del proyecto Ecuador 2026.

Todos los datos crudos y derivados se guardan en D:\\ecuador2026_data porque el
disco C: está lleno. La raíz es configurable con la variable de entorno
ECUADOR2026_DATA.

Uso desde otro script:

    import rutas_datos as rd
    archivo = rd.ruta("vivo/escrutinio_2026.csv.gz")   # D:\\ecuador2026_data\\...
    carpeta = rd.ruta_dir("mesas")                     # crea y devuelve la carpeta

CLI:
    python rutas_datos.py          # muestra la raíz y qué subcarpetas existen
    python rutas_datos.py --crear  # crea la raíz y todas las subcarpetas
"""

import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.environ.get("ECUADOR2026_DATA", r"D:\ecuador2026_data")

# Carpeta de datos derivados por tema (se crean al usarlas).
SUBCARPETAS = {
    "raw": "descargas crudas del CNE (bases y dumps por mesa)",
    "catalogo": "catálogos: provincia, cantón, parroquia, zona, junta, partido, candidato",
    "mesas": "resultados tidy por mesa (por dignidad y año)",
    "padron": "electores habilitados por junta",
    "vivo": "escrutinio 2026 en vivo (snapshots por mesa)",
    "forense": "salidas forenses (scores, ranking, mapas)",
    "ei": "inferencia ecológica (matrices de migración de votos)",
    "backtest": "backtest y calibración de márgenes",
}


def asegurar_raiz():
    os.makedirs(DATA_ROOT, exist_ok=True)
    return DATA_ROOT


def ruta(nombre):
    """Ruta absoluta de un archivo de datos (no lo crea)."""
    if os.path.isabs(nombre):
        return nombre
    asegurar_raiz()
    return os.path.join(DATA_ROOT, nombre)


def ruta_dir(nombre):
    """Ruta de una subcarpeta de datos; la crea si no existe."""
    asegurar_raiz()
    p = os.path.join(DATA_ROOT, nombre)
    os.makedirs(p, exist_ok=True)
    return p


def crear_estructura():
    asegurar_raiz()
    for sub in SUBCARPETAS:
        ruta_dir(sub)
    print(f"[OK] Estructura creada en {DATA_ROOT}")


if __name__ == "__main__":
    if "--crear" in sys.argv:
        crear_estructura()
    else:
        print(f"DATA_ROOT = {DATA_ROOT}")
        print(f"REPO      = {REPO}")
        for sub, desc in SUBCARPETAS.items():
            p = os.path.join(DATA_ROOT, sub)
            print(f"  {'OK ' if os.path.isdir(p) else '   '} {sub:<12} {desc}")

# -*- coding: utf-8 -*-
"""
backtest/consolidar_2019.py — Fase 0 del plan (docs/backtest.md).

* Une y **deduplica** los CSV del crawl 2019 (d2 prefecto, d4 alcalde) que quedaron
  repartidos entre workers (`_w*`, `_r*`).
* Escribe un Gaona consolidado por dignidad en `gaona_format/`.
* Reporta cobertura (votos 2019 vs oficial) y juntas únicas.

Uso: python -m backtest.consolidar_2019
"""
import os
import sys
import glob
import json
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd

OUT = rd.ruta_dir("gaona_format")
DIG = {"2": "d11_prefecto", "4": "d13_alcalde"}
# votos válidos oficiales aprox. 2019 (FINDINGS): prefecto ~8.09M, alcalde ~9.01M
OFICIAL = {"2": 8_090_000, "4": 9_010_000}
COLS = ["updated", "cod_dignidad", "cod_prov", "cod_cant", "circunscripcion",
        "parroquia", "recinto", "junta", "junta_genero", "acta_numero",
        "cod_org_pol", "cod_candidato", "total_sufragantes", "nulos", "blancos",
        "votos", "voto_acumulado", "nulo_acumulado", "blanco_acumulado",
        "sufragantes_acumulado", "porcentaje_votos_validos"]
KEY = ["cod_prov", "cod_cant", "circunscripcion", "parroquia", "recinto", "junta",
       "junta_genero", "cod_org_pol", "cod_candidato"]


def consolidar(dig):
    fs = sorted(glob.glob(rd.ruta(f"vivo/gaona2019_junta_d{dig}*.csv")))
    if not fs:
        print(f"[!] sin CSV para d{dig}"); return None
    d = pd.concat([pd.read_csv(f, dtype=str) for f in fs], ignore_index=True)
    antes = len(d)
    d = d.drop_duplicates(subset=KEY, keep="first")
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    juntas = d[KEY[:7]].drop_duplicates()
    tot = int(d["votos"].sum())
    p = os.path.join(OUT, f"gaona_2019_seccional_{DIG[dig]}_junta.csv")
    d[COLS].to_csv(p, index=False)
    print(f"\n== d{dig} ({DIG[dig]}) ==")
    print(f"  filas: {antes} -> {len(d)} tras dedup")
    print(f"  juntas únicas: {len(juntas)}")
    print(f"  votos: {tot:,}  (oficial aprox {OFICIAL[dig]:,} -> cobertura {100*tot/OFICIAL[dig]:.1f}%)")
    print(f"  [OK] {p}")
    return p


def faltantes(dig):
    z = json.load(open(rd.ruta("vivo/zonas2019.json"), encoding="utf-8"))
    tot = {f'{x["prov"]}-{x["cant"]}-{x["parr"]}-{x["zona"]}-{v}' for x in z for v, _ in x["juntas"]}
    done = set()
    for f in glob.glob(rd.ruta(f"vivo/gaona2019_junta_d{dig}*.done")):
        done |= set(open(f).read().split())
    fal = sorted(tot - done)
    print(f"\n  d{dig}: juntas en catálogo={len(tot)} hechas={len(done & tot)} faltan={len(fal)}")
    for k in fal[:10]:
        print("    falta:", k)
    return fal


def main():
    for dig in ("2", "4"):
        consolidar(dig)
        faltantes(dig)


if __name__ == "__main__":
    main()

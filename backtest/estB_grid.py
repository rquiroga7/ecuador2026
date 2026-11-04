# -*- coding: utf-8 -*-
"""
backtest/estB_grid.py — Grilla de variaciones de est_B (4 bloques, prefecto+alcalde,
error promedio por provincia de correísmo+derecha, a 10/15/20%).

OFAT (una dimensión a la vez): clip, nat, robust, ks1/ks4, lam25/lam75/lamdata,
sim, sizew, logit, nocanton/noparro. Luego ~20 combinaciones de los ganadores.

Salida: D:\\ecuador2026_data\\backtest\\estB_grid.csv
Uso: python -m backtest.estB_grid
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from backtest.variantes_swing import unidades, orden_zonas
from backtest.mejoras_v1 import hibrido_var
from backtest.tabla_correismo import metricas

FRACS = [0.10, 0.15, 0.20]
BASE = dict(clip=False, shrink_nat=False, robust="mean", ks=(2, 4, 8, 16),
            lam=0.5, peer="soft", logit=False, niveles=("parr", "cant", "prov", "nac"))

OFAT = [
    ("clip", dict(clip=True)),
    ("nat", dict(clip=True, shrink_nat=True)),
    ("robust", dict(clip=True, robust="median")),
    ("ks1", dict(clip=True, ks=(1, 2, 4, 8))),
    ("ks4", dict(clip=True, ks=(4, 8, 16, 32))),
    ("lam25", dict(clip=True, lam=0.25)),
    ("lam75", dict(clip=True, lam=0.75)),
    ("lamdata", dict(clip=True, lam="data")),
    ("sim", dict(clip=True, peer="sim")),
    ("sizew", dict(clip=True, peer="sizew")),
    ("logit", dict(clip=True, logit=True)),
    ("nocanton", dict(clip=True, niveles=("parr", "prov", "nac"))),
    ("noparro", dict(clip=True, niveles=("cant", "prov", "nac"))),
]
PAIRS = [
    ("nat_lam25", dict(shrink_nat=True, lam=0.25)),
    ("nat_lam75", dict(shrink_nat=True, lam=0.75)),
    ("nat_lamdata", dict(shrink_nat=True, lam="data")),
    ("nat_ks1", dict(shrink_nat=True, ks=(1, 2, 4, 8))),
    ("nat_ks4", dict(shrink_nat=True, ks=(4, 8, 16, 32))),
    ("nat_sim", dict(shrink_nat=True, peer="sim")),
    ("nat_logit", dict(shrink_nat=True, logit=True)),
    ("nat_noparro", dict(shrink_nat=True, niveles=("cant", "prov", "nac"))),
    ("robust_lam25", dict(robust="median", lam=0.25)),
    ("robust_lam75", dict(robust="median", lam=0.75)),
    ("robust_sim", dict(robust="median", peer="sim")),
    ("sim_lam25", dict(peer="sim", lam=0.25)),
    ("sim_lam75", dict(peer="sim", lam=0.75)),
    ("sim_ks1", dict(peer="sim", ks=(1, 2, 4, 8))),
    ("sim_ks4", dict(peer="sim", ks=(4, 8, 16, 32))),
    ("lamdata_sim", dict(lam="data", peer="sim")),
    ("lamdata_ks1", dict(lam="data", ks=(1, 2, 4, 8))),
    ("logit_lam25", dict(logit=True, lam=0.25)),
    ("logit_lam75", dict(logit=True, lam=0.75)),
    ("logit_nat", dict(logit=True, shrink_nat=True)),
]

VAR = {"base": dict(BASE), "clip": {**BASE, "clip": True}}
for n, kw in OFAT:
    VAR[n] = {**BASE, "clip": True, **kw}
for n, kw in PAIRS:
    VAR[n] = {**BASE, "clip": True, **kw}


def corrida(dig):
    B = unidades(2019, dig, "zona", "4bloques")
    T = unidades(2023, dig, "zona", "4bloques")
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= 100) & (T.sum(1) >= 100)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    ci, oi = cols.index("correismo"), cols.index("derecha")
    basev, finv = B.values, T.values; base_val = basev.sum(1)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    filas = []
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys)))); cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        for nombre, kw in VAR.items():
            proj = hibrido_var(obs, basev, base_val, keys, **kw)
            e2, e2n, a2, eg = metricas(proj, finv, keys, dig, ci, oi)
            filas.append({"dignidad": dig, "variante": nombre, "frac": int(fr * 100),
                          "err2": round(e2, 2), "acc2": round(a2, 3)})
    return filas


def main():
    filas = []
    for dig in ("prefecto", "alcalde"):
        filas += corrida(dig)
    df = pd.DataFrame(filas)
    p = os.path.join(rd.ruta_dir("backtest"), "estB_grid.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas |", len(VAR), "variantes")
    for dig in ("prefecto", "alcalde"):
        s = df[df.dignidad == dig]
        e = s.pivot_table(index="variante", columns="frac", values="err2")
        a = s.pivot_table(index="variante", columns="frac", values="acc2")
        e.columns = [f"err@{c}%" for c in e.columns]; a.columns = [f"acc@{c}%" for c in a.columns]
        t = pd.concat([e, a], axis=1)
        # ordenar por err@15 y mostrar top
        t = t.sort_values("err@15%")
        print(f"\n== {dig} (top 20 por err@15%) ==")
        print(t.head(20).to_string())


if __name__ == "__main__":
    main()

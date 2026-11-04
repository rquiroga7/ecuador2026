# -*- coding: utf-8 -*-
"""
backtest/validar_presidencial.py — Validación fuera de muestra de robust_sim en
**presidencial mismo-arena** (2021 general → 2023 anticipada 1ª vuelta), a nivel zona.

2 bloques: correísmo vs resto. Error = |Δcuota correísta| promedio por provincia;
acc = acierto correísmo-vs-resto por provincia. 10/15/20%.

Métodos: v1, sim (λ=0.5), robust_sim (λ=0.5/0.65/0.75).
Uso: python -m backtest.validar_presidencial
"""
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backtest.presidencial import unidades_anio, orden_zonas
from modelo import v1_brasil
from backtest.mejoras_v1 import hibrido_var
from backtest.tabla_correismo import metricas

FRACS = [0.10, 0.15, 0.20]


def main():
    B = unidades_anio(2021, "zona"); T = unidades_anio(2023, "zona")
    cols = ["corre", "resto"]
    com = sorted(set(B.index) & set(T.index))
    B = B.loc[com]; T = T.loc[com]
    keep = (B[cols].sum(1) >= 100) & (T[cols].sum(1) >= 100)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    basev = B[cols].values.astype(float); finv = T[cols].values.astype(float)
    base_val = basev.sum(1)
    ci, oi = 0, 1
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    print(f"2021->2023 presidencial · zonas={len(keys)}")
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys)))); cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        met = {
            "v1": v1_brasil.proyectar(obs, base_val, [np.array([k[:11] for k in keys]),
                    np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
                    np.full(len(keys), "EC")]),
            "sim": hibrido_var(obs, basev, base_val, keys, clip=True, robust="mean", peer="sim", lam=0.5),
            "robust_sim50": hibrido_var(obs, basev, base_val, keys, clip=True, robust="median", peer="sim", lam=0.5),
            "robust_sim65": hibrido_var(obs, basev, base_val, keys, clip=True, robust="median", peer="sim", lam=0.65),
            "robust_sim75": hibrido_var(obs, basev, base_val, keys, clip=True, robust="median", peer="sim", lam=0.75),
        }
        print(f"  @{fr*100:>3.0f}%")
        for nm, proj in met.items():
            e2, e2n, a2, eg = metricas(proj, finv, keys, "prefecto", ci, oi)
            print(f"     {nm:14s} err_prov={e2:5.2f}  acc={a2:.3f}")


if __name__ == "__main__":
    main()

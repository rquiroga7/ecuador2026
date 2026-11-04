# -*- coding: utf-8 -*-
"""
backtest/robust_sim_tune.py — Calibra λ y ks de `robust_sim`
(robust="median", peer="sim", clip=True) sobre local 2019→2023, 4 bloques.

Métrica: error promedio provincial (correísmo+derecha) y acc2 por territorio, a 10/15/20%,
prefecto y alcalde. Ranking: mayor acc media (y menor err como desempate).

Uso: python -m backtest.robust_sim_tune
"""
import sys
import itertools
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backtest.variantes_swing import unidades, orden_zonas
from backtest.mejoras_v1 import hibrido_var
from backtest.tabla_correismo import metricas

FRACS = [0.10, 0.15, 0.20]
LAMS = [0.35, 0.5, 0.65, 0.75]
KSS = [(1, 2, 4, 8), (2, 4, 8, 16), (4, 8, 16, 32), (8, 16, 32, 64)]


def prep(dig):
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
    basev, finv = B.values, T.values
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    return basev, finv, basev.sum(1), keys, ci, oi, orden


def main():
    data = {dig: prep(dig) for dig in ("prefecto", "alcalde")}
    rows = []
    for lam, ks in itertools.product(LAMS, KSS):
        errs, accs = [], []
        for dig, (basev, finv, base_val, keys, ci, oi, orden) in data.items():
            for fr in FRACS:
                n = max(3, int(round(fr * len(keys)))); cnt = orden[:n]
                obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
                proj = hibrido_var(obs, basev, base_val, keys, clip=True,
                                   robust="median", peer="sim", lam=lam, ks=ks)
                e2, e2n, a2, eg = metricas(proj, finv, keys, dig, ci, oi)
                errs.append(e2); accs.append(a2)
        rows.append({"lam": lam, "ks": str(ks), "err_media": round(float(np.mean(errs)), 2),
                     "acc_media": round(float(np.mean(accs)), 3)})
    df = pd.DataFrame(rows).sort_values(["acc_media", "err_media"], ascending=[False, True])
    print(df.to_string(index=False))
    print("\n[mejor por acc_media]:")
    print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()

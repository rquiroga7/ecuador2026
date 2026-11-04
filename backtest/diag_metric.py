# -*- coding: utf-8 -*-
"""backtest/diag_metric.py — Efecto de la definición de error:
  * fijo: correísmo + derecha.
  * top2_nac: los 2 bloques más votados a nivel nacional (mismos para todas las provincias).
  * top2_prov: los 2 bloques más votados en cada provincia (el "contendiente" local).
"""
import numpy as np
import pandas as pd
from backtest.variantes_swing import unidades, orden_zonas
from backtest.mejoras_v1 import hibrido, similitud


def metrics(proj, fin, keys, pair_fn):
    cols = list(range(proj.shape[1]))
    prov = np.array([k[:2] for k in keys])
    P = pd.DataFrame(proj); P["p"] = prov; P = P.groupby("p")[cols].sum()
    F = pd.DataFrame(fin); F["p"] = prov; F = F.groupby("p")[cols].sum()
    idx = P.index.intersection(F.index); P = P.loc[idx]; F = F.loc[idx]
    errs, accs = [], []
    for p in idx:
        sp, sf = P.loc[p].values, F.loc[p].values
        if sf.sum() <= 0:
            continue
        i, j = pair_fn(sf)
        scp = 100 * sp / sp.sum(); scf = 100 * sf / sf.sum()
        errs.append(0.5 * (abs(scp[i] - scf[i]) + abs(scp[j] - scf[j])))
        accs.append((sp[i] > sp[j]) == (sf[i] > sf[j]))
    return float(np.mean(errs)), float(np.mean(accs))


def main():
    for dig in ("prefecto", "alcalde"):
        B = unidades(2019, dig, "zona", "4bloques")
        T = unidades(2023, dig, "zona", "4bloques")
        cols = sorted(set(B.columns) | set(T.columns))
        com = sorted(set(B.index) & set(T.index))
        B = B.reindex(index=com, columns=cols, fill_value=0)
        T = T.reindex(index=com, columns=cols, fill_value=0)
        keep = (B.sum(1) >= 100) & (T.sum(1) >= 100)
        B, T = B[keep], T[keep]
        keys = list(B.index); basev, finv = B.values, T.values; base_val = basev.sum(1)
        ci, oi = cols.index("correismo"), cols.index("derecha")
        nat = finv.sum(0)
        top2 = list(np.argsort(nat)[::-1][:2])
        print(f"\n===== {dig} ===== | bloques {cols}")
        print(f"  top2 nacional (final): {[cols[i] for i in top2]}")
        g, prov = orden_zonas()
        tz = np.array([g.get(k, np.nan) for k in keys]); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
        orden = np.argsort(tz, kind="stable")
        fixed = lambda sf: (ci, oi)
        top2n = lambda sf: tuple(top2)
        top2p = lambda sf: tuple(np.argsort(sf)[::-1][:2])
        for fr in (0.10, 0.15, 0.20):
            n = max(3, int(round(fr * len(keys)))); cnt = orden[:n]
            obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
            for nm, proj in {"est_B": hibrido(obs, basev, base_val, keys, 0.5),
                             "est_C": similitud(obs, basev, base_val, keys)}.items():
                ef, af = metrics(proj, finv, keys, fixed)
                en, an = metrics(proj, finv, keys, top2n)
                ep, ap = metrics(proj, finv, keys, top2p)
                print(f"  @{fr*100:>3.0f}% {nm}: fijo err={ef:5.2f}/acc={af:.3f} | "
                      f"top2nac err={en:5.2f}/acc={an:.3f} | top2prov err={ep:5.2f}/acc={ap:.3f}")


if __name__ == "__main__":
    main()

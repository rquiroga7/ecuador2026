# -*- coding: utf-8 -*-
"""
backtest/diag_estB.py — Por qué est_B puede tener más error de composición y mejor
acierto que est_C.

Para 4 bloques (prefecto/alcalde, 10/15/20%), compara por provincia:
  * sesgo medio de la cuota correísta (mean Δ = prod − final),
  * error absoluto medio (mean |Δ|) y desvío (std Δ),
  * correlación entre cuota proyectada y final (ranking),
  * acierto correísmo-vs-derecha (acc2).
"""
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backtest.variantes_swing import unidades, orden_zonas
from backtest.mejoras_v1 import hibrido, similitud


def proj_est(obs, base, base_val, keys):
    return {"est_B": hibrido(obs, base, base_val, keys, lam=0.5),
            "est_C": similitud(obs, base, base_val, keys)}


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
        keys = list(B.index)
        basev, finv = B.values, T.values
        base_val = basev.sum(1)
        ci, oi = cols.index("correismo"), cols.index("derecha")
        g, prov = orden_zonas()
        tz = np.array([g.get(k, np.nan) for k in keys], float)
        tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
        orden = np.argsort(tz, kind="stable")
        pv = np.array([k[:2] for k in keys])
        print(f"\n===== {dig} =====")
        for fr in (0.10, 0.15, 0.20):
            n = max(3, int(round(fr * len(keys))))
            cnt = orden[:n]
            obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
            for nm, proj in proj_est(obs, basev, base_val, keys).items():
                # por provincia
                dp = pd.DataFrame({"p": pv, "pc": proj[:, ci], "pd": proj[:, oi],
                                   "fc": finv[:, ci], "fd": finv[:, oi]})
                gp = dp.groupby("p").sum()
                gp["sc"] = 100 * gp.pc / (gp.pc + gp.pd + 1e-9)
                gp["sf"] = 100 * gp.fc / (gp.fc + gp.fd + 1e-9)
                d = gp.sc - gp.sf
                corr = float(np.corrcoef(gp.sc, gp.sf)[0, 1])
                acc = float(((gp.pc > gp.pd) == (gp.fc > gp.fd)).mean())
                print(f"  {fr*100:>3.0f}% {nm:6s}: sesgo_medio={d.mean():+5.2f} "
                      f"|err|medio={d.abs().mean():5.2f} std={d.std():5.2f} "
                      f"corr={corr:.3f} acc={acc:.3f}")


if __name__ == "__main__":
    main()

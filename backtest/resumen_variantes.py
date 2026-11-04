# -*- coding: utf-8 -*-
"""
backtest/resumen_variantes.py — Fase 4 (docs/backtest.md): resumen vs v1@zona.

Lee `variantes_swing.csv` y, por (esquema, dignidad, 10%/20%), reporta:
  * baseline v1@zona (`v1:pa-c-pr`) y `v1:pr`;
  * mejor método por error y por acierto;
  * si algún método supera a v1@zona.

Salida: D:\\ecuador2026_data\\backtest\\resumen_variantes.csv
Uso: python -m backtest.resumen_variantes
"""
import os
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")

import rutas_datos as rd

BASE = "v1:pa-c-pr"


def main():
    d = pd.read_csv(rd.ruta("backtest/variantes_swing.csv"))
    filas = []
    for esq in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            for fr in (0.10, 0.20):
                s = d[(d.esquema == esq) & (d.dignidad == dig) & (abs(d.frac - fr) < 1e-9)]
                if s.empty:
                    continue
                b = s[s.metodo == BASE]
                be = float(b.err.iloc[0]) if len(b) else float("nan")
                ba = float(b.acc.iloc[0]) if len(b) else float("nan")
                best = s.sort_values("err").iloc[0]
                bestacc = s.sort_values("acc", ascending=False).iloc[0]
                filas.append({
                    "esquema": esq, "dignidad": dig, "frac": int(fr * 100),
                    "v1_zona_err": round(be, 2), "v1_zona_acc": round(ba, 3),
                    "best_err": round(float(best.err), 2), "best_err_metodo": best.metodo,
                    "best_err_acc": round(float(best.acc), 3),
                    "supera_v1_err": bool(float(best.err) < be),
                    "best_acc": round(float(bestacc.acc), 3), "best_acc_metodo": bestacc.metodo,
                })
    out = pd.DataFrame(filas)
    p = rd.ruta("backtest/resumen_variantes.csv")
    out.to_csv(p, index=False)
    print(out.to_string(index=False))
    print("[OK]", p)


if __name__ == "__main__":
    main()

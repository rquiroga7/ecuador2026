# -*- coding: utf-8 -*-
"""
backtest/tabla_metodos.py — Tabla para ELEGIR método de proyección (local 2019→2023).

Compara, por dignidad (prefecto / alcalde) y a distintos % de escrutado:
  * `v1`        — relleno jerárquico espacial (base.py de Brasil).
  * `jerarquico`— logit-swing jerárquico (Proyector).
  * `crudo`     — solo lo escrutado (sin rellenar); error de composición nacional.

Métricas: err = error de composición nacional (puntos); acc = acierto de ganador por
territorio (provincia prefecto, cantón alcalde); top2; marg_err.

Órdenes: aleatorio, prioridad2021 (orden real), adverso.
Salida: D:\\ecuador2026_data\\backtest\\tabla_metodos_<dig>.csv

Uso: python -m backtest.tabla_metodos
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from proyeccion import Proyector
from modelo import v1_brasil
from backtest.bloques_familia import cargar, a_familias, ordenes, metricas, UMBRALES


def corrida(dig):
    g19 = a_familias(cargar(dig, 2019))
    g23 = a_familias(cargar(dig, 2023))
    locs = sorted(set(g19.index) & set(g23.index))
    cols = sorted(set(g19.columns) & set(g23.columns))
    g19 = g19.reindex(index=locs, columns=cols, fill_value=0)
    g23 = g23.reindex(index=locs, columns=cols, fill_value=0)
    terr_of = [k[:2] if dig == "prefecto" else k[3:6] for k in locs]
    base = g19.values.astype(float)
    final = g23.values.astype(float)
    jer = {k: (k[:2], k[3:6], k, k) for k in locs}
    modelo = Proyector(locs, jer, base, base.sum(1))
    grupos_v1 = [np.array([l[:6] for l in locs]),
                 np.array([l[:2] for l in locs]),
                 np.full(len(locs), "EC")]
    ords = ordenes(locs, g19, g23, cols)
    K = len(cols)
    rows = []
    for onombre, orden in ords.items():
        for frac in UMBRALES:
            U = len(locs)
            n = max(3, int(round(frac * U)))
            cnt = orden[:n]
            obs = np.zeros_like(final); obs[cnt] = final[cnt]
            f = np.zeros(U); f[cnt] = 1.0
            salidas = {"v1": v1_brasil.proyectar(obs, base.sum(1), grupos_v1)}
            try:
                r = modelo.proyectar(obs.copy(), f, np.arange(K))
                salidas["jerarquico"] = r["final"] if r else None
            except Exception:
                salidas["jerarquico"] = None
            for met, proj in salidas.items():
                if proj is None:
                    continue
                err, acc, top2, merr = metricas(proj, final, terr_of, cols)
                rows.append({"dignidad": dig, "orden": onombre, "frac": frac,
                             "metodo": met, "err": round(err, 2),
                             "acc": round(acc, 3), "top2": round(top2, 3),
                             "marg_err": round(merr, 3)})
            # crudo: solo lo escrutado
            sc = 100 * obs.sum(0) / max(obs.sum(), 1)
            sf = 100 * final.sum(0) / max(final.sum(), 1)
            rows.append({"dignidad": dig, "orden": onombre, "frac": frac,
                         "metodo": "crudo", "err": round(float(np.abs(sc - sf).sum() / 2), 2),
                         "acc": np.nan, "top2": np.nan, "marg_err": np.nan})
    return pd.DataFrame(rows)


def main():
    out = rd.ruta_dir("backtest")
    todo = []
    for dig in ["prefecto", "alcalde"]:
        df = corrida(dig)
        todo.append(df)
        p = os.path.join(out, f"tabla_metodos_{dig}.csv")
        df.to_csv(p, index=False)
        # tabla legible para el orden realista
        sub = df[df["orden"] == "prioridad2021"]
        piv = sub.pivot_table(index="frac", columns="metodo",
                              values=["err", "acc"], aggfunc="first")
        print(f"\n===== {dig.upper()} · orden prioridad2021 =====")
        print("err (composición nacional, puntos):")
        print(piv["err"].round(2).to_string())
        print("acc (ganador por territorio):")
        print((piv["acc"] * 100).round(1).to_string())
        print(f"[OK] {p}")
    pd.concat(todo).to_csv(os.path.join(out, "tabla_metodos.csv"), index=False)


if __name__ == "__main__":
    main()

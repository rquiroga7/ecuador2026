# -*- coding: utf-8 -*-
"""
backtest/mejoras_v1_paso2.py — Paso 2: combinar métodos que funcionaron (local 2019→2023).

Combos (unidad zona, orden 2021):
  * `C1` = 0.5 v1 + 0.3 G_ens + 0.2 C_sim
  * `C2` = 0.4 v1 + 0.4 G_ens + 0.2 C_sim
  * `C3` dependiente del %: <=10% → 0.5 v1 + 0.5 G_ens; <=20% → 0.3 v1 + 0.4 G_ens + 0.3 C_sim;
          >20% → 0.2 v1 + 0.3 G_ens + 0.5 C_sim
  * `C4` = 0.5 v1 + 0.3 B_hyb + 0.2 G_ens

Compara contra v1, G_ens y C_sim a 5–50% (foco 10/20), 3 esquemas.
Salida: D:\\ecuador2026_data\\backtest\\mejoras_v1_paso2.csv
Uso: python -m backtest.mejoras_v1_paso2
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from proyeccion import Proyector
from modelo import swing, v1_brasil
from backtest.variantes_swing import unidades, orden_zonas, metricas, jer_de, FRACS
from backtest.mejoras_v1 import soft_cascade, hibrido, turnout, similitud


def _b(v):
    return np.clip(np.asarray(v, float), 0, None)


def corrida(esquema, dig, nivel="zona", min_votos=100):
    B = unidades(2019, dig, nivel, esquema)
    T = unidades(2023, dig, nivel, esquema)
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= min_votos) & (T.sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    K = len(cols)
    basev = B.values; finv = T.values; base_val = basev.sum(1)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    jz = jer_de(keys, ["nac", "prov", "cant", "parr"])
    modelo = Proyector(keys, jz, basev, base_val)
    filas = []
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys))))
        cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        f = np.zeros(len(keys)); f[cnt] = 1.0
        v1 = v1_brasil.proyectar(obs, base_val, [np.array([k[:11] for k in keys]),
             np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
             np.full(len(keys), "EC")])
        r = modelo.proyectar(obs.copy(), f, np.arange(K))
        hier = r["final"] if r else v1
        v2, _ = swing.proyectar(basev, obs, np.array(["EC"] * len(keys)), modo="nacional")
        G = 0.6 * v1 + 0.2 * hier + 0.2 * v2
        Cs = similitud(obs, basev, base_val, keys)
        Bh = hibrido(obs, basev, base_val, keys, lam=0.5)
        met = {"v1": v1, "G_ens": G, "C_sim": Cs, "B_hyb": Bh,
               "C1": 0.5 * v1 + 0.3 * G + 0.2 * Cs,
               "C2": 0.4 * v1 + 0.4 * G + 0.2 * Cs,
               "C4": 0.5 * v1 + 0.3 * Bh + 0.2 * G}
        if fr <= 0.10:
            C3 = 0.5 * v1 + 0.5 * G
        elif fr <= 0.20:
            C3 = 0.3 * v1 + 0.4 * G + 0.3 * Cs
        else:
            C3 = 0.2 * v1 + 0.3 * G + 0.5 * Cs
        met["C3_frac"] = C3
        for nombre, proj in met.items():
            err, acc, top2 = metricas(proj, finv, keys, dig)
            filas.append({"esquema": esquema, "dignidad": dig, "metodo": nombre,
                          "frac": round(fr, 2), "err": round(err, 2),
                          "acc": round(acc, 3), "top2": round(top2, 3)})
    return filas


def main():
    filas = []
    for esquema in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            filas += corrida(esquema, dig)
    df = pd.DataFrame(filas)
    p = os.path.join(rd.ruta_dir("backtest"), "mejoras_v1_paso2.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas")
    for esquema in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            sub = df[(df.esquema == esquema) & (df.dignidad == dig) & (df.frac.isin([0.10, 0.20]))]
            if sub.empty:
                continue
            piv = sub.pivot_table(index="metodo", columns="frac", values="err", aggfunc="first")
            piv.columns = [f"err@{int(c*100)}%" for c in piv.columns]
            piv["acc@10%"] = sub[sub.frac == 0.10].set_index("metodo")["acc"]
            piv["acc@20%"] = sub[sub.frac == 0.20].set_index("metodo")["acc"]
            print(f"\n== {esquema} · {dig} ==")
            print(piv.reindex(["v1", "G_ens", "C_sim", "B_hyb", "C1", "C2", "C3_frac", "C4"]).to_string())


if __name__ == "__main__":
    main()

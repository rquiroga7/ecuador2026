# -*- coding: utf-8 -*-
"""
backtest/tabla_correismo.py — Tabla de TODOS los modelos base (sin combos lineales C3/C4/G),
a 10%/15%/20% de escrutado, midiendo:

  * err2 / acc2 — error y acierto de **los dos principales** (correísmo vs su opositor).
  * err_gen / acc_gen — error de composición y acierto de ganador (referencia general).

Modelos:
  * `v1` (cascada estratificada base)
  * `est_A` cascada suavizada · `est_B` híbrido base+swing · `est_H` turnout · `est_C` similitud
  * `v2` nacional · `v4_{prov,cant,parr,zona}`
  * `hier_*` jerárquico con distintos conjuntos de niveles (N nacional, P provincia, C cantón,
    Pa parroquia, Z zona)

Variantes: familias / 3bloques (corr-derecha-otros) / 4bloques (corr-derecha-izq-otros).
Opositor: familias = mayor familia de derecha; 3/4 bloques = `derecha`.

Salida: D:\\ecuador2026_data\\backtest\\correismo_tabla.csv
Uso: python -m backtest.tabla_correismo
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
from backtest.variantes_swing import unidades, orden_zonas, jer_de
from backtest.mejoras_v1 import (soft_cascade, hibrido, turnout, similitud,
                                 turnout_factor, aplicar_turnout)

FRACS = [0.10, 0.15, 0.20]
HIER = {"hier_N-P-Pa": ["nac", "prov", "parr"],
        "hier_N-P-C-Pa": ["nac", "prov", "cant", "parr"],
        "hier_N-P-C-Pa-Z": ["nac", "prov", "cant", "parr", "zona"],
        "hier_N-P-C-Z": ["nac", "prov", "cant", "zona"],
        "hier_N-P-C": ["nac", "prov", "cant"],
        "hier_N-P-Z": ["nac", "prov", "zona"]}


def _opp(cols, T, esquema):
    if esquema == "familias":
        from datos.familias import familia
        from datos.homologar_2019 import DER
        right = {familia(l) for l in DER[2023]} - {"LOCAL", "OTRO", "OTROS"}
        cand = [c for c in cols if c in right and c != "RC"]
        return "RC", (max(cand, key=lambda c: T[c].sum()) if cand else "PSC")
    return "correismo", "derecha"


def metricas(proj, fin, keys, dig, ci, oi):
    tp = float(proj.sum()); tf = float(fin.sum())
    shp = proj.sum(0) / max(tp, 1); shf = fin.sum(0) / max(tf, 1)
    err2_nac = 0.5 * (abs(100 * (shp[ci] - shf[ci])) + abs(100 * (shp[oi] - shf[oi])))
    err_gen = float(100 * np.abs(shp - shf).sum() / 2)
    # --- error por PROVINCIA (solo los dos principales), luego promedio ---
    prov = np.array([k[:2] for k in keys])
    cols = list(range(proj.shape[1]))
    Pg = pd.DataFrame(proj); Pg["p"] = prov; Pg = Pg.groupby("p")[cols].sum()
    Fg = pd.DataFrame(fin); Fg["p"] = prov; Fg = Fg.groupby("p")[cols].sum()
    ip = Pg.index.intersection(Fg.index); Pg = Pg.loc[ip]; Fg = Fg.loc[ip]
    errs = []
    for p in ip:
        sp = Pg.loc[p].values; sf = Fg.loc[p].values
        if sf.sum() <= 0:
            continue
        errs.append(0.5 * (abs(100 * sp[ci] / sp.sum() - 100 * sf[ci] / sf.sum())
                           + abs(100 * sp[oi] / sp.sum() - 100 * sf[oi] / sf.sum())))
    err2 = float(np.mean(errs)) if errs else np.nan
    # --- acc2 por territorio ---
    terr = np.array([k[:2] if dig == "prefecto" else k[3:6] for k in keys])
    Pt = pd.DataFrame(proj); Pt["t"] = terr; Pt = Pt.groupby("t")[cols].sum()
    Ft = pd.DataFrame(fin); Ft["t"] = terr; Ft = Ft.groupby("t")[cols].sum()
    it = Pt.index.intersection(Ft.index); Pt = Pt.loc[it]; Ft = Ft.loc[it]
    m2 = (Ft[ci] + Ft[oi]) > 0
    acc2 = float(((Pt[ci] > Pt[oi])[m2] == (Ft[ci] > Ft[oi])[m2]).mean())
    return err2, err2_nac, acc2, err_gen


def corrida(esquema, dig, min_votos=100):
    B = unidades(2019, dig, "zona", esquema)
    T = unidades(2023, dig, "zona", esquema)
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= min_votos) & (T.sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    ccol, opp = _opp(cols, T, esquema)
    ci, oi = cols.index(ccol), cols.index(opp)
    K = len(cols); basev = B.values; finv = T.values; base_val = basev.sum(1)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    modelos = {n: Proyector(keys, jer_de(keys, nv), basev, base_val) for n, nv in HIER.items()}
    filas = []
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys))))
        cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        f = np.zeros(len(keys)); f[cnt] = 1.0
        met = {}
        met["v1"] = v1_brasil.proyectar(obs, base_val, [np.array([k[:11] for k in keys]),
                    np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
                    np.full(len(keys), "EC")])
        met["est_A"] = soft_cascade(obs, base_val, keys)
        met["est_B"] = hibrido(obs, basev, base_val, keys, lam=0.5)
        met["est_H"] = turnout(obs, basev, base_val, keys)
        met["est_C"] = similitud(obs, basev, base_val, keys)
        rr = turnout_factor(obs, base_val, keys)
        met["est_BH"] = aplicar_turnout(met["est_B"], obs, rr)
        met["est_CH"] = aplicar_turnout(met["est_C"], obs, rr)
        met["est_BCH"] = aplicar_turnout(0.5 * met["est_B"] + 0.5 * met["est_C"], obs, rr)
        met["v2"] = swing.proyectar(basev, obs, np.array(["EC"] * len(keys)), modo="nacional")[0]
        for tn, idx in [("prov", 2), ("cant", 6), ("parr", 11), ("zona", 14)]:
            met[f"v4_{tn}"] = swing.proyectar(basev, obs, np.array([k[:idx] for k in keys]),
                                              modo="territorio")[0]
        for hname, m in modelos.items():
            r = m.proyectar(obs.copy(), f, np.arange(K))
            met[hname] = r["final"] if r else None
        for nombre, proj in met.items():
            if proj is None:
                continue
            e2, e2n, a2, eg = metricas(proj, finv, keys, dig, ci, oi)
            filas.append({"esquema": esquema, "dignidad": dig, "opositor": opp,
                          "metodo": nombre, "frac": int(round(fr * 100)),
                          "err2": round(e2, 2), "err2_nac": round(e2n, 2),
                          "acc2": round(a2, 3), "err_gen": round(eg, 2)})
    return filas


def main():
    filas = []
    for esquema in ("familias", "3bloques", "4bloques"):
        for dig in ("prefecto", "alcalde"):
            filas += corrida(esquema, dig)
    df = pd.DataFrame(filas)
    p = os.path.join(rd.ruta_dir("backtest"), "correismo_tabla.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas")
    for esquema in ("familias", "3bloques", "4bloques"):
        for dig in ("prefecto", "alcalde"):
            sub = df[(df.esquema == esquema) & (df.dignidad == dig)]
            if sub.empty:
                continue
            opp = sub["opositor"].iloc[0]
            for met, col in (("err2", "err2"), ("acc2", "acc2")):
                piv = sub.pivot_table(index="metodo", columns="frac", values=col, aggfunc="first")
                piv.columns = [f"{met}@{c}%" for c in piv.columns]
                if met == "err2":
                    piv = piv.sort_values(piv.columns[0])
                else:
                    piv = piv.reindex(sub.pivot_table(index="metodo", columns="frac",
                                      values="err2", aggfunc="first").sort_values(10).index)
                print(f"\n== {esquema} · {dig} · {met} (opositor={opp}) ==")
                print(piv.to_string())


if __name__ == "__main__":
    main()

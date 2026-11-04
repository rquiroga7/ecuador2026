# -*- coding: utf-8 -*-
"""
backtest/correismo_variantes.py — Comparar 3 variantes de bloque midiendo el error de los
**dos principales** (correísmo vs su principal opositor), para que los métodos sean
comparables.

Variantes:
  * `familias`  — correísmo = familia RC; opositor = mayor familia no-RC.
  * `3bloques`  — correísmo / derecha / otros; opositor = derecha.
  * `4bloques`  — correísmo / derecha / izquierda / otros; opositor = derecha.

Métricas (nacional, en puntos):
  err_c = |Δshare correísmo|, err_o = |Δshare opositor|, err2 = ½(err_c+err_o).
  acc2 = acierto correísmo-vs-opositor por territorio (provincia/cantón).

Métodos: v1@zona, jerárquico N-P-C-Pa, v2 nacional, v4:prov, C3_frac, C4.
Salida: D:\\ecuador2026_data\\backtest\\correismo_variantes.csv
Uso: python -m backtest.correismo_variantes
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
from backtest.variantes_swing import unidades, orden_zonas, jer_de, FRACS
from backtest.mejoras_v1 import soft_cascade, hibrido, similitud


def _share(sumvec, tot):
    return 100 * sumvec / max(tot, 1)


def err_acc2(proj, fin, keys, dig, ci, oi):
    shp = proj.sum(0) / max(proj.sum(), 1)
    shf = fin.sum(0) / max(fin.sum(), 1)
    ec = abs(100 * (shp[ci] - shf[ci]))
    eo = abs(100 * (shp[oi] - shf[oi]))
    terr = np.array([k[:2] if dig == "prefecto" else k[3:6] for k in keys])
    dfp = pd.DataFrame({"c": proj[:, ci], "o": proj[:, oi], "t": terr})
    dff = pd.DataFrame({"c": fin[:, ci], "o": fin[:, oi], "t": terr})
    P = dfp.groupby("t")[["c", "o"]].sum(); F = dff.groupby("t")[["c", "o"]].sum()
    idx = P.index.intersection(F.index)
    P = P.loc[idx]; F = F.loc[idx]
    m = (F["c"] + F["o"]) > 0
    acc2 = float(((P["c"] > P["o"])[m] == (F["c"] > F["o"])[m]).mean())
    return ec, eo, 0.5 * (ec + eo), acc2


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
    if esquema == "familias":
        from datos.familias import familia
        from datos.homologar_2019 import DER
        ccol = "RC"
        right = {familia(l) for l in DER[2023]} - {"LOCAL", "OTRO", "OTROS"}
        cand = [c for c in cols if c in right and c != ccol]
        opp = max(cand, key=lambda c: T[c].sum()) if cand else max(
            [c for c in cols if c != ccol], key=lambda c: T[c].sum())
    else:
        ccol = "correismo"
        opp = "derecha"
    if ccol not in cols or opp not in cols:
        return []
    ci = cols.index(ccol)
    oi = cols.index(opp)
    K = len(cols)
    basev = B.values; finv = T.values; base_val = basev.sum(1)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    modelo = Proyector(keys, jer_de(keys, ["nac", "prov", "cant", "parr"]), basev, base_val)
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
        v4p, _ = swing.proyectar(basev, obs, np.array([k[:2] for k in keys]), modo="territorio")
        G = 0.6 * v1 + 0.2 * hier + 0.2 * v2
        Cs = similitud(obs, basev, base_val, keys)
        Bh = hibrido(obs, basev, base_val, keys, lam=0.5)
        if fr <= 0.10:
            C3 = 0.5 * v1 + 0.5 * G
        elif fr <= 0.20:
            C3 = 0.3 * v1 + 0.4 * G + 0.3 * Cs
        else:
            C3 = 0.2 * v1 + 0.3 * G + 0.5 * Cs
        C4 = 0.5 * v1 + 0.3 * Bh + 0.2 * G
        met = {"v1": v1, "hier": hier, "v2": v2, "v4prov": v4p, "C3_frac": C3, "C4": C4}
        for nombre, proj in met.items():
            ec, eo, e2, a2 = err_acc2(proj, finv, keys, dig, ci, oi)
            filas.append({"esquema": esquema, "dignidad": dig, "opositor": opp,
                          "metodo": nombre, "frac": round(fr, 2),
                          "err_c": round(ec, 2), "err_o": round(eo, 2),
                          "err2": round(e2, 2), "acc2": round(a2, 3)})
    return filas


def main():
    filas = []
    for esquema in ("familias", "3bloques", "4bloques"):
        for dig in ("prefecto", "alcalde"):
            filas += corrida(esquema, dig)
    df = pd.DataFrame(filas)
    p = os.path.join(rd.ruta_dir("backtest"), "correismo_variantes.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas")
    for esquema in ("familias", "3bloques", "4bloques"):
        for dig in ("prefecto", "alcalde"):
            sub = df[(df.esquema == esquema) & (df.dignidad == dig) & (df.frac.isin([0.10, 0.20]))]
            if sub.empty:
                continue
            opp = sub["opositor"].iloc[0]
            piv = sub.pivot_table(index="metodo", columns="frac", values="err2", aggfunc="first")
            piv.columns = [f"err2@{int(c*100)}%" for c in piv.columns]
            piv["acc2@10%"] = sub[sub.frac == 0.10].set_index("metodo")["acc2"]
            piv["acc2@20%"] = sub[sub.frac == 0.20].set_index("metodo")["acc2"]
            print(f"\n== {esquema} · {dig} (opositor={opp}) ==")
            print(piv.reindex(["v1", "hier", "v2", "v4prov", "C3_frac", "C4"]).to_string())


if __name__ == "__main__":
    main()

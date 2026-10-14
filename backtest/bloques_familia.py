# -*- coding: utf-8 -*-
"""
backtest/bloques_familia.py — Backtest local 2019->2023 con bloques = FAMILIAS y
comparación de MÉTODOS de proyección:

  * `jerarquico`     — logit-swing jerárquico (clase `Proyector`).
  * `v2_nacional`    — swing uniforme nacional (método v2 de Brasil).
  * `v4_territorio`  — swing por territorio (provincia/cantón), encogido al nacional.

Órdenes de carga: aleatorio, prioridad-2021 y adverso.
Métricas: error de composición, aciertos de ganador por territorio, contención del
ganador real en el top-2 proyectado, y error del margen top1-top2.

Uso:  python -m backtest.bloques_familia prefecto
"""

import os
import sys

import numpy as np
import pandas as pd

import rutas_datos as rd
from proyeccion import Proyector
from modelo import swing, v1_brasil
from backtest.bloques_lista import cargar, ordenes, UMBRALES

FAMILIA = {
    "5": "RC", "33": "RETO", "72": "RC", "6": "PSC", "18": "MUPP", "21": "CREO",
    "23": "SUMA", "12": "ID", "2": "UP", "3": "PSP", "1": "CD", "8": "Avanza",
    "17": "PSE", "20": "DSI", "35": "MOVER", "25": "CONSTRUYE", "4": "PID",
    "16": "AMIGO",
}
METODOS = ["jerarquico", "v2_nacional", "v4_territorio", "v1_brasil"]


def a_familias(g):
    out = g.copy()
    out.columns = [FAMILIA.get(str(c), "LOCAL") for c in g.columns]
    return out.T.groupby(level=0).sum().T


def _top2(M):
    s = -np.sort(-M, axis=1)
    tot = np.where(M.sum(1) == 0, 1, M.sum(1))
    return (s[:, 0] - s[:, 1]) / tot


def metricas(proj, final_votes, terr_of, cols):
    tot = proj.sum(0)
    sh = 100 * tot / max(tot.sum(), 1)
    fin = final_votes.sum(0)
    shf = 100 * fin / fin.sum()
    err = float(np.abs(sh - shf).sum() / 2)
    dfp = pd.DataFrame(proj, columns=cols); dfp["_t"] = terr_of
    dff = pd.DataFrame(final_votes, columns=cols); dff["_t"] = terr_of
    P = dfp.groupby("_t")[cols].sum(); F = dff.groupby("_t")[cols].sum()
    wp = P.values.argmax(1); wf = F.values.argmax(1)
    acc = float((wp == wf).mean())
    top2p = P.values.argsort(1)[:, ::-1][:, :2]
    contain = float(np.mean([wf[i] in set(top2p[i]) for i in range(len(wf))]))
    margin_err = float(np.abs(_top2(P.values) - _top2(F.values)).mean())
    return err, acc, contain, margin_err


def main():
    dig = sys.argv[1] if len(sys.argv) > 1 else "alcalde"
    g19 = a_familias(cargar(dig, 2019))
    g23 = a_familias(cargar(dig, 2023))
    locs = sorted(set(g19.index) & set(g23.index))
    cols = sorted(set(g19.columns) & set(g23.columns))
    g19 = g19.reindex(index=locs, columns=cols, fill_value=0)
    g23 = g23.reindex(index=locs, columns=cols, fill_value=0)
    terr_of = [k[:2] if dig == "prefecto" else k[3:6] for k in locs]
    base = g19.values.astype(float)
    final_votes = g23.values.astype(float)
    print(f"[{dig}] locs={len(locs)} familias={len(cols)} votos23={int(final_votes.sum()):,}")

    jer = {k: (k[:2], k[3:6], k, k) for k in locs}
    modelo = Proyector(locs, jer, base, base.sum(1))
    grupos_v1 = [np.array([l[:6] for l in locs]), np.array([l[:2] for l in locs]),
                 np.full(len(locs), "EC")]

    err0, acc0, c0, m0 = metricas(base, final_votes, terr_of, cols)
    print(f"  baseline 2019 (sin swing): err={err0:.2f} acc={acc0:.1%} top2={c0:.1%}")

    ords = ordenes(locs, g19, g23, cols)
    filas = []
    for nombre, orden in ords.items():
        for frac in UMBRALES:
            U = len(locs); n = max(3, int(round(frac * U))); cnt = orden[:n]
            obs = np.zeros_like(final_votes); obs[cnt] = final_votes[cnt]
            f = np.zeros(U); f[cnt] = 1.0
            salidas = {}
            try:
                r = modelo.proyectar(obs.copy(), f, np.arange(len(cols)))
                salidas["jerarquico"] = r["final"] if r else None
            except Exception:
                salidas["jerarquico"] = None
            salidas["v2_nacional"], _ = swing.proyectar(base, obs, terr_of, modo="nacional")
            salidas["v4_territorio"], _ = swing.proyectar(base, obs, terr_of, modo="territorio")
            salidas["v1_brasil"] = v1_brasil.proyectar(obs, base.sum(1), grupos_v1)
            for met in METODOS:
                if salidas[met] is None:
                    continue
                err, acc, c, m = metricas(salidas[met], final_votes, terr_of, cols)
                filas.append((met, nombre, frac, round(err, 2), round(acc, 3),
                              round(c, 3), round(m, 3)))
        # línea por orden
        sub = [x for x in filas if x[1] == nombre and abs(x[2] - 0.10) < 1e-9]
        for met, _, frac, err, acc, c, m in sub:
            print(f"  [{nombre}] {met:<14} @10% err={err:5.2f} acc={acc:4.1%} top2={c:4.1%}")

    df = pd.DataFrame(filas, columns=["metodo", "orden", "frac", "err_share", "acc",
                                      "top2", "marg_err"])
    p = os.path.join(rd.ruta_dir("backtest"), f"comparar_metodos_{dig}.csv")
    df.to_csv(p, index=False)
    print(f"[OK] -> {p}")


if __name__ == "__main__":
    main()

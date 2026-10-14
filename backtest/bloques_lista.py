# -*- coding: utf-8 -*-
"""
backtest/bloques_lista.py — Backtest local 2019 -> 2023 a nivel parroquia con
bloques = **cada lista/partido** (versión base; ver `bloques_familia.py`).

Proyecta las seccionales 2023 usando 2019 como referencia con la clase `Proyector`
(logit-swing jerárquico) y órdenes de carga de mesas simulados:
  * aleatorio
  * prioridad 2021 (orden real de publicación observado en la captura de Gaona)
  * adverso (las parroquias donde más crece el partido ganador entran últimas)

Mide, por dignidad (prefecto/alcalde), el error del share nacional de cada partido y
la coincidencia del ganador proyectado por territorio (provincia/cantón) con el final,
según el % de parroquias escrutadas.

Uso:  python -m backtest.bloques_lista prefecto
"""

import os
import sys
import json

import numpy as np
import pandas as pd

import rutas_datos as rd
from proyeccion import Proyector

UMBRALES = [0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]


def cargar(dig, anio):
    p = rd.ruta(f"mesas/parr_partido_{dig}_{anio}.csv.gz")
    v = pd.read_csv(p, dtype=str)
    v["votos"] = v["votos"].astype(int)
    v["partido"] = pd.to_numeric(v["partido"], errors="coerce")
    v = v.dropna(subset=["partido"])
    g = v.groupby(["loc_id", "partido"])["votos"].sum().unstack(fill_value=0)
    g.columns = [int(c) for c in g.columns]
    return g


def _prioridad_2021(locs):
    p = rd.ruta("backtest/orden_parroquia_2021.csv")
    if not os.path.exists(p):
        return None
    o = pd.read_csv(p)
    d = dict(zip(o["loc_id"], o["min_medio"]))
    pr = np.array([d.get(k, np.nan) for k in locs], float)
    if np.isnan(pr).all():
        return None
    pr = np.where(np.isnan(pr), np.nanmedian(pr), pr)
    return pr


def ordenes(locs, g19, g23, cols):
    U = len(locs)
    rng = np.random.default_rng(42)
    o = {"aleatorio": rng.permutation(U)}
    pr = _prioridad_2021(locs)
    if pr is not None:
        o["prioridad2021"] = np.argsort(pr, kind="stable")
    # adverso: partido top por 2023, ordenar por su swing local ascendente
    tot23 = g23.values.sum(0)
    top = cols[int(np.argmax(tot23))]
    v19 = g19.sum(1).replace(0, np.nan)
    v23 = g23.sum(1).replace(0, np.nan)
    delta = ((g23[top] / v23) - (g19[top] / v19)).fillna(0).values
    o["adverso"] = np.argsort(delta, kind="stable")
    return o


def proyectar_unidades(modelo, final_votes, orden, frac, K):
    U = final_votes.shape[0]
    n = max(3, int(round(frac * U)))
    counted = orden[:n]
    O = np.zeros((U, K))
    O[counted] = final_votes[counted]
    f = np.zeros(U)
    f[counted] = 1.0
    bloque = np.arange(K)
    r = modelo.proyectar(O, f, bloque)
    return r


def evaluar(res_final, final_votes, terr_of, cols):
    """res_final: [U,K] votos proyectados. Devuelve (error_share_nac, aciertos, n_terr)."""
    tot = res_final.sum(0)
    sh = 100 * tot / tot.sum()
    fin = final_votes.sum(0)
    shf = 100 * fin / fin.sum()
    err = float(np.abs(sh - shf).sum() / 2)     # error total de composición (puntos)
    # ganador por territorio
    dfp = pd.DataFrame(res_final, columns=cols)
    dfp["_t"] = terr_of
    proy_t = dfp.groupby("_t")[cols].sum()
    win_proy = proy_t.values.argmax(1)
    dff = pd.DataFrame(final_votes, columns=cols)
    dff["_t"] = terr_of
    win_fin = dff.groupby("_t")[cols].sum().values.argmax(1)
    return err, int((win_proy == win_fin).sum()), len(win_fin)


def main():
    dig = sys.argv[1] if len(sys.argv) > 1 else "prefecto"
    terr = "provincia" if dig == "prefecto" else "canton"
    g19 = cargar(dig, 2019)
    g23 = cargar(dig, 2023)
    locs = sorted(set(g19.index) & set(g23.index))
    cols = sorted(set(g19.columns) & set(g23.columns))
    g19 = g19.reindex(index=locs, columns=cols, fill_value=0)
    g23 = g23.reindex(index=locs, columns=cols, fill_value=0)
    print(f"[{dig}] locs comunes={len(locs)} partidos comunes={len(cols)} "
          f"votos2023={int(g23.values.sum()):,}")

    jer = {k: (k[:2], k[3:6], k, k) for k in locs}
    base = g19.values.astype(float)
    modelo = Proyector(locs, jer, base, base.sum(1))
    final_votes = g23.values.astype(float)
    terr_of = [k[:2] if dig == "prefecto" else k[3:6] for k in locs]

    ords = ordenes(locs, g19, g23, cols)
    filas = []
    for nombre, orden in ords.items():
        for frac in UMBRALES:
            try:
                r = proyectar_unidades(modelo, final_votes, orden, frac, len(cols))
            except Exception as e:
                r = None
            if r is None:
                filas.append((nombre, frac, np.nan, np.nan, np.nan)); continue
            err, ok, n = evaluar(r["final"], final_votes, terr_of, cols)
            filas.append((nombre, frac, round(err, 3), ok, n))
            print(f"  {nombre:<13} {frac*100:>4.0f}%  err_share={err:5.2f}pt  "
                  f"ganador {terr} {ok}/{n}")
    df = pd.DataFrame(filas, columns=["orden", "frac", "err_share", "aciertos", "n_terr"])
    out = rd.ruta_dir("backtest")
    p = os.path.join(out, f"backtest_local_{dig}_2019_2023.csv")
    df.to_csv(p, index=False)
    print(f"[OK] -> {p}")


if __name__ == "__main__":
    main()

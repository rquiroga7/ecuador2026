# -*- coding: utf-8 -*-
"""
forense/simular.py — ¿Detectamos mesas amañadas, aun si son sutiles?

Toma las juntas reales (prefecto 2023), inyecta anomalías en una fracción de mesas
y mide si el score de `forense/juntas.py` las separa de las limpias (AUC y TPR a FPR
fijo). Escenarios:
  * `boost:<m>`     — transfiere m·(votos no-líder) al líder (sesga el share, emitidos igual).
  * `stuffing:<m>`  — agrega m·(votos válidos) al líder **y sube los emitidos** (=ballot
                      stuffing; debería cazarlo `z_emit`/`z_bn`).
  * `coerce:<m>`    — fuerza al líder a un share m.
  * `round5`/`round10` — redondea los conteos (señal de dígitos).

Uso:  python -m forense.simular prefecto
"""

import os
import sys
import numpy as np
import pandas as pd

import rutas_datos as rd
from forense import juntas


def _auc(scores, y):
    s = np.asarray(scores, float); y = np.asarray(y, bool)
    r = pd.Series(s).rank().values
    n1 = y.sum(); n0 = (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _metricas(scores, y, fpr=0.01):
    s = np.asarray(scores, float); y = np.asarray(y, bool)
    n1 = y.sum(); n0 = (~y).sum()
    k = max(1, int(fpr * n0))
    top = np.argsort(-s)[:k]
    return (float(y[top].sum() / n1) if n1 else np.nan, float(y[top].mean()), k)


def un_escenario(wide, rng, modo, mag, frac=0.05):
    meta, M, tot, cols = juntas.preparar(wide)
    meta = meta.reset_index(drop=True)
    n = len(M)
    idx = rng.choice(n, int(round(frac * n)), replace=False)
    mask = np.zeros(n, bool); mask[idx] = True

    prov = meta["prov"].values
    totv = M.groupby(prov).sum()
    lider = {u: cols[int(np.argmax(totv.loc[u].values))] for u in totv.index}
    i_lider = np.array([cols.index(lider[p]) for p in prov])

    A = M.values.copy()
    em = tot["emitidos"].values.copy()
    for i in idx:
        l = i_lider[i]
        if modo == "boost":
            others = A[i].sum() - A[i, l]
            A[i, l] += mag * others
        elif modo == "stuffing":
            add = mag * max(A[i].sum(), 1.0)
            A[i, l] += add
            em[i] += add
        elif modo == "coerce":
            v = A[i].sum()
            A[i, l] = mag * v
        elif modo == "round5":
            A[i] = np.round(A[i] / 5) * 5
        elif modo == "round10":
            A[i] = np.round(A[i] / 10) * 10

    M2 = pd.DataFrame(A, columns=cols)
    tot2 = tot.reset_index(drop=True).copy()
    tot2["emitidos"] = em
    sc = juntas.score_matriz(meta, M2, tot2, cols).set_index("mesa_id")
    sc = sc.reindex(meta["mesa_id"].values)
    y = pd.Series(mask, index=meta["mesa_id"].values).reindex(sc.index).values
    auc = _auc(sc["score"].values, y)
    t1, _, _ = _metricas(sc["score"].values, y, 0.01)
    t5, _, _ = _metricas(sc["score"].values, y, 0.05)
    return auc, t1, t5, len(idx)


def main():
    dig = sys.argv[1] if len(sys.argv) > 1 else "prefecto"
    wide = juntas.cargar(dig, 2023)
    escenarios = [
        ("stuffing (obvio)", "stuffing", 0.80),
        ("stuffing (medio)", "stuffing", 0.30),
        ("stuffing (sutil)", "stuffing", 0.12),
        ("boost share (obvio)", "boost", 0.80),
        ("boost share (sutil)", "boost", 0.20),
        ("coerce 0.9", "coerce", 0.90),
        ("round5", "round5", None),
    ]
    filas = []
    print(f"[{dig}] mesas={len(wide)} | 5% amañadas | AUC y TPR@1%/5% (FPR)")
    for nombre, modo, mag in escenarios:
        auc, t1, t5, n = un_escenario(wide, np.random.default_rng(7), modo, mag)
        filas.append((nombre, modo, mag, round(auc, 3), round(t1, 3), round(t5, 3)))
        print(f"  {nombre:<20} AUC={auc:5.3f}  TPR@1%={t1:5.1%}  TPR@5%={t5:5.1%}")
    pd.DataFrame(filas, columns=["escenario", "modo", "mag", "auc", "tpr1", "tpr5"]).to_csv(
        os.path.join(rd.ruta_dir("forense"), f"simulacion_deteccion_{dig}.csv"), index=False)
    print(f"[OK] -> {rd.ruta_dir('forense')}")


if __name__ == "__main__":
    main()

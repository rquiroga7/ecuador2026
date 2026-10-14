# -*- coding: utf-8 -*-
"""
inferencia/ecologica.py — Inferencia ecológica de las PRESIDENCIALES (Ecuador).

Estima por máxima verosimilitud (EM) la MATRIZ DE TRANSICIÓN de votos entre la
presidencial de **2021** (origen) y la de **2025** (destino), a nivel de **parroquia**.
theta[j,k] = P(votar al bloque k en 2025 | haber votado al bloque j en 2021).

Bloques (por código interno OP):
  2021: RC=Arauz, CREO=Lasso, MUPP=Yaku, ID=Hervás, RESTO
  2025: RC=Luisa, ADN=Noboa, MUPP=Iza, CREO=Tabacchi, PSC=Kronfle, RESTO

Modelo: en cada parroquia i, la distribución del destino se ajusta como
    y_ik = sum_j x_ij * theta_jk
con x = shares de origen y y = shares de destino. EM + bootstrap sobre parroquias.

Limitación: **no incluye "No voto"** (requiere el padrón/electores por parroquia de
2021 y 2025, aún no descargado); se estima solo migración voto→voto.

Salidas (D:\\ecuador2026_data\\ei\\):
  transicion_presidencial_2021_2025.csv  (theta en %)
  transicion_presidencial_2021_2025_ic.csv (IC bootstrap)
  heatmap_presidencial_2021_2025.png
  resumen_ei_presidencial.json

Uso:  python -m inferencia.ecologica
"""

import os
import sys
import json

import numpy as np
import pandas as pd

import rutas_datos as rd
import estilo_plot as ep
import datos.registro as registro

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MAPA = {
    2021: {"1030": "RC", "1021": "CREO", "2": "MUPP", "42": "ID"},
    2025: {"1644": "RC", "500": "ADN", "7": "MUPP", "99": "CREO", "32": "PSC"},
}
ORIG = ["RC", "MUPP", "CREO", "ID", "RESTO", "NOV"]
DEST = ["RC", "ADN", "MUPP", "CREO", "PSC", "RESTO", "NOV"]


def cargar(anio, cats):
    v = pd.read_csv(rd.ruta(f"mesas/parr_votos_nacional_{anio}.csv.gz"), dtype=str)
    v = v[v["dignidad"].str.contains("PRESID", case=False, na=False)].copy()
    v["votos"] = v["votos"].astype(int)
    v["op"] = pd.to_numeric(v["op_codigo"], errors="coerce")
    v = v.dropna(subset=["op"])
    v["op"] = v["op"].astype(int).astype(str)
    v["blk"] = v["op"].map(MAPA[anio]).fillna("RESTO")
    v["loc_id"] = v["cod_provincia"].str.cat([v["cod_canton"], v["cod_parroquia"]],
                                             sep="-")
    t = v.pivot_table(index="loc_id", columns="blk", values="votos",
                      aggfunc="sum", fill_value=0)
    # "No voto" = electores habilitados − sufragantes (registro electoral del año)
    nv = registro.no_voto(anio)
    t["NOV"] = nv.reindex(t.index).fillna(0)
    return t.reindex(columns=cats, fill_value=0)


def em_transicion(Xs, Ys, iters=2000, tol=1e-12, theta0=None):
    """EM para theta[j,k] = P(destino k | origen j) con shares por unidad."""
    Ko, Kd = Xs.shape[1], Ys.shape[1]
    theta = np.full((Ko, Kd), 1.0 / Kd) if theta0 is None else theta0.copy()
    for _ in range(iters):
        p = np.clip(Xs @ theta, 1e-15, None)
        w = Ys / p
        num = (Xs[:, :, None] * theta[None, :, :]) * w[:, None, :]
        Z = num.sum(0)
        new = Z / Z.sum(1, keepdims=True)
        if np.max(np.abs(new - theta)) < tol:
            theta = new
            break
        theta = new
    return theta


def _shares(M):
    s = M.sum(1, keepdims=True)
    s = np.where(s <= 0, 1, s)
    return M / s


def ajustar(X, Y, n_boot=400, rng=None):
    val = (X.sum(1) > 0) & (Y.sum(1) > 0)
    X, Y = X[val], Y[val]
    Xs, Ys = _shares(X), _shares(Y)
    theta = em_transicion(Xs, Ys)
    rng = rng or np.random.default_rng(0)
    boots = np.full((n_boot,) + theta.shape, np.nan)
    for b in range(n_boot):
        idx = rng.integers(0, len(Xs), len(Xs))
        boots[b] = em_transicion(Xs[idx], Ys[idx], iters=400)
    lo = np.nanpercentile(boots, 5, axis=0)
    hi = np.nanpercentile(boots, 95, axis=0)
    return theta, lo, hi, int(val.sum())


def heatmap(theta, path):
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(100 * theta, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(DEST))); ax.set_xticklabels(DEST)
    ax.set_yticks(range(len(ORIG))); ax.set_yticklabels(ORIG)
    ax.set_xlabel("Destino (2025)"); ax.set_ylabel("Origen (2021)")
    for i in range(len(ORIG)):
        for j in range(len(DEST)):
            ax.text(j, i, f"{100*theta[i,j]:.0f}", ha="center", va="center",
                    fontsize=9, color="black")
    ax.set_title("Transición de votos presidencial 2021 → 2025 (%)")
    ep.mpl(fig, "Inferencia ecológica (EM) por parroquia; migración de votos voto→voto.")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    t21 = cargar(2021, ORIG)
    t25 = cargar(2025, DEST)
    locs = sorted(set(t21.index) & set(t25.index))
    X = t21.reindex(index=locs).to_numpy(float)
    Y = t25.reindex(index=locs).to_numpy(float)
    print(f"[EI] parroquias comunes={len(locs)} | origen={ORIG} destino={DEST}")
    theta, lo, hi, nval = ajustar(X, Y)
    out = rd.ruta_dir("ei")
    pd.DataFrame(100 * theta, index=ORIG, columns=DEST).round(1).to_csv(
        os.path.join(out, "transicion_presidencial_2021_2025.csv"))
    ic = pd.DataFrame(
        [{"origen": ORIG[i], "destino": DEST[j], "media": round(100 * theta[i, j], 1),
          "p5": round(100 * lo[i, j], 1), "p95": round(100 * hi[i, j], 1)}
         for i in range(len(ORIG)) for j in range(len(DEST))])
    ic.to_csv(os.path.join(out, "transicion_presidencial_2021_2025_ic.csv"), index=False)
    heatmap(theta, os.path.join(out, "heatmap_presidencial_2021_2025.png"))
    resumen = {
        "parroquias": int(nval),
        "origen": ORIG, "destino": DEST,
        "theta_pct": (100 * theta).round(1).tolist(),
        "diagonal": {ORIG[i]: round(100 * theta[i, ORIG.index(ORIG[i])], 1)
                     for i in range(len(ORIG)) if ORIG[i] in DEST},
        "nota": "Sin 'No voto' (falta padrón por parroquia).",
    }
    with open(os.path.join(out, "resumen_ei_presidencial.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(pd.DataFrame(100 * theta, index=ORIG, columns=DEST).round(1).to_string())
    print(f"[OK] -> {out}")


if __name__ == "__main__":
    main()

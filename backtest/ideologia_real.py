# -*- coding: utf-8 -*-
"""
backtest/ideologia_real.py — Bloques por **ideología real** (izquierda / derecha /
otros-locales) y verificación de la correlación 2021→2023 por recinto.

Corrige el sesgo del mapa previo (`unificaideologias.py`), donde partidos de
**izquierda** (UP=Unidad Popular, PSE=Partido Socialista, ID=Iquierda Democrática,
CD=Centro Democrático, SUR, AMIGO) quedaban en el bloque "anticorreísta" y absorbían
el voto correísta/MUPP, inflando el anticorreísmo.

Bloques:
  * izquierda : RC, MUPP, ID, UP, PSE, CD, SUR, AMIGO
  * derecha   : PSC, CREO, SUMA, PSP, PID, MF, Avanza, MOVER, CONSTRUYE, Todos, RETO
  * otro      : LOCAL (movimientos puramente locales)

2021 (por org): izquierda = UNES(1005), 35, MUPP(18), ID(12); derecha = resto; otro = Ø.

Salidas: D:\\ecuador2026_data\\backtest\\scatter_ideologia_2021_2023.png y
         correlacion_ideologia.csv
Uso:     python -m backtest.ideologia_real
"""

import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import rutas_datos as rd
from datos.familias import familia

BLOQUES = ["izquierda", "derecha", "otro"]

IZQ_2023 = {"RC", "MUPP", "ID", "UP", "PSE", "CD", "SUR", "AMIGO"}
OTRO_2023 = {"LOCAL"}

IZQ_ORG_2021 = {1005, 35, 18, 12}   # UNES/Arauz, org35, MUPP, ID
# el resto de orgs 2021 -> derecha


def bloque_fam(f):
    if f in IZQ_2023:
        return "izquierda"
    if f in OTRO_2023:
        return "otro"
    return "derecha"


def bloque_org(org):
    return "izquierda" if org in IZQ_ORG_2021 else "derecha"


def _z(s, n):
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).str.zfill(n)


def recintos_2021():
    g = pd.read_csv(rd.ruta("raw/gaona_2021_presidencia_junta.csv"), dtype=str,
                    usecols=["cod_prov", "cod_cant", "parroquia", "recinto",
                             "cod_org_pol", "votos"])
    g["votos"] = pd.to_numeric(g["votos"], errors="coerce").fillna(0).astype(int)
    g["rec"] = (_z(g["cod_prov"], 2) + "-" + _z(g["cod_cant"], 3) + "-"
                + _z(g["parroquia"], 4) + "-" + _z(g["recinto"], 2))
    g["bloque"] = pd.to_numeric(g["cod_org_pol"], errors="coerce").apply(bloque_org)
    t = g.pivot_table(index="rec", columns="bloque", values="votos", aggfunc="sum",
                      fill_value=0).reindex(columns=BLOQUES, fill_value=0)
    return t


def recintos_2023(dig="prefecto"):
    v = pd.read_csv(rd.ruta(f"mesas/votos_{dig}_2023.csv.gz"), dtype=str,
                    usecols=["loc_id", "lista", "votos"])
    v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
    sp = v["loc_id"].str.split("-")
    v["rec"] = sp.str[0] + "-" + sp.str[1] + "-" + sp.str[3] + "-" + sp.str[4]
    v["bloque"] = v["lista"].map(lambda x: bloque_fam(familia(x)))
    t = v.pivot_table(index="rec", columns="bloque", values="votos", aggfunc="sum",
                      fill_value=0).reindex(columns=BLOQUES, fill_value=0)
    return t


def _shares(t):
    out = t.copy()
    out["total"] = t.sum(axis=1)
    tot = out["total"].replace(0, np.nan)
    for b in BLOQUES:
        out[b + "_sh"] = 100 * t[b] / tot
    return out


def correlaciones(A, B, nivel=None):
    if nivel:
        A = A.groupby(A.index.str[:nivel])[BLOQUES + ["total"]].sum()
        B = B.groupby(B.index.str[:nivel])[BLOQUES + ["total"]].sum()
    idx = A.index.intersection(B.index)
    a, b = A.loc[idx], B.loc[idx]
    filas = []
    for bl in BLOQUES:
        sa = 100 * a[bl] / a["total"]
        sb = 100 * b[bl] / b["total"]
        m = sa.notna() & sb.notna()
        r = float(np.corrcoef(sa[m], sb[m])[0, 1]) if m.sum() > 5 else np.nan
        filas.append({"bloque": bl, "r": round(r, 3), "n": int(m.sum())})
    return pd.DataFrame(filas)


def main():
    S21 = _shares(recintos_2021())
    S23 = _shares(recintos_2023("prefecto"))
    com = S21.index.intersection(S23.index)
    A, B = S21.loc[com], S23.loc[com]

    print("Correlación share por recinto (2021 vs 2023), bloques ideología real:")
    print(correlaciones(A, B).to_string(index=False))
    print("\nProvincia:")
    print(correlaciones(A, B, nivel=2).to_string(index=False))

    # scatter 3 facetas
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    col = {"izquierda": "#1f77b4", "derecha": "#d62728", "otro": "#2ca02c"}
    for ax, bl in zip(axes, BLOQUES):
        x, y = B[bl + "_sh"], A[bl + "_sh"]
        m = x.notna() & y.notna()
        r = float(np.corrcoef(x[m], y[m])[0, 1])
        ax.scatter(x[m], y[m], s=6, alpha=0.35, color=col[bl])
        ax.plot([0, 100], [0, 100], "k--", lw=0.8)
        ax.set_title(f"{bl}  (r={r:.3f})")
        ax.set_xlabel("share 2023 (%) · prefecto")
        ax.set_ylabel("share 2021 (%) · presidencial")
        ax.set_xlim(-2, 102); ax.set_ylim(-2, 102); ax.grid(alpha=0.2)
    fig.suptitle("Bloques por ideología real · recintos 2021 vs 2023", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(rd.ruta_dir("backtest"), "scatter_ideologia_2021_2023.png")
    fig.savefig(out, dpi=130, bbox_inches="tight"); plt.close(fig)
    correlaciones(A, B).to_csv(os.path.join(rd.ruta_dir("backtest"),
                                            "correlacion_ideologia.csv"), index=False)
    print("\n[OK]", out)


if __name__ == "__main__":
    main()

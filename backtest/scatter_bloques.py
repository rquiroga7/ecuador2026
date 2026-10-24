# -*- coding: utf-8 -*-
"""
backtest/scatter_bloques.py — Scatter de 3 facetas (un bloque por panel) comparando
2021 (presidencial) vs 2023 (seccional prefecto) por **recinto**.

Cada punto es un recinto (común a ambos años): x = share del bloque en 2023,
y = share del bloque en 2021. Si el mapeo de bloques y los IDs de recinto están bien,
los puntos deben pegarse a la diagonal y=x (correlación alta). Los puntos alejados
señalan recintos donde el bloque se movió mucho → candidatos mal asignados, cambios
reales, o emparejamiento de recinto erróneo.

Salida: D:\\ecuador2026_data\\backtest\\scatter_bloques_2021_2023.png
Uso:    python -m backtest.scatter_bloques
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
from backtest import validar_recintos_bloques as V

BL = ["correista", "anticorreista", "diferentes"]
COL = {"correista": "#1f77b4", "anticorreista": "#d62728", "diferentes": "#2ca02c"}
RESALTAR = "09-125-1435-01"


def datos():
    t21 = V.recintos_2021()
    t23 = V.recintos_2023("prefecto")
    com = t21.index.intersection(t23.index)
    return t21.loc[com], t23.loc[com]


def _prov_nombres():
    p = rd.ruta("catalogo/provincia.csv.gz")
    if not os.path.exists(p):
        return {}
    d = pd.read_csv(p, dtype=str)
    return dict(zip(d["COD_PROVINCIA"].str.zfill(2), d["NOM_PROVINCIA"].str.strip()))


def scatter(out=None, resaltar=RESALTAR, min_votos=100):
    """Scatter de 3 facetas. Filtra recintos con < `min_votos` (min de ambos años),
    tamaño del punto ∝ votos, color por provincia, leyenda abajo."""
    from matplotlib.lines import Line2D
    A, B = datos()
    prov = A.index.str.slice(0, 2)
    tot = np.minimum(A["total"], B["total"]).astype(float)
    keep = (tot >= min_votos).values
    provs = sorted(pd.unique(prov[keep]))
    nom = _prov_nombres()
    cmap = plt.get_cmap("tab20")
    palette = {p: cmap(i % 20) for i, p in enumerate(provs)}
    colarr = [palette[p] for p in prov[keep]]
    s = 6 + 300 * (tot[keep].values / max(tot[keep].max(), 1))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8))
    pos_res = A.index.get_indexer([resaltar])[0] if resaltar in A.index else -1
    for ax, b in zip(axes, BL):
        x = B[b + "_sh"][keep].values
        y = A[b + "_sh"][keep].values
        ax.scatter(x, y, s=s, c=colarr, alpha=0.6, edgecolor="none")
        ax.plot([0, 100], [0, 100], "k--", lw=0.8)
        r = float(np.corrcoef(x, y)[0, 1])
        ax.set_title(f"{b}  (r={r:.3f}, n={int(keep.sum())})")
        ax.set_xlabel("share 2023 (%)  ·  prefecto")
        ax.set_ylabel("share 2021 (%)  ·  presidencial")
        ax.set_xlim(-2, 102); ax.set_ylim(-2, 102)
        ax.grid(alpha=0.2)
        if pos_res >= 0 and keep[pos_res]:
            ax.scatter([x[pos_res]], [y[pos_res]], s=90, facecolor="none",
                       edgecolor="black", linewidth=1.6, zorder=5)
            ax.annotate(resaltar, (x[pos_res], y[pos_res]),
                        textcoords="offset points", xytext=(6, 6), fontsize=8)
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7,
                      markerfacecolor=palette[p], markeredgecolor="none",
                      label=nom.get(p, p)) for p in provs]
    fig.legend(handles=handles, loc="lower center", ncol=8, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Bloques ideológicos por recinto · 2021 (presidencial) vs 2023 (prefecto)\n"
                 f"puntos ≥ {min_votos} votos · tamaño ∝ votos · color = provincia",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    p = out or os.path.join(rd.ruta_dir("backtest"), "scatter_bloques_2021_2023.png")
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("[OK]", p, f"({int(keep.sum())} recintos >= {min_votos} votos)")
    return p


def _presencia():
    """(pres21, pres23): DataFrame provincia × bloque con True si el bloque tuvo
    votos en esa provincia (proxy de 'estaba en papeleta')."""
    g = _gaona()
    g["prov"] = g["rec"].str.slice(0, 2)
    org = pd.to_numeric(g["cod_org_pol"], errors="coerce")

    def b21(o):
        if o in V.CORREISTA_ORG:
            return "correista"
        if o in V.ANTI_ORG:
            return "anticorreista"
        return "diferentes"
    g["bl"] = org.map(b21)
    p21 = (g[g["votos"] > 0].groupby(["prov", "bl"]).size().unstack(fill_value=0) > 0)
    v = _votos23()
    v["prov"] = v["rec"].str.slice(0, 2)
    v["bl"] = v["familia"].map(V._bloque_fam)
    p23 = (v[v["votos"] > 0].groupby(["prov", "bl"]).size().unstack(fill_value=0) > 0)
    for df in (p21, p23):
        for bl in BL:
            if bl not in df.columns:
                df[bl] = False
    return p21, p23


def scatter_2(out=None, resaltar=RESALTAR, min_votos=100, excluir_ausentes=True):
    """Igual que `scatter` pero con **2 bloques**: correísmo vs resto.

    `excluir_ausentes`: descarta recintos cuya provincia no tuvo correísmo en
    papeleta en alguno de los dos años (p. ej. Zamora Chinchipe 2023)."""
    from matplotlib.lines import Line2D
    A, B = datos()
    prov = A.index.str.slice(0, 2)
    tot = np.minimum(A["total"], B["total"]).astype(float)
    keep = (tot >= min_votos).values
    excl = 0
    if excluir_ausentes:
        p21, p23 = _presencia()
        ok = (p21["correista"].reindex(prov).fillna(False).values
              & p23["correista"].reindex(prov).fillna(False).values)
        excl = int((keep & ~ok).sum())
        keep = keep & ok
        print(f"[i] excluidos {excl} recintos por correísmo fuera de papeleta; "
              f"provincias ausentes: {sorted(set(prov[~ok]))}")
    sh21 = 100 * A["correista"] / A["total"]
    sh23 = 100 * B["correista"] / B["total"]
    paneles = [("correismo", sh23, sh21), ("resto", 100 - sh23, 100 - sh21)]

    provs = sorted(pd.unique(prov[keep]))
    nom = _prov_nombres()
    cmap = plt.get_cmap("tab20")
    palette = {p: cmap(i % 20) for i, p in enumerate(provs)}
    colarr = [palette[p] for p in prov[keep]]
    s = 6 + 300 * (tot[keep].values / max(tot[keep].max(), 1))
    pos_res = A.index.get_indexer([resaltar])[0] if resaltar in A.index else -1

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
    for ax, (titulo, x_all, y_all) in zip(axes, paneles):
        x = x_all[keep].values
        y = y_all[keep].values
        ax.scatter(x, y, s=s, c=colarr, alpha=0.6, edgecolor="none")
        ax.plot([0, 100], [0, 100], "k--", lw=0.8)
        r = float(np.corrcoef(x, y)[0, 1])
        ax.set_title(f"{titulo}  (r={r:.3f}, n={int(keep.sum())})")
        ax.set_xlabel("share 2023 (%)  ·  prefecto")
        ax.set_ylabel("share 2021 (%)  ·  presidencial")
        ax.set_xlim(-2, 102); ax.set_ylim(-2, 102)
        ax.grid(alpha=0.2)
        if pos_res >= 0 and keep[pos_res]:
            ax.scatter([x[pos_res]], [y[pos_res]], s=90, facecolor="none",
                       edgecolor="black", linewidth=1.6, zorder=5)
            ax.annotate(resaltar, (x[pos_res], y[pos_res]),
                        textcoords="offset points", xytext=(6, 6), fontsize=8)
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7,
                      markerfacecolor=palette[p], markeredgecolor="none",
                      label=nom.get(p, p)) for p in provs]
    fig.legend(handles=handles, loc="lower center", ncol=8, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Dos bloques por recinto (correísmo vs resto) · 2021 vs 2023\n"
                 f"puntos ≥ {min_votos} votos · tamaño ∝ votos · color = provincia",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    p = out or os.path.join(rd.ruta_dir("backtest"), "scatter_2bloques_2021_2023.png")
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("[OK]", p, f"({int(keep.sum())} recintos >= {min_votos} votos)")
    return p


def outliers(b="correista", n=15):
    """Recintos con mayor caída/ subida del bloque, con su composición en ambos años."""
    A, B = datos()
    d = (B[b + "_sh"] - A[b + "_sh"]).dropna().sort_values()
    cols = ["prov_cant_parr_zona", "sh2021", "sh2023", "delta",
            "top2021", "top2023", "total21", "total23"]
    filas = []
    idx = list(d.index[:n]) + list(d.index[-n:][::-1])
    for k in idx:
        filas.append({
            "prov_cant_parr_zona": k,
            "sh2021": round(float(A.loc[k, b + "_sh"]), 1),
            "sh2023": round(float(B.loc[k, b + "_sh"]), 1),
            "delta": round(float(B.loc[k, b + "_sh"] - A.loc[k, b + "_sh"]), 1),
            "top2021": _top_2021(k), "top2023": _top_2023(k),
            "total21": int(A.loc[k, "total"]), "total23": int(B.loc[k, "total"])})
    return pd.DataFrame(filas, columns=cols)


def _top_2021(rec, k=3):
    g = _gaona()
    r = g[g["rec"] == rec]
    t = r.groupby("cod_org_pol")["votos"].sum().sort_values(ascending=False).head(k)
    return ", ".join(f"{a}:{int(v)}" for a, v in t.items())


def _top_2023(rec, k=3):
    v = _votos23()
    r = v[v["rec"] == rec]
    t = r.groupby("familia")["votos"].sum().sort_values(ascending=False).head(k)
    return ", ".join(f"{a}:{int(v_)}" for a, v_ in t.items())


_CACHE = {}


def _gaona():
    if "g" not in _CACHE:
        g = pd.read_csv(rd.ruta("raw/gaona_2021_presidencia_junta.csv"), dtype=str,
                        usecols=["cod_prov", "cod_cant", "parroquia", "recinto",
                                 "cod_org_pol", "votos"])
        g["votos"] = pd.to_numeric(g["votos"], errors="coerce").fillna(0).astype(int)
        z = lambda c, n: pd.to_numeric(g[c], errors="coerce").astype("Int64").astype(str).str.zfill(n)
        g["rec"] = z("cod_prov", 2) + "-" + z("cod_cant", 3) + "-" + z("parroquia", 4) + "-" + z("recinto", 2)
        _CACHE["g"] = g
    return _CACHE["g"]


def _votos23():
    if "v" not in _CACHE:
        from datos.familias import familia
        v = pd.read_csv(rd.ruta("mesas/votos_prefecto_2023.csv.gz"), dtype=str,
                        usecols=["loc_id", "lista", "votos"])
        v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
        v["familia"] = v["lista"].map(familia)
        s = v["loc_id"].str.split("-")
        v["rec"] = s.str[0] + "-" + s.str[1] + "-" + s.str[3] + "-" + s.str[4]
        _CACHE["v"] = v
    return _CACHE["v"]


def main():
    scatter()
    for b in BL:
        print(f"\n=== outliers {b} (extremos de delta) ===")
        print(outliers(b).to_string(index=False))


if __name__ == "__main__":
    main()

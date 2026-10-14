# -*- coding: utf-8 -*-
"""
inferencia/local.py — Inferencia ecológica de las SECCIONALES (Ecuador), 2019 → 2023.

Estima por EM la matriz de transición de votos **entre familias políticas** a nivel de
parroquia, para **prefecto** y **alcalde** (las únicas dignidades locales con par
2019→2023 a nivel parroquia). Incluye **No voto** (NOV) usando el registro electoral
y los sufragantes por parroquia.

theta[j,k] = P(votar/bastinerse del bloque k en 2023 | bloque j en 2019).

Reutiliza el núcleo EM de `inferencia/ecologica.py`. Salidas en `...\\ei\\`:
  transicion_local_<dignidad>_2019_2023.csv
  transicion_local_<dignidad>_2019_2023_ic.csv
  heatmap_local_<dignidad>_2019_2023.png
  resumen_ei_local_2019_2023.json

Uso:  python -m inferencia.local [prefecto|alcalde]
"""

import os
import sys
import json

import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import familia
from inferencia.ecologica import em_transicion, _shares, ajustar
import datos.registro as registro
import estilo_plot as ep

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIN_SHARE = 1.5      # % mínimo (en algún año) para que una familia sea bloque propio
MAX_BLOQUES = 8


def _loc3_de4(s):
    p = s.astype(str).str.split("-")
    return p.str[0] + "-" + p.str[1] + "-" + p.str[3]


def _sufragantes(dignidad, anio):
    """Serie loc_id (3-part) -> sufragantes (personas que votaron)."""
    if anio == 2019:
        p = rd.ruta("mesas/parr_unidades_seccionales_2019.csv.gz")
        if not os.path.exists(p):
            return pd.Series(dtype=float)
        u = pd.read_csv(p, dtype=str)
        u = u[u["dignidad"] == dignidad].copy()
        u["loc3"] = _loc3_de4(u["loc_id"])
        u["sufragantes"] = pd.to_numeric(u["sufragantes"], errors="coerce").fillna(0)
        return u.groupby("loc3")["sufragantes"].sum()
    # 2023: sumar votos emitidos de las mesas (loc_id 6-part) por parroquia
    p = rd.ruta(f"mesas/mesas_{dignidad}_2023.csv.gz")
    if not os.path.exists(p):
        return pd.Series(dtype=float)
    m = pd.read_csv(p, dtype=str)
    m["loc3"] = _loc3_de4(m["loc_id"])     # sirve: toma partes 0,1,3
    m["votos_emitidos"] = pd.to_numeric(m["votos_emitidos"], errors="coerce").fillna(0)
    return m.groupby("loc3")["votos_emitidos"].sum()


def _nov(anio):
    """Serie loc_id -> No voto = electores − sufragantes (≥0), si hay padrón."""
    try:
        E = registro.electores_parroquia(anio)
    except Exception:
        return None
    S = _sufragantes("prefecto", anio)
    if S.empty:
        return None
    loc = E.index.intersection(S.index)
    return (E.reindex(loc) - S.reindex(loc)).clip(lower=0)


def _bloques(dignidad):
    """Familias con participación ≥ MIN_SHARE en 2019 o 2023 (hasta MAX_BLOQUES)."""
    tot = {}
    for anio in (2019, 2023):
        v = pd.read_csv(rd.ruta(f"mesas/parr_partido_{dignidad}_{anio}.csv.gz"), dtype=str)
        v["votos"] = v["votos"].astype(int)
        v["familia"] = v["partido"].map(familia)
        tot[anio] = v.groupby("familia")["votos"].sum()
    T = pd.DataFrame(tot).fillna(0)
    T["max"] = T.max(axis=1)
    share = 100 * T["max"] / T["max"].sum()
    fams = share[share >= MIN_SHARE].sort_values(ascending=False).index.tolist()
    return fams[:MAX_BLOQUES]


def cargar(dignidad, anio, bloques, con_nov=True):
    v = pd.read_csv(rd.ruta(f"mesas/parr_partido_{dignidad}_{anio}.csv.gz"), dtype=str)
    v["votos"] = v["votos"].astype(int)
    v["familia"] = v["partido"].map(familia)
    v["familia"] = v["familia"].where(v["familia"].isin(bloques), "RESTO")
    t = v.pivot_table(index="loc_id", columns="familia", values="votos",
                      aggfunc="sum", fill_value=0)
    cols = bloques + ["RESTO"] + (["NOV"] if con_nov else [])
    if con_nov:
        nv = _nov(anio)
        t["NOV"] = nv.reindex(t.index).fillna(0) if nv is not None else 0.0
    return t.reindex(columns=cols, fill_value=0)


def heatmap(theta, origen, destino, titulo, path):
    fig, ax = plt.subplots(figsize=(1.1 + 0.9 * len(destino), 1 + 0.6 * len(origen)))
    im = ax.imshow(100 * theta, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(destino))); ax.set_xticklabels(destino, rotation=30, ha="right")
    ax.set_yticks(range(len(origen))); ax.set_yticklabels(origen)
    ax.set_xlabel("Destino (2023)"); ax.set_ylabel("Origen (2019)")
    for i in range(len(origen)):
        for j in range(len(destino)):
            ax.text(j, i, f"{100*theta[i,j]:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title(titulo)
    ep.mpl(fig, "Inferencia ecológica (EM) por parroquia; migración de votos entre familias.")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def analizar(dignidad):
    bloques = _bloques(dignidad)
    con_nov = _nov(2019) is not None and _nov(2023) is not None
    origen = bloques + ["RESTO"] + (["NOV"] if con_nov else [])
    destino = origen[:]
    t19 = cargar(dignidad, 2019, bloques, con_nov)
    t23 = cargar(dignidad, 2023, bloques, con_nov)
    locs = sorted(set(t19.index) & set(t23.index))
    X = t19.reindex(index=locs, columns=origen).to_numpy(float)
    Y = t23.reindex(index=locs, columns=destino).to_numpy(float)
    print(f"[EI {dignidad}] parroquias comunes={len(locs)} | bloques={origen} "
          f"| NOV={'sí' if con_nov else 'no'}")
    theta, lo, hi, nval = ajustar(X, Y)

    out = rd.ruta_dir("ei")
    pd.DataFrame(100 * theta, index=origen, columns=destino).round(1).to_csv(
        os.path.join(out, f"transicion_local_{dignidad}_2019_2023.csv"))
    ic = pd.DataFrame(
        [{"origen": origen[i], "destino": destino[j],
          "media": round(100 * theta[i, j], 1), "p5": round(100 * lo[i, j], 1),
          "p95": round(100 * hi[i, j], 1)}
         for i in range(len(origen)) for j in range(len(destino))])
    ic.to_csv(os.path.join(out, f"transicion_local_{dignidad}_2019_2023_ic.csv"),
              index=False)
    heatmap(theta, origen, destino,
            f"Transición de votos {dignidad} 2019 → 2023 (%)",
            os.path.join(out, f"heatmap_local_{dignidad}_2019_2023.png"))
    print(pd.DataFrame(100 * theta, index=origen, columns=destino).round(1).to_string())
    return {"dignidad": dignidad, "parroquias": int(nval), "bloques": origen,
            "con_nov": con_nov, "theta_pct": (100 * theta).round(1).tolist()}


def main():
    digs = [sys.argv[1]] if len(sys.argv) > 1 else ["prefecto", "alcalde"]
    res = [analizar(d) for d in digs]
    out = rd.ruta_dir("ei")
    with open(os.path.join(out, "resumen_ei_local_2019_2023.json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"[OK] -> {out}")


if __name__ == "__main__":
    main()

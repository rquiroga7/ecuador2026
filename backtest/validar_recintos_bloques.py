# -*- coding: utf-8 -*-
"""
backtest/validar_recintos_bloques.py — Validación de **recintos** y de la
clasificación ideológica por **3 bloques**, comparando 2021 (presidencial, nivel
junta con zona ⇒ recinto) contra 2023 (seccionales prefecto, nivel mesa ⇒ recinto).

Idea (control de calidad): los tres bloques (correísta / anticorreísta / diferentes)
deberían tener **shares altamente correlacionados por recinto** entre 2021 y 2023
(si el mapeo de bloques y la asignación de IDs de recinto son correctos). Una
correlación baja delata un error en: (a) la definición de bloques, o (b) cómo se
construye/empareja el ID de recinto (prov-cant-parroquia-zona).

Bloques 2021: los de `unificaideologias.py`, por `cod_org_pol` (normalizado):
  correísta: {1005, 35} · anticorreísta: {21006,3,4,8,10,16,17051,19,20,23,25,33}
  diferentes: resto (MUPP=18, ID=12, …)
Bloques 2023: por FAMILIA (datos.familias) replicando el mismo criterio:
  correísta: RC · diferentes: MUPP, ID · anticorreísta: resto de organizaciones.

Salidas (D:\\ecuador2026_data\\backtest\\):
  recintos_bloques_2021.csv · recintos_bloques_2023.csv · correlacion_recintos_bloques.csv

Uso:
    python -m backtest.validar_recintos_bloques
"""

import os
import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import familia

BLOQUES = ["correista", "anticorreista", "diferentes"]

# --- 2021 (presidencial): bloques del experto por cod_org_pol (sin ceros) ---
CORREISTA_ORG = {1005, 35}
ANTI_ORG = {21006, 3, 4, 8, 10, 16, 17051, 19, 20, 23, 25, 33}


def _bloque_org(org):
    if org in CORREISTA_ORG:
        return "correista"
    if org in ANTI_ORG:
        return "anticorreista"
    return "diferentes"


# --- 2023 (seccionales prefecto): mismo criterio por FAMILIA ---
CORREISTA_FAM = {"RC"}
DIFERENTES_FAM = {"MUPP", "ID"}


def _bloque_fam(fam):
    if fam in CORREISTA_FAM:
        return "correista"
    if fam in DIFERENTES_FAM:
        return "diferentes"
    return "anticorreista"


def _z(s, n):
    s = pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)
    return s.str.zfill(n)


def recintos_2021():
    g = pd.read_csv(rd.ruta("raw/gaona_2021_presidencia_junta.csv"), dtype=str,
                    usecols=["cod_prov", "cod_cant", "parroquia", "recinto",
                             "cod_org_pol", "votos"])
    g["votos"] = pd.to_numeric(g["votos"], errors="coerce").fillna(0).astype(int)
    g["rec"] = (_z(g["cod_prov"], 2) + "-" + _z(g["cod_cant"], 3) + "-"
                + _z(g["parroquia"], 4) + "-" + _z(g["recinto"], 2))
    g["bloque"] = pd.to_numeric(g["cod_org_pol"], errors="coerce").apply(_bloque_org)
    t = g.pivot_table(index="rec", columns="bloque", values="votos",
                      aggfunc="sum", fill_value=0)
    t = t.reindex(columns=BLOQUES, fill_value=0)
    t["total"] = t.sum(1)
    return _shares(t)


def recintos_2023(dig="prefecto"):
    v = pd.read_csv(rd.ruta(f"mesas/votos_{dig}_2023.csv.gz"), dtype=str,
                    usecols=["loc_id", "lista", "votos"])
    v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
    sp = v["loc_id"].str.split("-")
    v["rec"] = sp.str[0] + "-" + sp.str[1] + "-" + sp.str[3] + "-" + sp.str[4]
    v["bloque"] = v["lista"].map(lambda x: _bloque_fam(familia(x)))
    t = v.pivot_table(index="rec", columns="bloque", values="votos",
                      aggfunc="sum", fill_value=0)
    t = t.reindex(columns=BLOQUES, fill_value=0)
    t["total"] = t.sum(1)
    return _shares(t)


def _shares(t):
    tot = t[BLOQUES].sum(1).replace(0, np.nan)
    for b in BLOQUES:
        t[b + "_sh"] = 100 * t[b] / tot
    return t


def _r(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 5 or a[m].std() == 0 or b[m].std() == 0:
        return np.nan, int(m.sum())
    return float(np.corrcoef(a[m], b[m])[0, 1]), int(m.sum())


def _wcorr(x, y, w):
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    if len(x) < 5 or w.sum() <= 0:
        return np.nan
    mx = np.average(x, weights=w)
    my = np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx = np.average((x - mx) ** 2, weights=w)
    vy = np.average((y - my) ** 2, weights=w)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else np.nan


def main():
    t21 = recintos_2021()
    t23 = recintos_2023("prefecto")
    print(f"recintos 2021={len(t21)} | 2023={len(t23)} | "
          f"comunes={len(t21.index.intersection(t23.index))} | "
          f"solo2021={len(t21.index.difference(t23.index))} | "
          f"solo2023={len(t23.index.difference(t21.index))}")

    comunes = t21.index.intersection(t23.index)
    A, B = t21.loc[comunes], t23.loc[comunes]
    w = A["total"].clip(lower=1)

    filas = []
    for b in BLOQUES:
        r, n = _r(A[b + "_sh"], B[b + "_sh"])
        # correlación ponderada por tamaño (min de votos de los dos años)
        ww = np.minimum(A["total"], B["total"]).clip(lower=1)
        m = A[b + "_sh"].notna() & B[b + "_sh"].notna()
        rw = _wcorr(A[b + "_sh"][m], B[b + "_sh"][m], ww[m]) if m.sum() > 5 else np.nan
        filas.append({"bloque": b, "r_pearson": round(r, 3), "r_ponderada": round(rw, 3),
                      "n": n,
                      "sh2021": round(float(A[b + "_sh"].mean()), 2),
                      "sh2023": round(float(B[b + "_sh"].mean()), 2)})
    res = pd.DataFrame(filas)
    print("\nCorrelación por bloque (share por recinto, 2021 vs 2023):")
    print(res.to_string(index=False))

    out = rd.ruta_dir("backtest")
    t21.to_csv(os.path.join(out, "recintos_bloques_2021.csv"))
    t23.to_csv(os.path.join(out, "recintos_bloques_2023.csv"))
    res.to_csv(os.path.join(out, "correlacion_recintos_bloques.csv"), index=False)
    print(f"\n[OK] -> {out}")
    return res


if __name__ == "__main__":
    main()

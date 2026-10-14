# -*- coding: utf-8 -*-
"""
forense/ranking.py — Ranking priorizado de MESAS a fiscalizar (combina señales).

Toma las señales por mesa de `forense/juntas.py` (z de share del líder, parroquia,
dígitos 0/5, emitidos y caída de blanco/nulo), las convierte en **p-valores** de una
cola, las combina con el método de **Simes** y controla la tasa de falsos
descubrimientos con **Benjamini–Hochberg** (FDR). El resultado es un ranking con
niveles de prioridad para el equipo de fiscalización.

Advertencia (Mebane): el score **prioriza**, no prueba fraude. Digit tests y
multimodalidad tienen falsos positivos (voto estratégico, coaliciones). Combinar con
denuncias y observación. Ver `docs/FORENSE.md`.

Uso:
    python -m forense.ranking prefecto
    python -m forense.ranking alcalde --top 40
"""

import os
import sys
import csv
import math
import argparse

import numpy as np
import pandas as pd

import rutas_datos as rd
from forense import juntas

# señales de una cola (mayores = más anómalo). Se excluye la firma según la dirección.
SENALES = ["z_share", "z_parr", "z_c05", "z_emit", "z_bn", "tope"]
DIRECCION = {"z_share": +1, "z_parr": +1, "z_c05": +1, "z_emit": +1,
             "z_bn": -1, "tope": +1}


def _phi(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z, float) / math.sqrt(2.0)))


def p_valores(df):
    """p de una cola por señal, orientadas por DIRECCION (z alto => p chico)."""
    P = pd.DataFrame(index=df.index)
    for s in SENALES:
        z = pd.to_numeric(df[s], errors="coerce").values * DIRECCION[s]
        with np.errstate(invalid="ignore"):
            P[s] = 1.0 - _phi(z)
    return P


def simes(p_fila):
    """p combinado de Simes sobre los k p-valores (ignora NaN)."""
    p = np.sort(p_fila[np.isfinite(p_fila)])
    k = len(p)
    if k == 0:
        return np.nan
    return float(np.min(k * p / np.arange(1, k + 1)))


def benjamini_hochberg(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    fin = np.isfinite(p)
    idx = np.where(fin)[0]
    if len(idx) == 0:
        return q
    orden = idx[np.argsort(p[idx])]
    m = len(orden)
    prev = 1.0
    for rank, i in enumerate(orden[::-1], start=1):
        val = p[i] * m / (m - rank + 1)
        prev = min(prev, val)
        q[i] = prev
    return np.clip(q, 0, 1)


def prioridad(q, score):
    if q is None or not np.isfinite(q):
        return "Baja"
    if q < 0.01 and score >= 4:
        return "Alta"
    if q < 0.05:
        return "Media"
    return "Baja"


def cargar_score(dig="prefecto", anio=2023):
    p = rd.ruta(f"forense/score_mesas_{dig}_{anio}.csv.gz")
    if os.path.exists(p):
        return pd.read_csv(p, dtype=str)
    return juntas.score(juntas.cargar(dig, anio))


def ranking(dig="prefecto", anio=2023, min_emitidos=20):
    df = cargar_score(dig, anio)
    for c in SENALES + ["emitidos", "share_lider", "bn_rate", "frac_c05", "score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # mesas muy chicas (pocos votantes) distorsionan el z del share y no son accionables
    if min_emitidos and "emitidos" in df.columns:
        df = df[df["emitidos"] >= min_emitidos].copy()
    P = p_valores(df)
    df["p_simes"] = P.apply(simes, axis=1)
    df["q_bh"] = benjamini_hochberg(df["p_simes"].values)
    df["rank"] = df["score"].rank(ascending=False, method="first").astype("Int64")
    df["prioridad"] = [prioridad(row.q_bh, row.score) for row in df.itertuples()]
    # índice de anomalía combinado: score y significancia
    df["indice"] = (np.log1p(np.clip(df["score"], 0, None)) *
                    (1 + np.clip(-np.log10(df["q_bh"].clip(lower=1e-12)), 0, 8)))
    df = df.sort_values("indice", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def _resumen(df):
    return {
        "mesas": int(len(df)),
        "prioridad_alta": int((df["prioridad"] == "Alta").sum()),
        "prioridad_media": int((df["prioridad"] == "Media").sum()),
        "q<0.05": int((df["q_bh"] < 0.05).sum()),
        "q<0.01": int((df["q_bh"] < 0.01).sum()),
        "score>5": int((df["score"] > 5).sum()),
    }


def main():
    ap = argparse.ArgumentParser(description="Ranking forense de mesas a fiscalizar.")
    ap.add_argument("dignidad", nargs="?", default="prefecto")
    ap.add_argument("--anio", type=int, default=2023)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-emitidos", type=int, default=20,
                    help="descarta mesas con menos votantes (ruido)")
    args = ap.parse_args()

    df = ranking(args.dignidad, args.anio, min_emitidos=args.min_emitidos)
    res = _resumen(df)
    print(f"[{args.dignidad}] " + " | ".join(f"{k}={v}" for k, v in res.items()))
    cols = ["rank", "mesa_id", "canton", "emitidos", "share_lider", "score",
            "p_simes", "q_bh", "prioridad"]
    cols = [c for c in cols if c in df.columns]
    print(df.head(args.top)[cols].to_string(index=False))

    out = rd.ruta_dir("forense")
    p = os.path.join(out, f"ranking_mesas_{args.dignidad}_{args.anio}.csv.gz")
    df.to_csv(p, index=False, compression="gzip")
    desglose = (df.groupby("prov")["prioridad"].apply(
        lambda s: int((s == "Alta").sum())).sort_values(ascending=False))
    pd_ = os.path.join(out, f"ranking_prioridad_alta_por_prov_{args.dignidad}.csv")
    desglose.rename("prioridad_alta").to_csv(pd_, header=True)
    print(f"[OK] -> {p}\n[OK] prioridad alta por provincia -> {pd_}")
    return df


if __name__ == "__main__":
    main()

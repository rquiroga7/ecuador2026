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
import json
import math
import argparse

import numpy as np
import pandas as pd

import rutas_datos as rd
from forense import juntas

# señales de una cola (mayores = más anómalo). Se excluye la firma según la dirección.
# El share usa la versión **calibrada** (exceso fuera del fence del estrato).
SENALES = ["z_share_cal", "z_parr_cal", "z_c05", "z_part", "z_bn", "tope"]
DIRECCION = {"z_share_cal": +1, "z_parr_cal": +1, "z_c05": +1, "z_part": +1,
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


# Etiqueta legible de cada señal (la "sospecha gatillada").
SENAL_TXT = {
    "share_canton": "Share del líder muy distinto al del cantón",
    "share_parroquia": "Share del líder muy distinto al de la parroquia",
    "digitos_0_5": "Exceso de conteos terminados en 0/5 (posible redondeo)",
    "participacion_alta": "Participación muy por encima del cantón (posible ballot stuffing)",
    "blanco_nulo_bajo": "Blancos/nulos anormalmente bajos (posible relleno de válidos)",
    "sobre_tope": "Emitidos por encima del máximo razonable por junta",
}


def _senales_de(row, thr=3.0, mat_share=0.15, mat_part=15.0):
    """Señales gatilladas en la mesa (|z|≥thr o tope>0).

    Para el share se exige además **materialidad** (una diferencia de al menos
    `mat_share`, p. ej. 15 puntos) respecto de la mediana del cantón/parroquia, y para
    la participación al menos `mat_part` puntos por encima de la mediana del cantón (o
    >100%): una desviación estadísticamente significativa pero trivial no gatilla.
    """
    tags = []
    for col, med_col, key in (("z_share_cal", "share_canton", "share_canton"),
                              ("z_parr_cal", "share_parr", "share_parroquia")):
        v = getattr(row, col, None)
        if v is not None and np.isfinite(v) and v > 0:
            med = getattr(row, med_col, None)
            if med is None or not np.isfinite(med) or \
                    abs(getattr(row, "share_lider", 0.0) - med) >= mat_share:
                tags.append(key)
    v = getattr(row, "z_c05", None)
    if v is not None and np.isfinite(v) and v >= thr:
        tags.append("digitos_0_5")
    v = getattr(row, "z_part", None)
    p = getattr(row, "participacion", None)
    pc = getattr(row, "participacion_canton", None)
    if v is not None and np.isfinite(v) and v >= thr:
        material = (p is not None and np.isfinite(p) and p > 100) or \
                   (p is not None and np.isfinite(p) and pc is not None
                    and np.isfinite(pc) and (p - pc) >= mat_part)
        if material:
            tags.append("participacion_alta")
    v = getattr(row, "z_bn", None)
    if v is not None and np.isfinite(v) and v <= -thr:
        tags.append("blanco_nulo_bajo")
    v = getattr(row, "tope", 0)
    if v is not None and np.isfinite(v) and v > 0:
        tags.append("sobre_tope")
    return tags or ["score_compuesto"]


def _nombres():
    """Cod -> nombre de provincia/cantón/parroquia (catálogos CNE)."""
    out = {"prov": {}, "canton": {}, "parr": {}}
    p = rd.ruta("catalogo/provincia.csv.gz")
    if os.path.exists(p):
        d = pd.read_csv(p, dtype=str)
        out["prov"] = dict(zip(d["COD_PROVINCIA"].str.zfill(2),
                              d["NOM_PROVINCIA"].str.strip()))
    p = rd.ruta("catalogo/canton.csv.gz")
    if os.path.exists(p):
        d = pd.read_csv(p, dtype=str)
        out["canton"] = dict(zip(d["COD_CANTON"].str.zfill(3),
                                 d["NOM_CANTON"].str.strip()))
    p = rd.ruta("catalogo/parroquia.csv.gz")
    if os.path.exists(p):
        d = pd.read_csv(p, dtype=str)
        k = d["COD_CANTON"].str.zfill(3) + "|" + d["COD_PARROQUIA"].str.zfill(4)
        out["parr"] = dict(zip(k, d["NOM_PARROQUIA"].str.strip()))
    return out


def cargar_score(dig="prefecto", anio=2023):
    p = rd.ruta(f"forense/score_mesas_{dig}_{anio}.csv.gz")
    if os.path.exists(p):
        return pd.read_csv(p, dtype=str)
    return juntas.score(juntas.cargar(dig, anio), anio=anio)


def _wide_desde_snapshot(snap):
    """Convierte una instantánea (tidy por mesa) al formato de `juntas.score`:
    mesa × bloque + emitidos/b/n. Permite correr el forense sobre el escrutinio vivo."""
    from modelo.bloques import bloque_principal
    v = snap["votos"].copy()
    if "bloque" not in v.columns:
        v["bloque"] = v["lista"].map(bloque_principal) if "lista" in v.columns else "ZZZ"
    wide = v.pivot_table(index=["mesa_id", "loc_id"], columns="bloque", values="votos",
                         fill_value=0, aggfunc="sum").reset_index()
    m = snap["totales"][["mesa_id", "votos_emitidos", "votos_b", "votos_n"]]
    m = m.drop_duplicates("mesa_id")
    wide = wide.merge(m, on="mesa_id", how="left")
    return wide.rename(columns={"votos_emitidos": "emitidos", "votos_b": "b",
                                "votos_n": "n"})


def ranking(dig="prefecto", anio=2023, min_emitidos=20, wide=None):
    df = juntas.score(wide, anio=anio) if wide is not None else cargar_score(dig, anio)
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
    df["sospechas"] = [_senales_de(r) for r in df.itertuples()]
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


def _num(v, nd=3):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if np.isfinite(f) else None


def exportar_web(digs=("prefecto", "alcalde"), anio=2023, top=500,
                 min_emitidos=20, destino=None, snaps=None):
    """Escribe `web/forense.json` con el ranking de mesas sospechosas y su sospecha.

    Si se pasa `snaps` ({dignidad: instantánea}), el forense corre sobre ese
    escrutinio (parcial) en vez de las bases 2023 en disco.
    """
    nm = _nombres()
    por = {}
    for dig in digs:
        wide = None
        if snaps is not None and dig in snaps:
            try:
                wide = _wide_desde_snapshot(snaps[dig])
            except Exception as e:
                print(f"[!] forense {dig}: no pude armar la matriz ({e})")
        df = ranking(dig, anio, min_emitidos=min_emitidos, wide=wide)
        items = []
        for r in df.head(top).itertuples():
            parts = str(r.loc_id).split("-")
            cod_prov = parts[0] if len(parts) > 0 else ""
            cod_cant = parts[1] if len(parts) > 1 else ""
            cod_parr = parts[3] if len(parts) > 3 else ""
            margen = getattr(r, "margen_mesa", np.nan)
            votos_fam = getattr(r, "votos_familia", None)
            if votos_fam is not None and not isinstance(votos_fam, dict):
                votos_fam = None
            n_est = getattr(r, "electores_est", None)
            items.append({
                "rank": int(r.rank),
                "mesa_id": str(r.mesa_id),
                "loc_id": str(r.loc_id),
                "provincia": nm["prov"].get(cod_prov, cod_prov),
                "canton": nm["canton"].get(cod_cant, cod_cant),
                "parroquia": nm["parr"].get(f"{cod_cant}|{cod_parr}", ""),
                "emitidos": int(r.emitidos),
                "blancos": int(getattr(r, "b", 0) or 0),
                "nulos": int(getattr(r, "n", 0) or 0),
                "electores_est": (None if n_est is None or pd.isna(n_est)
                                  else int(n_est)),
                "participacion": _num(getattr(r, "participacion", None), 1),
                "participacion_parroquia": _num(
                    getattr(r, "participacion_parroquia", None), 1),
                "share_lider": round(float(r.share_lider), 3),
                "ganador_mesa": getattr(r, "ganador_mesa", None),
                "segundo_mesa": getattr(r, "segundo_mesa", None),
                "margen_mesa": (round(float(margen), 1) if margen is not None
                                and np.isfinite(margen) else None),
                "votos_familia": votos_fam,
                "score": round(float(r.score), 2),
                "q": float(f"{r.q_bh:.2e}") if np.isfinite(r.q_bh) else None,
                "prioridad": r.prioridad,
                "sospechas": list(r.sospechas),
                "medidas": {
                    "share_lider": _num(getattr(r, "share_lider", None), 3),
                    "share_canton": _num(getattr(r, "share_canton", None), 3),
                    "share_parr": _num(getattr(r, "share_parr", None), 3),
                    "share_lo_canton": _num(getattr(r, "share_lo_canton", None), 3),
                    "share_hi_canton": _num(getattr(r, "share_hi_canton", None), 3),
                    "share_lo_parr": _num(getattr(r, "share_lo_parr", None), 3),
                    "share_hi_parr": _num(getattr(r, "share_hi_parr", None), 3),
                    "participacion": _num(getattr(r, "participacion", None), 1),
                    "participacion_canton": _num(
                        getattr(r, "participacion_canton", None), 1),
                    "bn_rate": _num(getattr(r, "bn_rate", None), 3),
                    "bn_canton": _num(getattr(r, "bn_canton", None), 3),
                    "frac_c05": _num(getattr(r, "frac_c05", None), 3),
                    "c05_canton": _num(getattr(r, "c05_canton", None), 3),
                    "tope": 400,
                },
                "detalle": {k: (None if getattr(r, k, None) is None
                                or not np.isfinite(getattr(r, k, np.nan)) else
                                round(float(getattr(r, k)), 2))
                            for k in ["z_share", "z_parr", "z_c05", "z_part", "z_bn"]},
            })
        por[dig] = {"items": items, "resumen": _resumen(df)}
    doc = {"generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
           "anio": anio, "senal_txt": SENAL_TXT, "por_dignidad": por}
    p = destino or os.path.join(rd.REPO, "web", "forense.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[OK] {p} | " + " | ".join(
        f"{d}: {len(por[d]['items'])} mesas (alta={por[d]['resumen']['prioridad_alta']})"
        for d in por))
    return doc


def main():
    ap = argparse.ArgumentParser(description="Ranking forense de mesas a fiscalizar.")
    ap.add_argument("dignidad", nargs="?", default="prefecto")
    ap.add_argument("--anio", type=int, default=2023)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-emitidos", type=int, default=20,
                    help="descarta mesas con menos votantes (ruido)")
    ap.add_argument("--web", action="store_true",
                    help="exporta web/forense.json (prefecto y alcalde)")
    args = ap.parse_args()

    if args.web:
        exportar_web(("prefecto", "alcalde"), args.anio, top=max(args.top, 500),
                     min_emitidos=args.min_emitidos)
        return

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

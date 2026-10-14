# -*- coding: utf-8 -*-
"""
forense/juntas.py — Score de anomalía por MESA (junta) para priorizar fiscalización.

Señales (todas a nivel de mesa):
  1. `z_share`  — share del partido líder (provincial) vs mediana/MAD de su **cantón**.
  2. `z_parr`   — ídem respecto de su **parroquia**.
  3. `z_c05`    — fracción de conteos que terminan en 0/5 vs el cantón (redondeo).
  4. `z_emit`   — **emitidos** (votantes) vs el cantón → **ballot stuffing** infla votos
                  y por tanto los emitidos de la mesa.
  5. `z_bn`     — tasa (blancos+nulos)/emitidos vs el cantón → el stuffing baja la tasa
                  (se agregan votos válidos pero no blancos/nulos).
  6. `tope`     — emitidos por encima del máximo legal razonable por junta (flag duro).

Score = máximo de los |z| de señales independientes (+ tope). Ver docs/FORENSE.md.
"""

import os
import numpy as np
import pandas as pd

import rutas_datos as rd

TOPE_JUNTA = 400  # máx. razonable de electores/votantes por junta en Ecuador


def cargar(dig="prefecto", anio=2023):
    b = pd.read_csv(rd.ruta(f"mesas/bloques_{dig}_{anio}.csv.gz"), dtype=str)
    b["votos"] = b["votos"].astype(int)
    wide = b.pivot_table(index=["mesa_id", "loc_id"], columns="bloque",
                         values="votos", fill_value=0, aggfunc="sum").reset_index()
    m = pd.read_csv(rd.ruta(f"mesas/mesas_{dig}_{anio}.csv.gz"), dtype=str)
    m = m[["mesa_id", "votos_emitidos", "votos_b", "votos_n"]].drop_duplicates("mesa_id")
    for c in ["votos_emitidos", "votos_b", "votos_n"]:
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0)
    wide = wide.merge(m, on="mesa_id", how="left")
    wide = wide.rename(columns={"votos_emitidos": "emitidos", "votos_b": "b",
                                "votos_n": "n"})
    return wide


def _mad(x):
    m = np.nanmedian(x)
    return 1.4826 * np.nanmedian(np.abs(x - m))


def _z(x, g, floor=1e-3):
    d = pd.DataFrame({"x": x, "g": g})
    med = d.groupby("g")["x"].transform("median")
    mad = np.maximum(d.groupby("g")["x"].transform(_mad), floor)
    return ((d["x"] - med) / mad).values


def preparar(wide):
    cols_all = [c for c in wide.columns if c not in
                ("mesa_id", "loc_id", "emitidos", "b", "n")]
    val = (pd.to_numeric(wide["emitidos"], errors="coerce").fillna(0) > 0) & \
          (wide[cols_all].astype(float).sum(1) > 0)
    wide = wide[val].reset_index(drop=True)
    meta = wide[["mesa_id", "loc_id"]].copy()
    sp = wide["loc_id"].str.split("-", expand=True)
    meta["prov"] = sp[0]
    meta["canton"] = sp[0] + "-" + sp[1]
    meta["parr"] = wide["loc_id"]
    cols = cols_all
    M = wide[cols].astype(float)
    tot = wide[["emitidos", "b", "n"]].astype(float).copy()
    return meta, M, tot, cols


def score_matriz(meta, M, tot, cols):
    prov = meta["prov"].values
    tot_v = M.groupby(prov).sum()
    lider_prov = {u: cols[int(np.argmax(tot_v.loc[u].values))] for u in tot_v.index}
    validos = M.sum(1).values
    lider = np.array([lider_prov[u] for u in prov])
    A = M.values
    share = np.array([A[i, cols.index(lider[i])] / validos[i] if validos[i] > 0 else 0
                      for i in range(len(M))])

    frac_c05 = np.full(len(M), np.nan)
    for i in range(len(M)):
        vals = A[i][A[i] > 0]
        if len(vals) >= 5:
            frac_c05[i] = np.isin(vals.astype(int) % 10, [0, 5]).mean()

    emitidos = tot["emitidos"].values
    bn = np.where(emitidos > 0, (tot["b"] + tot["n"]).values / emitidos, np.nan)

    out = meta.copy()
    out["emitidos"] = emitidos
    out["share_lider"] = share
    out["frac_c05"] = frac_c05
    out["bn_rate"] = bn
    out["z_share"] = _z(share, meta["canton"].values, 0.01)
    out["z_parr"] = _z(share, meta["parr"].values, 0.02)
    out["z_c05"] = _z(frac_c05, meta["canton"].values, 0.05)
    out["z_emit"] = _z(np.log1p(emitidos), meta["canton"].values, 0.05)
    out["z_bn"] = _z(bn, meta["canton"].values, 0.02)
    out["tope"] = np.clip(emitidos - TOPE_JUNTA, 0, None) / 50.0   # flag blando
    # señales de un solo lado: emitidos altos, bn_rate bajo, c05 alto; share bidireccional
    out["score"] = np.nanmax(np.vstack([
        np.abs(out["z_share"]), np.abs(out["z_parr"]),
        np.clip(out["z_c05"], 0, None),
        np.clip(out["z_emit"], 0, None),
        np.clip(-out["z_bn"], 0, None),
        out["tope"]]), axis=0)
    return out.sort_values("score", ascending=False)


def score(wide):
    meta, M, tot, cols = preparar(wide)
    return score_matriz(meta, M, tot, cols)


def main():
    import sys
    dig = sys.argv[1] if len(sys.argv) > 1 else "prefecto"
    sc = score(cargar(dig, 2023))
    print(f"[{dig}] mesas={len(sc)} | score>5: {(sc['score']>5).sum()} "
          f"| emitidos>{TOPE_JUNTA}: {(sc['emitidos']>TOPE_JUNTA).sum()}")
    print(sc.head(10)[["mesa_id", "prov", "emitidos", "bn_rate", "z_emit", "z_bn",
                       "score"]].to_string(index=False))
    out = rd.ruta_dir("forense")
    sc.to_csv(os.path.join(out, f"score_mesas_{dig}_2023.csv.gz"), index=False,
              compression="gzip")
    print(f"[OK] -> {out}")


if __name__ == "__main__":
    main()

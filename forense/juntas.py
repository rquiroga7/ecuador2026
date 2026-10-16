# -*- coding: utf-8 -*-
"""
forense/juntas.py — Score de anomalía por MESA (junta) para priorizar fiscalización.

Señales (todas a nivel de mesa):
  1. `z_share`  — share del partido líder (provincial) vs mediana/MAD de su **cantón**.
  2. `z_parr`   — ídem respecto de su **parroquia**.
  3. `z_c05`    — fracción de conteos que terminan en 0/5 vs el cantón (redondeo).
  4. `z_part`   — **participación** (emitidos / electores estimados) vs el cantón →
                  **ballot stuffing** eleva la participación por encima de lo normal.
                  Si no hay padrón (p. ej. simulación sin registro), cae a `z_emit`.
  5. `z_bn`     — tasa (blancos+nulos)/emitidos vs el cantón → el stuffing baja la tasa
                  (se agregan votos válidos pero no blancos/nulos).
  6. `tope`     — emitidos por encima del máximo legal razonable por junta (flag duro).

Score = máximo de los |z| de señales independientes (+ tope). Ver docs/FORENSE.md.
"""

import os
import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import familia as _familia

TOPE_JUNTA = 400  # máx. razonable de electores/votantes por junta en Ecuador
# Fence robusto para el share: "muy distinto" = fuera de mediana ± K_FENCE·IQR del
# estrato (IQR = heterogeneidad observada del cantón/parroquia). Calibrado sobre 2023
# para que un z≈4.87 (≈3.6·IQR) NO gatille; marca ~0.3% de las mesas (antes 2.6%).
K_FENCE = 4.0


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


def _med(x, g):
    return pd.DataFrame({"x": x, "g": g}).groupby("g")["x"].transform("median").values


def _fence(x, g, k, floor):
    """Fence robusto `[Q1 − k·IQR, Q3 + k·IQR]` del estrato (calibrado a su
    heterogeneidad). Devuelve (lo, hi)."""
    d = pd.DataFrame({"x": x, "g": g})
    q1 = d.groupby("g")["x"].transform(lambda s: s.quantile(0.25)).values
    q3 = d.groupby("g")["x"].transform(lambda s: s.quantile(0.75)).values
    iqr = np.maximum(q3 - q1, floor)
    return q1 - k * iqr, q3 + k * iqr


def _fuera(share, lo, hi, mad):
    """Exceso (en unidades MAD) del share fuera del fence; 0 si está dentro."""
    return np.where(share > hi, (share - hi) / mad,
                    np.where(share < lo, (lo - share) / mad, 0.0))


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
    meta["parr"] = sp[0] + "-" + sp[1] + "-" + sp[3]   # parroquia (sin zona/junta)
    meta["sexo"] = wide["mesa_id"].astype(str).str.rsplit("-", n=1).str[-1]
    cols = cols_all
    M = wide[cols].astype(float)
    tot = wide[["emitidos", "b", "n"]].astype(float).copy()
    return meta, M, tot, cols


def _electores_mesa(meta, anio):
    """Electores habilitados por mesa.

    Prefiere el **padrón por junta** del "Distributivo de recintos" del CNE
    (`datos.distributivo`); para las juntas sin match cae al padrón parroquial
    (abierto por sexo) repartido entre las mesas de esa parroquia y sexo.
    """
    from datos import distributivo, registro
    q = meta["mesa_id"].astype(str).str.split("-")
    jkey = (q.str[0] + "-" + q.str[1] + "-" + q.str[3] + "-" + q.str[4] + "-"
            + q.str[5] + "-" + q.str[6])
    try:
        ej = distributivo.electores_junta(anio)
    except Exception:
        ej = pd.Series(dtype=float)
    elect = (ej.reindex(jkey.values).values.astype(float) if len(ej)
             else np.full(len(meta), np.nan))
    falta = ~np.isfinite(elect)
    if falta.any():
        E = registro.electores_parroquia_sexo(anio)
        n = meta.groupby(["parr", "sexo"])["mesa_id"].transform("size")
        idx = pd.MultiIndex.from_arrays([meta["parr"].values, meta["sexo"].values])
        part = pd.Series(E.reindex(idx).values, index=meta.index) / n.values
        elect = np.where(falta, part.values, elect)
    return pd.Series(elect, index=meta.index)


def score_matriz(meta, M, tot, cols, electores=None):
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
    out["b"] = tot["b"].values
    out["n"] = tot["n"].values
    out["share_lider"] = share
    out["frac_c05"] = frac_c05
    out["bn_rate"] = bn
    # valores de comparación (medianas del estrato), para reportar la magnitud
    out["share_canton"] = _med(share, meta["canton"].values)
    out["share_parr"] = _med(share, meta["parr"].values)
    out["emitidos_canton"] = _med(emitidos, meta["canton"].values)
    out["bn_canton"] = _med(bn, meta["canton"].values)
    out["c05_canton"] = _med(frac_c05, meta["canton"].values)
    out["z_share"] = _z(share, meta["canton"].values, 0.01)
    out["z_parr"] = _z(share, meta["parr"].values, 0.02)
    out["z_c05"] = _z(frac_c05, meta["canton"].values, 0.05)
    out["z_emit"] = _z(np.log1p(emitidos), meta["canton"].values, 0.05)
    out["z_bn"] = _z(bn, meta["canton"].values, 0.02)
    # share "calibrado por heterogeneidad": solo cuenta el EXCESO fuera del fence
    # mediana ± K_FENCE·IQR del cantón/parroquia (un z alto pero esperable dado el IQR
    # del estrato no es sospechoso).
    med_c = _med(share, meta["canton"].values)
    med_p = _med(share, meta["parr"].values)
    mad_c = np.maximum(
        pd.DataFrame({"x": share, "g": meta["canton"].values}).groupby("g")["x"]
        .transform(_mad).values, 0.01)
    mad_p = np.maximum(
        pd.DataFrame({"x": share, "g": meta["parr"].values}).groupby("g")["x"]
        .transform(_mad).values, 0.02)
    lo_c, hi_c = _fence(share, meta["canton"].values, K_FENCE, 0.01)
    lo_p, hi_p = _fence(share, meta["parr"].values, K_FENCE, 0.02)
    out["share_lo_canton"], out["share_hi_canton"] = lo_c, hi_c
    out["share_lo_parr"], out["share_hi_parr"] = lo_p, hi_p
    out["z_share_cal"] = _fuera(share, lo_c, hi_c, mad_c)
    out["z_parr_cal"] = _fuera(share, lo_p, hi_p, mad_p)
    # Señal de ballot stuffing: **participación** por encima de lo normal (si hay
    # padrón), no los emitidos en crudo — una mesa puede ser grande legítimamente.
    if electores is not None:
        elect = np.asarray(electores, float)
        part = np.where(elect > 0, 100.0 * emitidos / elect, np.nan)
        out["electores_est"] = elect
        out["participacion"] = part
        out["participacion_canton"] = _med(part, meta["canton"].values)
        out["z_part"] = _z(part, meta["canton"].values, 0.5)
    else:
        out["electores_est"] = np.nan
        out["participacion"] = np.nan
        out["participacion_canton"] = np.nan
        out["z_part"] = out["z_emit"]           # sin padrón: cae a emitidos
    out["tope"] = np.clip(emitidos - TOPE_JUNTA, 0, None) / 50.0   # flag blando
    # señales de un solo lado: participación alta, bn_rate bajo, c05 alto; share (calibrado)
    base = np.nanmax(np.vstack([
        out["z_share_cal"], out["z_parr_cal"],
        np.clip(out["z_c05"], 0, None),
        np.clip(out["z_part"], 0, None),
        np.clip(-out["z_bn"], 0, None),
        out["tope"]]), axis=0)
    # Pondera por tamaño de la mesa: prioriza las mesas con muchos votantes y no tanto
    # las pequeñas, donde es más probable hallar outliers por ruido.
    prom = np.nanmean(emitidos) if len(emitidos) else 0.0
    out["score"] = base * (emitidos / prom if prom else 1.0)
    return out.sort_values("score", ascending=False)


def ganador_mesa(M, cols, top_n=8):
    """Ganador (por FAMILIA de partido) de cada mesa y su ventaja en puntos.

    Agrega los votos de los bloques que comparten familia (alianzas) y devuelve un
    DataFrame indexado como `M` con:
      * `ganador_mesa`  — sigla de la familia más votada (p. ej. "RC")
      * `segundo_mesa`  — sigla de la segunda familia
      * `margen_mesa`   — ventaja top1−top2 en puntos porcentuales de válidos
      * `votos_familia` — dict familia -> votos (las `top_n` primeras), para el detalle
    """
    fams = np.array([_familia(c) for c in cols])
    uniq = sorted(set(fams))
    F = M.T.groupby(fams).sum().T.reindex(columns=uniq, fill_value=0)
    Fv = F.values.astype(float)
    n = len(Fv)
    if n == 0:
        return pd.DataFrame(index=M.index)
    validosF = Fv.sum(1)
    i1 = Fv.argmax(1)
    top1 = Fv[np.arange(n), i1]
    Fm = Fv.copy()
    Fm[np.arange(n), i1] = -1.0
    i2 = Fm.argmax(1)
    top2 = Fm[np.arange(n), i2]
    margen = np.where(validosF > 0, 100.0 * (top1 - top2) / validosF, np.nan)
    gan = np.array([uniq[j] for j in i1])
    seg = np.array([uniq[j] for j in i2])
    votos_fam = []
    for i in range(n):
        pares = sorted(((uniq[j], int(round(Fv[i, j]))) for j in range(len(uniq))
                        if Fv[i, j] > 0), key=lambda t: -t[1])[:top_n]
        votos_fam.append(dict(pares))
    res = pd.DataFrame({"ganador_mesa": gan, "segundo_mesa": seg,
                        "margen_mesa": margen, "votos_familia": votos_fam},
                       index=M.index)
    # donde no hay válidos, no hay ganador
    res.loc[validosF <= 0, ["ganador_mesa", "segundo_mesa"]] = None
    return res


def score(wide, anio=2023):
    meta, M, tot, cols = preparar(wide)
    try:
        elect = _electores_mesa(meta, anio)
    except Exception as e:
        print(f"[i] sin padrón {anio}: participación no disponible ({e})")
        elect = None
    out = score_matriz(meta, M, tot, cols, electores=elect)
    # participación parroquial (padrón parroquial real, estimado por mesa)
    ep = out.groupby("parr")["electores_est"].transform("sum")
    out["participacion_parroquia"] = (100 * out.groupby("parr")["emitidos"].transform("sum")
                                      / ep.replace(0, np.nan)).round(1)
    gm = ganador_mesa(M, cols)
    out = out.join(gm)
    return out


def main():
    import sys
    dig = sys.argv[1] if len(sys.argv) > 1 else "prefecto"
    sc = score(cargar(dig, 2023), anio=2023)
    print(f"[{dig}] mesas={len(sc)} | score>5: {(sc['score']>5).sum()} "
          f"| emitidos>{TOPE_JUNTA}: {(sc['emitidos']>TOPE_JUNTA).sum()}")
    print(sc.head(10)[["mesa_id", "prov", "emitidos", "participacion",
                       "bn_rate", "z_part", "z_bn", "score"]].to_string(index=False))
    out = rd.ruta_dir("forense")
    sc.to_csv(os.path.join(out, f"score_mesas_{dig}_2023.csv.gz"), index=False,
              compression="gzip")
    print(f"[OK] -> {out}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
backtest/nacional.py — Comparación de métodos en la PRESIDENCIAL (parroquia).

Parámetros: referencia 2021, objetivo 2025 (ambos .sav del CNE, nivel parroquia).
Bloques = partidos mapeados por código interno de organización (OP); el resto = RESTO.
  RC: Arauz(2021) -> Luisa González(2025)
  MUPP: Yaku(2021) -> Iza(2025)
  CREO: Lasso(2021) -> Tabacchi(2025)
  ADN: NO existe en 2021 -> Noboa(2025)   <-- partido nuevo (difícil para swing)
  ID: Hervás(2021) -> (no corre 2025)

Métricas (nacionales): error de composición, error del margen top1-top2 y share del top.

Uso:  python -m backtest.nacional
"""

import os
import numpy as np
import pandas as pd

import rutas_datos as rd
from proyeccion import Proyector
from modelo import swing, v1_brasil
from backtest.bloques_lista import ordenes, UMBRALES

MAPA = {
    2021: {"1030": "RC", "1021": "CREO", "2": "MUPP", "42": "ID"},
    2025: {"1644": "RC", "500": "ADN", "7": "MUPP", "99": "CREO", "32": "PSC"},
}


def cargar(anio):
    v = pd.read_csv(rd.ruta(f"mesas/parr_votos_nacional_{anio}.csv.gz"), dtype=str)
    v = v[v["dignidad"].str.contains("PRESID", case=False, na=False)].copy()
    v["votos"] = v["votos"].astype(int)
    v["op"] = pd.to_numeric(v["op_codigo"], errors="coerce")
    v = v.dropna(subset=["op"])
    v["op"] = v["op"].astype(int).astype(str)
    v["bloque"] = v["op"].map(MAPA[anio]).fillna("RESTO")
    v["loc_id"] = v["cod_provincia"].str.cat([v["cod_canton"], v["cod_parroquia"]],
                                             sep="-")
    g = v.groupby(["loc_id", "bloque"])["votos"].sum().unstack(fill_value=0)
    return g


def metricas(proj, final, cols):
    sh = proj.sum(0); sh = 100 * sh / max(sh.sum(), 1)
    shf = final.sum(0); shf = 100 * shf / max(shf.sum(), 1)
    err = float(np.abs(sh - shf).sum() / 2)
    o = np.argsort(-shf)
    fin_top = cols[o[0]]
    margen_f = shf[o[0]] - shf[o[1]]
    ip = int(np.where(np.array(cols) == fin_top)[0][0])
    orden_proy = np.argsort(-sh)
    margen_p = sh[orden_proy[0]] - sh[orden_proy[1]]
    # margen "del mismo par" (top1 y top2 reales) proyectado
    i2 = o[1]
    margen_par = sh[ip] - sh[i2]
    return err, abs(margen_p - margen_f), abs(float(margen_par) - float(margen_f)), fin_top


def main():
    g21 = cargar(2021)
    g25 = cargar(2025)
    locs = sorted(set(g21.index) & set(g25.index))
    cols = sorted(set(g21.columns) | set(g25.columns))   # unión (ADN nace en 2025)
    g21 = g21.reindex(index=locs, columns=cols, fill_value=0)
    g25 = g25.reindex(index=locs, columns=cols, fill_value=0)
    base = g21.values.astype(float)
    final = g25.values.astype(float)
    print(f"[nacional 2021->2025] locs={len(locs)} bloques={cols} "
          f"votos2025={int(final.sum()):,}")
    print("  shares finales:", {c: round(100 * final.sum(0)[i] / final.sum(), 1)
                                for i, c in enumerate(cols)})

    jer = {k: (k[:2], k[3:6], k, k) for k in locs}
    modelo = Proyector(locs, jer, base, base.sum(1))
    terr_of = [k[:2] for k in locs]
    grupos_v1 = [np.array([l[:6] for l in locs]), np.array([l[:2] for l in locs]),
                 np.full(len(locs), "EC")]

    ords = ordenes(locs, g21, g25, cols)
    filas = []
    for nombre, orden in ords.items():
        for frac in UMBRALES:
            U = len(locs); n = max(3, int(round(frac * U))); cnt = orden[:n]
            obs = np.zeros_like(final); obs[cnt] = final[cnt]
            f = np.zeros(U); f[cnt] = 1.0
            sal = {}
            try:
                r = modelo.proyectar(obs.copy(), f, np.arange(len(cols)))
                sal["jerarquico"] = r["final"] if r else None
            except Exception:
                sal["jerarquico"] = None
            sal["v2_nacional"], _ = swing.proyectar(base, obs, terr_of, modo="nacional")
            sal["v4_territorio"], _ = swing.proyectar(base, obs, terr_of, modo="territorio")
            sal["v1_brasil"] = v1_brasil.proyectar(obs, base.sum(1), grupos_v1)
            for met, p in sal.items():
                if p is None:
                    continue
                err, me, mp, top = metricas(p, final, cols)
                filas.append((met, nombre, frac, round(err, 2), round(me, 2),
                              round(mp, 2), top))
        for met, nom, frac, err, me, mp, top in [x for x in filas if x[1] == nombre]:
            if abs(frac - 0.10) < 1e-9:
                print(f"  [{nombre}] {met:<14} @10% err={err:5.2f} "
                      f"|margen_top|={me:5.2f} |margen_par|={mp:5.2f}")
    df = pd.DataFrame(filas, columns=["metodo", "orden", "frac", "err_share",
                                      "err_margen_top", "err_margen_par", "top_final"])
    p = os.path.join(rd.ruta_dir("backtest"), "comparar_nacional_2021_2025.csv")
    df.to_csv(p, index=False)
    print(f"[OK] -> {p}")


if __name__ == "__main__":
    main()

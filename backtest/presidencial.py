# -*- coding: utf-8 -*-
"""
backtest/presidencial.py — Backtest presidencial **misma arena** con jerarquía completa,
probando la unidad fina en **zona (recinto)** o **junta (mesa)**.

Pares: 2023 anticipada 1v → 2025; 2021 → 2025; 2021 → 2023 (control).
Bloques: correísmo (2021 Arauz; 2023/2025 lista cabeza 5 RC) vs resto.
Orden de carga: orden de zonas de 2021 (minuto medio de sus juntas); las juntas de una
misma zona entran juntas (o la zona entera). `min_votos` descarta unidades chicas.

Jerarquía:
  * nivel=zona : (nacional, provincia, cantón, parroquia) sobre unidades zona.
  * nivel=junta: (provincia, cantón, parroquia, zona) sobre unidades junta (mesa).

Uso: python -m backtest.presidencial
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from datos.familias import normalizar_lista
from proyeccion import Proyector
from modelo import swing, v1_brasil

FRACS = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50]
DIR = rd.ruta("gaona_format")
FILES = {
    2021: ("gaona_2021_general_d1_presidente_junta.csv", "cand"),
    2023: ("gaona_2023_anticipada1v_d11_junta.csv", "org"),
    2025: ("gaona_2025_general_d11_junta.csv", "org"),
}


_CACHE = {}


def unidades_anio(anio, nivel="zona"):
    ck = (anio, nivel)
    if ck in _CACHE:
        return _CACHE[ck].copy()
    f, modo = FILES[anio]
    d = pd.read_csv(os.path.join(DIR, f), dtype=str,
                    usecols=["cod_prov", "cod_cant", "parroquia", "recinto", "junta",
                             "junta_genero", "cod_org_pol", "cod_candidato", "votos"])
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    z = (d["cod_prov"].str.zfill(2) + "-" + d["cod_cant"].str.zfill(3) + "-"
         + d["parroquia"].str.zfill(4) + "-" + d["recinto"].str.zfill(2))
    if nivel == "junta":
        d["u"] = z + "-" + d["junta"].str.zfill(3) + "-" + d["junta_genero"].fillna("")
        d["zona"] = z
    else:
        d["u"] = z
        d["zona"] = z
    if modo == "cand":
        iscor = d["cod_candidato"].isin(["1030", "3"])
    else:
        iscor = d["cod_org_pol"].map(lambda x: normalizar_lista(x) == "5")
    d["cor"] = np.where(iscor, d["votos"], 0)
    g = d.groupby("u").agg(corre=("cor", "sum"), total=("votos", "sum"),
                           zona=("zona", "first"))
    g["resto"] = g["total"] - g["corre"]
    g = g[["corre", "resto", "zona"]].astype({"corre": float, "resto": float})
    _CACHE[ck] = g
    return g.copy()


def orden_zonas():
    o = pd.read_csv(rd.ruta("backtest/orden_junta_2021.csv"), dtype={"key": str})
    o["zona"] = o["key"].str.rsplit("-", n=2).str[0]
    g = o.groupby("zona")["min_medio"].mean()
    prov = g.groupby(g.index.str[:2]).mean()
    return g, prov


def jerarquia(keys, nivel):
    if nivel == "junta":
        return {k: (k[:2], k[:6], k[:11], k[:14]) for k in keys}
    return {k: ("EC", k[:2], k[:6], k[:11]) for k in keys}


def metricas(proj, final, zonas):
    sh = 100 * proj.sum(0) / max(proj.sum(), 1)
    shf = 100 * final.sum(0) / max(final.sum(), 1)
    err = float(np.abs(sh - shf).sum() / 2)
    terr = np.array([z[:2] for z in zonas])
    P = pd.DataFrame(proj).groupby(terr).sum().values
    F = pd.DataFrame(final).groupby(terr).sum().values
    acc = float((P.argmax(1) == F.argmax(1)).mean())
    return err, acc


def backtest(base_year, target_year, min_votos=0, nivel="zona"):
    B = unidades_anio(base_year, nivel); T = unidades_anio(target_year, nivel)
    comunes = sorted(set(B.index) & set(T.index))
    B = B.loc[comunes]; T = T.loc[comunes]
    keep = (B[["corre", "resto"]].sum(1) >= min_votos) & (T[["corre", "resto"]].sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    g, prov = orden_zonas()
    # orden por zona (todas las juntas de la zona juntas)
    tz = np.array([g.get(z, np.nan) for z in B["zona"]], float)
    pv = np.array([prov.get(z[:2], np.nan) for z in B["zona"]], float)
    tz = np.where(np.isnan(tz), pv, tz)
    tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    jer = jerarquia(keys, nivel)
    base_val = B[["corre", "resto"]].sum(1).values
    modelo = Proyector(keys, jer, B[["corre", "resto"]].values, base_val)
    if nivel == "junta":
        grupos_v1 = [np.array([k[:14] for k in keys]), np.array([k[:11] for k in keys]),
                     np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
                     np.full(len(keys), "EC")]
    else:
        grupos_v1 = [np.array([k[:11] for k in keys]), np.array([k[:6] for k in keys]),
                     np.array([k[:2] for k in keys]), np.full(len(keys), "EC")]
    K = 2
    print(f"\n== {base_year} -> {target_year} · nivel={nivel} | unidades={len(keys)} "
          f"(min_votos={min_votos}) ==")
    print("   %   n      jerárq(err/acc)      v1(err/acc)      crudo err")
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys))))
        cnt = orden[:n]
        obs = np.zeros((len(keys), K)); obs[cnt] = T[["corre", "resto"]].values[cnt]
        f = np.zeros(len(keys)); f[cnt] = 1.0
        r = modelo.proyectar(obs.copy(), f, np.arange(K))
        if r is None:
            continue
        ej, aj = metricas(r["final"], T[["corre", "resto"]].values, keys)
        proj_v1 = v1_brasil.proyectar(obs, base_val, grupos_v1)
        ev, av = metricas(proj_v1, T[["corre", "resto"]].values, keys)
        crudo = obs.sum(0)
        sc = 100 * crudo / max(crudo.sum(), 1)
        sf = 100 * T[["corre", "resto"]].values.sum(0) / max(T[["corre", "resto"]].values.sum(), 1)
        err_c = float(np.abs(sc - sf).sum() / 2)
        print(f"  {fr*100:>4.0f}% {n:5d}   {ej:5.2f}/{aj:5.1%}     {ev:5.2f}/{av:5.1%}     {err_c:5.2f}")


def main():
    for nivel in ("zona", "junta"):
        backtest(2023, 2025, 0, nivel)
        backtest(2023, 2025, 100, nivel)
        backtest(2021, 2025, 100, nivel)
        backtest(2021, 2023, 100, nivel)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
backtest/local_junta.py — Backtest local 2019→2023 (prefecto/alcalde) a nivel **zona** o
**junta**, comparando jerárquico (Proyector) vs v1 vs crudo.

Homologación 2019: el crawl guarda **nombres** de partido/alianza. Se mapea a bloque
correísmo por keywords (FCS "COMPROMISO SOCIAL", "ALIANZA PAIS"/"PATRIA ALTIVA").
2023: bloque correísmo = lista cabeza 5 (RC) vía `familias.normalizar_lista`.

Orden de carga: orden de zonas de 2021 (minuto medio); las juntas de una zona entran juntas.
`min_votos` descarta unidades chicas.

Uso: python -m backtest.local_junta
"""
import os
import sys
import glob
import unicodedata
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from datos.familias import normalizar_lista
from proyeccion import Proyector
from modelo import v1_brasil

FRACS = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50]
DIR = rd.ruta("gaona_format")
G2023 = {"prefecto": "gaona_2023_seccional_d11_prefecto_junta.csv",
         "alcalde": "gaona_2023_seccional_d13_alcalde_junta.csv"}
D2019 = {"prefecto": "gaona2019_junta_d2", "alcalde": "gaona2019_junta_d4"}
_CACHE = {}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _corre_name(name):
    n = _norm(name)
    return ("COMPROMISO SOCIAL" in n or "ALIANZA PAIS" in n
            or "PATRIA ALTIVA" in n or "REVOLUCION CIUDADANA" in n)


def _unidad(d, nivel):
    z = (d["cod_prov"].str.zfill(2) + "-" + d["cod_cant"].str.zfill(3) + "-"
         + d["parroquia"].str.zfill(4) + "-" + d["recinto"].str.zfill(2))
    if nivel == "junta":
        return z + "-" + d["junta"].str.zfill(3) + "-" + d["junta_genero"].fillna("")
    return z


def unidades_2019(dig, nivel):
    ck = (2019, dig, nivel)
    if ck in _CACHE:
        return _CACHE[ck].copy()
    fs = glob.glob(rd.ruta(f"vivo/{D2019[dig]}*.csv"))
    d = pd.concat([pd.read_csv(f, dtype=str) for f in fs], ignore_index=True).drop_duplicates()
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    d["cor"] = np.where(d["cod_org_pol"].map(_corre_name), d["votos"], 0)
    d["u"] = _unidad(d, nivel)
    g = d.groupby("u").agg(corre=("cor", "sum"), total=("votos", "sum"))
    g["resto"] = g["total"] - g["corre"]
    g = g.astype(float)
    _CACHE[ck] = g
    return g.copy()


def unidades_2023(dig, nivel):
    ck = (2023, dig, nivel)
    if ck in _CACHE:
        return _CACHE[ck].copy()
    d = pd.read_csv(os.path.join(DIR, G2023[dig]), dtype=str)
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    d["cor"] = np.where(d["cod_org_pol"].map(lambda x: normalizar_lista(x) == "5"),
                        d["votos"], 0)
    d["u"] = _unidad(d, nivel)
    g = d.groupby("u").agg(corre=("cor", "sum"), total=("votos", "sum"))
    g["resto"] = g["total"] - g["corre"]
    g = g.astype(float)
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


def metricas(proj, final, keys):
    sh = 100 * proj.sum(0) / max(proj.sum(), 1)
    shf = 100 * final.sum(0) / max(final.sum(), 1)
    err = float(np.abs(sh - shf).sum() / 2)
    terr = np.array([k[:2] if dig == "prefecto" else k[3:6] for k in keys])
    P = pd.DataFrame(proj).groupby(terr).sum().values
    F = pd.DataFrame(final).groupby(terr).sum().values
    acc = float((P.argmax(1) == F.argmax(1)).mean())
    return err, acc


dig = "prefecto"
for dn in ("prefecto", "alcalde"):
    pass


def corrida(dignidad, nivel="junta", min_votos=100):
    global dig
    dig = dignidad
    B = unidades_2019(dignidad, nivel); T = unidades_2023(dignidad, nivel)
    comunes = sorted(set(B.index) & set(T.index))
    B = B.loc[comunes]; T = T.loc[comunes]
    keep = (B.sum(1) >= min_votos) & (T.sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    z = [k.rsplit("-", 1)[0] if nivel == "junta" else k for k in keys]
    g, prov = orden_zonas()
    tz = np.array([g.get(x, np.nan) for x in z], float)
    pv = np.array([prov.get(x[:2], np.nan) for x in z], float)
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
    print(f"\n== {dignidad} 2019->2023 · nivel={nivel} | unidades={len(keys)} (min_votos={min_votos}) ==")
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
        p1 = v1_brasil.proyectar(obs, base_val, grupos_v1)
        ev, av = metricas(p1, T[["corre", "resto"]].values, keys)
        cr = obs.sum(0)
        sc = 100 * cr / max(cr.sum(), 1)
        sf = 100 * T[["corre", "resto"]].values.sum(0) / max(T[["corre", "resto"]].values.sum(), 1)
        ec = float(np.abs(sc - sf).sum() / 2)
        print(f"  {fr*100:>4.0f}% {n:6d}   {ej:5.2f}/{aj:5.1%}     {ev:5.2f}/{av:5.1%}     {ec:5.2f}")


def main():
    for nivel in ("zona", "junta"):
        for dig_ in ("prefecto", "alcalde"):
            try:
                corrida(dig_, nivel)
            except Exception as e:
                print(f"[!] {dig_} {nivel}: {e}")


if __name__ == "__main__":
    main()

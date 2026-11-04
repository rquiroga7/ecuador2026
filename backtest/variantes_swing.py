# -*- coding: utf-8 -*-
"""
backtest/variantes_swing.py — Fase 3 (docs/backtest.md): grilla de variantes de swing.

Local 2019 → 2023 (prefecto/alcalde), a nivel zona o junta, con 3 esquemas de bloque
(familias / 2bloques / 3bloques+residual), comparando:
  * jerárquico con distintos conjuntos de niveles (N=nacional, P=provincia, C=cantón,
    Pa=parroquia, Z=zona);
  * v2 (nacional) y v4 (territorial en provincia/cantón/parroquia/zona);
  * v1 (cascadas de relleno).

Una sola corrida con el orden realista 2021 (extrapolado a 2023). `min_votos` descarta
unidades chicas.

Salida: D:\\ecuador2026_data\\backtest\\variantes_swing.csv
Uso: python -m backtest.variantes_swing
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from datos.familias import normalizar_lista
from datos.homologar_2019 import mapa_lista_2019, bloque
from proyeccion import Proyector
from modelo import swing, v1_brasil

FRACS = [0.05, 0.10, 0.20, 0.30, 0.50]
DIR = rd.ruta("gaona_format")
G2019 = {"prefecto": "gaona_2019_seccional_d11_prefecto_junta.csv",
         "alcalde": "gaona_2019_seccional_d13_alcalde_junta.csv"}
G2023 = {"prefecto": "gaona_2023_seccional_d11_prefecto_junta.csv",
         "alcalde": "gaona_2023_seccional_d13_alcalde_junta.csv"}
LF = {"nac": 0, "prov": 2, "cant": 6, "parr": 11, "zona": 14}
_C = {}
_MAPA2019 = None


def _mapa():
    global _MAPA2019
    if _MAPA2019 is None:
        _MAPA2019 = mapa_lista_2019()
    return _MAPA2019


def _unidad(d, nivel):
    z = (d["cod_prov"].str.zfill(2) + "-" + d["cod_cant"].str.zfill(3) + "-"
         + d["parroquia"].str.zfill(4) + "-" + d["recinto"].str.zfill(2))
    if nivel == "junta":
        return z + "-" + d["junta"].str.zfill(3) + "-" + d["junta_genero"].fillna("")
    return z


def unidades(anio, dig, nivel, esquema):
    ck = (anio, dig, nivel, esquema)
    if ck in _C:
        return _C[ck].copy()
    f = G2019[dig] if anio == 2019 else G2023[dig]
    d = pd.read_csv(os.path.join(DIR, f), dtype=str,
                    usecols=["cod_prov", "cod_cant", "parroquia", "recinto", "junta",
                             "junta_genero", "cod_org_pol", "votos"])
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    if anio == 2019:
        d["lista"] = d["cod_org_pol"].map(_mapa())
    else:
        d["lista"] = d["cod_org_pol"].map(normalizar_lista)
    mp = {x: bloque(x, anio, esquema) for x in d["lista"].dropna().unique()}
    d["bl"] = d["lista"].map(mp).fillna("LOCAL" if esquema == "familias" else "residual")
    d["u"] = _unidad(d, nivel)
    g = d.pivot_table(index="u", columns="bl", values="votos", aggfunc="sum", fill_value=0)
    g = g.astype(float)
    _C[ck] = g
    return g.copy()


def orden_zonas():
    o = pd.read_csv(rd.ruta("backtest/orden_junta_2021.csv"), dtype={"key": str})
    o["zona"] = o["key"].str.rsplit("-", n=2).str[0]
    g = o.groupby("zona")["min_medio"].mean()
    prov = g.groupby(g.index.str[:2]).mean()
    return g, prov


def jer_de(keys, niveles):
    out = {}
    for k in keys:
        tup = []
        for n in niveles:
            tup.append("EC" if n == "nac" else k[:LF[n]])
        out[k] = tuple(tup)
    return out


def metricas(proj, final, keys, dig):
    sh = 100 * proj.sum(0) / max(proj.sum(), 1)
    shf = 100 * final.sum(0) / max(final.sum(), 1)
    err = float(np.abs(sh - shf).sum() / 2)
    terr = np.array([k[:2] if dig == "prefecto" else k[3:6] for k in keys])
    P = pd.DataFrame(proj).groupby(terr).sum().values
    F = pd.DataFrame(final).groupby(terr).sum().values
    acc = float((P.argmax(1) == F.argmax(1)).mean())
    s = -np.sort(-P, axis=1)
    top2 = float(np.mean([F[i].argmax() in set(P[i].argsort()[::-1][:2]) for i in range(len(F))]))
    return err, acc, top2


HIER_ZONA = {"N-P-Pa": ["nac", "prov", "parr"],
             "N-P-C-Pa": ["nac", "prov", "cant", "parr"],
             "N-P-C-Pa-Z": ["nac", "prov", "cant", "parr", "zona"],
             "N-P-C-Z": ["nac", "prov", "cant", "zona"],
             "N-P-C": ["nac", "prov", "cant"],
             "N-P-Z": ["nac", "prov", "zona"]}
HIER_JUNTA = {"P-C-Pa-Z": ["prov", "cant", "parr", "zona"],
              "P-C-Z": ["prov", "cant", "zona"],
              "P-C": ["prov", "cant"],
              "P-Pa-Z": ["prov", "parr", "zona"]}


def corrida(esquema, dig, nivel, min_votos=100):
    B = unidades(2019, dig, nivel, esquema)
    T = unidades(2023, dig, nivel, esquema)
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= min_votos) & (T.sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    if not keys:
        return []
    K = len(cols)
    basev = B.values; finv = T.values; base_val = basev.sum(1)
    z = [k.rsplit("-", 1)[0] if nivel == "junta" else k for k in keys]
    g, prov = orden_zonas()
    tz = np.array([g.get(x, np.nan) for x in z], float)
    pv = np.array([prov.get(x[:2], np.nan) for x in z], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")

    metodos = {}
    hier = HIER_ZONA if nivel == "zona" else HIER_JUNTA
    for nombre, niveles in hier.items():
        metodos[f"hier:{nombre}"] = ("hier", jer_de(keys, niveles))
    # v2/v4
    for tn, idx in [("prov", 2), ("cant", 6), ("parr", 11), ("zona", 14)]:
        metodos[f"v4:{tn}"] = ("swing", np.array([k[:idx] for k in keys]))
    metodos["v2:nacional"] = ("swing", np.array(["EC"] * len(keys)))
    # v1 cascadas
    if nivel == "junta":
        metodos["v1:z-p-c-pr"] = ("v1", [np.array([k[:14] for k in keys]), np.array([k[:11] for k in keys]),
                                         np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]), np.full(len(keys), "EC")])
        metodos["v1:z-c-pr"] = ("v1", [np.array([k[:14] for k in keys]), np.array([k[:6] for k in keys]),
                                       np.array([k[:2] for k in keys]), np.full(len(keys), "EC")])
    else:
        metodos["v1:pa-c-pr"] = ("v1", [np.array([k[:11] for k in keys]), np.array([k[:6] for k in keys]),
                                        np.array([k[:2] for k in keys]), np.full(len(keys), "EC")])
        metodos["v1:c-pr"] = ("v1", [np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
                                     np.full(len(keys), "EC")])
    metodos["v1:pr"] = ("v1", [np.array([k[:2] for k in keys]), np.full(len(keys), "EC")])

    modelos = {n: Proyector(keys, v[1], basev, base_val) for n, v in metodos.items() if v[0] == "hier"}
    filas = []
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys))))
        cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        f = np.zeros(len(keys)); f[cnt] = 1.0
        for nombre, (tipo, arg) in metodos.items():
            try:
                if tipo == "hier":
                    r = modelos[nombre].proyectar(obs.copy(), f, np.arange(K))
                    proj = r["final"] if r else None
                elif tipo == "swing":
                    proj, _ = swing.proyectar(basev, obs, arg, modo="nacional" if nombre.startswith("v2") else "territorio")
                else:
                    proj = v1_brasil.proyectar(obs, base_val, arg)
            except Exception:
                proj = None
            if proj is None:
                continue
            err, acc, top2 = metricas(proj, finv, keys, dig)
            filas.append({"esquema": esquema, "dignidad": dig, "nivel": nivel,
                          "metodo": nombre, "frac": round(fr, 2), "err": round(err, 2),
                          "acc": round(acc, 3), "top2": round(top2, 3)})
    return filas


def main():
    out = rd.ruta_dir("backtest")
    filas = []
    for esquema in ("familias", "2bloques", "3bloques"):
        for nivel in ("zona", "junta"):
            for dig in ("prefecto", "alcalde"):
                try:
                    filas += corrida(esquema, dig, nivel, 100)
                except Exception as e:
                    print(f"[!] {esquema} {nivel} {dig}: {e}")
    df = pd.DataFrame(filas)
    p = os.path.join(out, "variantes_swing.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas")
    # resumen 10%/20% prefecto/alcalde por esquema
    for esquema in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            sub = df[(df.esquema == esquema) & (df.dignidad == dig) & (df.frac.isin([0.10, 0.20]))]
            if sub.empty:
                continue
            piv = sub.pivot_table(index="metodo", columns="frac", values="err", aggfunc="first")
            piv.columns = [f"err@{int(c*100)}%" for c in piv.columns]
            print(f"\n== {esquema} · {dig} (err) ==")
            print(piv.sort_values(piv.columns[0]).to_string())


if __name__ == "__main__":
    main()

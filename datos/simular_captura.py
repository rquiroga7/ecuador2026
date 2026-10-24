# -*- coding: utf-8 -*-
"""
datos/simular_captura.py — Genera una captura 2023 *simulada* con los **timestamps
de carga reales de 2021** y la **misma estructura de columnas** del volcado junta a
junta de Gabriel Gaona (Gaona 2021, `raw\\gaona_2021_presidencia_junta.csv`).

Motivación: los resultados del CNE no traen marca de tiempo por mesa, así que no se
puede reconstruir el orden real de publicación de 2023. Pero la captura de 2021 **sí**
lo tiene (jun-ta + `updated`). Trasladamos ese orden de carga a las mesas de 2023
emparejando por la clave estable `prov-cant-parroquia-zona-junta-sexo` (`orden_junta_2021.csv`,
95% de cobertura) y asignamos a cada junta de 2023 el minuto medio de publicación de su
misma junta en 2021. El resultado es un archivo 2023 con la forma de una captura en vivo
(`updated` + acumulados), útil para backtest/replay realistas.

Columnas de salida (idénticas a Gaona 2021):
    updated · cod_dignidad · cod_prov · cod_cant · circunscripcion · parroquia ·
    recinto · junta · junta_genero · acta_numero · cod_org_pol · cod_candidato ·
    total_sufragantes · nulos · blancos · votos · voto_acumulado · nulo_acumulado ·
    blanco_acumulado · sufragantes_acumulado · porcentaje_votos_validos

Salida (D:\\ecuador2026_data\\backtest\\):
    sim_2023_<dignidad>_junta.csv

Uso:
    python -m datos.simular_captura                 # prefecto y alcalde
    python -m datos.simular_captura prefecto
    python -m datos.simular_captura prefecto --t0 2023-02-05T17:00:00Z
"""

import os
import sys
import argparse

import numpy as np
import pandas as pd

import rutas_datos as rd

# Columnas del volcado de Gaona 2021 (fuente del esquema).
COLS_2021 = [
    "updated", "cod_dignidad", "cod_prov", "cod_cant", "circunscripcion",
    "parroquia", "recinto", "junta", "junta_genero", "acta_numero",
    "cod_org_pol", "cod_candidato", "total_sufragantes", "nulos", "blancos",
    "votos", "voto_acumulado", "nulo_acumulado", "blanco_acumulado",
    "sufragantes_acumulado", "porcentaje_votos_validos",
]

# Código de dignidad del CNE (esquema FINDINGS §4).
DIG_COD = {"prefecto": 11, "alcalde": 13, "concejal_urbano": 14,
           "concejal_rural": 12}

# Anchos de la clave de junta (prov-cant-circ-parr-zona-junta-sexo).
ANCHOS = {"cod_provincia": 2, "cod_canton": 3, "cod_circunscripcion": 1,
          "cod_parroquia": 4, "cod_zona": 2, "junta": 3}


def _clave_junta(m):
    """mesa_id `prov-cant-circ-parr-zona-junta-sexo` -> clave sin circunscripción."""
    q = m.astype(str).str.split("-")
    return (q.str[0] + "-" + q.str[1] + "-" + q.str[3] + "-" + q.str[4]
            + "-" + q.str[5] + "-" + q.str[6])


def orden_2021(destino="backtest/orden_junta_2021.csv"):
    """DataFrame con la clave de junta y el minuto medio de publicación de 2021."""
    p = rd.ruta(destino)
    if os.path.exists(p):
        return pd.read_csv(p, dtype={"key": str})
    from datos import publicacion
    return publicacion.orden_junta(publicacion.tabla_junta(publicacion.cargar()))


def _min_por_junta(mesas, orden):
    """min_medio de 2021 por mesa de otro año, con relleno jerárquico
    (match exacto -> mediana del cantón -> de la provincia -> global)."""
    o = orden.copy()
    o["prov"] = o["key"].str.split("-").str[0]
    o["cant"] = o["key"].str.split("-").str[1]
    gl = float(o["min_medio"].median())
    med_cant = o.groupby(["prov", "cant"])["min_medio"].median()
    med_prov = o.groupby("prov")["min_medio"].median()
    d = dict(zip(o["key"], o["min_medio"]))

    key = _clave_junta(mesas["mesa_id"])
    prov = mesas["cod_provincia"].astype(str).str.zfill(2)
    cant = mesas["cod_canton"].astype(str).str.zfill(3)
    mn = key.map(d)
    idx_c = pd.MultiIndex.from_arrays([prov, cant])
    mn = mn.fillna(pd.Series(med_cant.reindex(idx_c).values, index=mn.index))
    mn = mn.fillna(prov.map(med_prov))
    return mn.fillna(gl).astype(float)


def simular(dignidad="prefecto", anio=2023, t0="2023-02-05T17:00:00Z",
            orden=None, guardar=True, destino=None):
    """Escribe (y devuelve) la captura 2023 simulada con esquema 2021."""
    pv = rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz")
    pt = rd.ruta(f"mesas/mesas_{dignidad}_{anio}.csv.gz")
    if not (os.path.exists(pv) and os.path.exists(pt)):
        raise FileNotFoundError(f"faltan datos 2023 de {dignidad} ({pv} | {pt})")
    votos = pd.read_csv(pv, dtype=str)
    mesas = pd.read_csv(pt, dtype=str)
    votos["votos"] = pd.to_numeric(votos["votos"], errors="coerce").fillna(0).astype(int)
    for c in ["votos_emitidos", "votos_b", "votos_n"]:
        mesas[c] = pd.to_numeric(mesas[c], errors="coerce").fillna(0).astype(int)

    if orden is None:
        orden = orden_2021()
    mesas["min"] = _min_por_junta(mesas, orden)
    t0 = pd.Timestamp(t0)
    # minuto medio de publicación -> marca de tiempo (segundos incluidos)
    mesas["updated"] = t0 + pd.to_timedelta(mesas["min"], unit="m")

    # acumulados de la junta (por orden de publicación)
    mj = (mesas.sort_values(["updated", "mesa_id"])
          .drop_duplicates("mesa_id")
          .assign(nulo_acumulado=lambda d: d["votos_n"].cumsum(),
                  blanco_acumulado=lambda d: d["votos_b"].cumsum(),
                  sufragantes_acumulado=lambda d: d["votos_emitidos"].cumsum())
          [["mesa_id", "updated", "votos_emitidos", "votos_b", "votos_n",
            "nulo_acumulado", "blanco_acumulado", "sufragantes_acumulado"]])

    v = votos.merge(mj, on="mesa_id", how="left")
    v = v.sort_values(["updated", "mesa_id", "cod_candidato"], kind="stable")
    v["voto_acumulado"] = (v.groupby("cod_candidato")["votos"].cumsum())

    s = v["mesa_id"].astype(str).str.split("-")
    validos = (v["votos_emitidos"] - v["votos_n"] - v["votos_b"]).replace(0, np.nan)

    out = pd.DataFrame({
        "updated": v["updated"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cod_dignidad": DIG_COD.get(dignidad, ""),
        "cod_prov": s.str[0], "cod_cant": s.str[1], "circunscripcion": s.str[2],
        "parroquia": s.str[3], "recinto": s.str[4], "junta": s.str[5],
        "junta_genero": s.str[6],
        "acta_numero": v["cod_junta"],
        "cod_org_pol": v["lista"], "cod_candidato": v["cod_candidato"],
        "total_sufragantes": v["votos_emitidos"],
        "nulos": v["votos_n"], "blancos": v["votos_b"], "votos": v["votos"],
        "voto_acumulado": v["voto_acumulado"],
        "nulo_acumulado": v["nulo_acumulado"],
        "blanco_acumulado": v["blanco_acumulado"],
        "sufragantes_acumulado": v["sufragantes_acumulado"],
        "porcentaje_votos_validos": (v["votos"] / validos).round(4).fillna(0),
    })
    if guardar:
        p = destino or os.path.join(rd.ruta_dir("backtest"),
                                    f"sim_2023_{dignidad}_junta.csv")
        out.to_csv(p, index=False)
        print(f"[OK] {dignidad}: {len(out):,} filas, "
              f"{out['acta_numero'].nunique():,} juntas -> {p}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Captura 2023 simulada (esquema Gaona 2021).")
    ap.add_argument("dignidades", nargs="*", default=None,
                    help="prefecto | alcalde | concejal_urbano | concejal_rural")
    ap.add_argument("--t0", default="2023-02-05T17:00:00Z",
                    help="marca de tiempo base (default: cierre de votación 2023)")
    ap.add_argument("--anio", type=int, default=2023)
    a = ap.parse_args()
    digs = a.dignidades or ["prefecto", "alcalde"]
    for d in digs:
        simular(d, anio=a.anio, t0=a.t0)


if __name__ == "__main__":
    main()

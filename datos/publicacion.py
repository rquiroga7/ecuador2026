# -*- coding: utf-8 -*-
"""
datos/publicacion.py — Orden real de publicación y sesgo de carga (Ecuador 2021).

Usa la captura en vivo de Gabriel Gaona (`gaona_2021_presidencia_junta.csv`), que
trae, por junta, la marca de tiempo `updated` en que el acta se publicó. Es el
análogo ecuatoriano del `DT_RECEBIMENTO_BU_HOR_TSE` del TSE (Brasil).

Productos (D:\\ecuador2026_data\\backtest\\):
    carga_2021_nacional.csv     curva: tiempo -> % de juntas y % de votos
    sesgo_2021_provincia.csv    tiempo medio de publicación y share por provincia
    orden_parroquia_2021.csv    parroquia -> minuto medio de publicación (para transferir)
    orden_junta_2021.csv        junta -> minuto medio de publicación (orden real de carga)
    resumen_publicacion_2021.json

Uso:
    python -m datos.publicacion
"""

import os
import json

import numpy as np
import pandas as pd

import rutas_datos as rd

ARCHIVO = rd.ruta("raw/gaona_2021_presidencia_junta.csv")

# candidatos 2021 (1ª vuelta)
CANDS = {"1030": "Arauz", "1021": "Lasso", "2": "Yaku", "42": "Hervas"}
KEY_JUNTA = ["cod_prov", "cod_cant", "circunscripcion", "parroquia", "recinto",
             "junta", "junta_genero"]


def cargar():
    df = pd.read_csv(ARCHIVO, dtype=str)
    for c in ["cod_prov", "cod_cant", "circunscripcion", "parroquia", "recinto",
              "junta", "cod_candidato", "votos", "total_sufragantes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["updated"] = pd.to_datetime(df["updated"])
    df["junta_genero"] = df["junta_genero"].astype(str).str.upper()
    df["cod_candidato"] = df["cod_candidato"].astype("Int64").astype(str)
    df["loc_id"] = (df["cod_prov"].astype("Int64").astype(str).str.zfill(2) + "-"
                    + df["cod_cant"].astype("Int64").astype(str).str.zfill(3) + "-"
                    + df["parroquia"].astype("Int64").astype(str).str.zfill(4))
    return df


def tabla_junta(df):
    """Una fila por junta: tiempo de publicación, votos, sufragantes y share de los
    principales candidatos."""
    tot = df.groupby(KEY_JUNTA + ["loc_id"], sort=False).agg(
        updated=("updated", "min"),
        votos=("votos", "sum"),
        sufragantes=("total_sufragantes", "max"),
    ).reset_index()
    for num, nom in CANDS.items():
        v = df[df["cod_candidato"] == num].groupby(KEY_JUNTA, sort=False)["votos"].sum()
        tot = tot.merge(v.rename(f"v_{nom}").reset_index(), on=KEY_JUNTA, how="left")
        tot[f"v_{nom}"] = tot[f"v_{nom}"].fillna(0)
    tot["validos"] = tot["votos"]
    for nom in CANDS.values():
        tot[f"sh_{nom}"] = tot[f"v_{nom}"] / tot["votos"].replace(0, np.nan)
    return tot


def curva(g):
    o = g.sort_values("updated").reset_index(drop=True)
    o["cum_juntas"] = np.arange(1, len(o) + 1)
    o["cum_votos"] = o["votos"].cumsum()
    o["pct_juntas"] = 100 * o["cum_juntas"] / len(o)
    o["pct_votos"] = 100 * o["cum_votos"] / o["votos"].sum()
    t0 = o["updated"].min()
    o["min"] = (o["updated"] - t0).dt.total_seconds() / 60.0
    return o[["updated", "min", "cum_juntas", "cum_votos", "pct_juntas", "pct_votos"]]


def sesgo(g):
    t0 = g["updated"].min()
    g = g.copy()
    g["min"] = (g["updated"] - t0).dt.total_seconds() / 60.0
    g["prov"] = g["loc_id"].str[:2]
    por_prov = g.groupby("prov", as_index=False).agg(
        juntas=("votos", "size"), votos=("votos", "sum"),
        min_medio=("min", "mean"), min_mediano=("min", "median"),
        sh_Arauz=("sh_Arauz", "mean"), sh_Lasso=("sh_Lasso", "mean"))
    por_prov = por_prov.sort_values("min_medio")
    return g, por_prov


def orden_parroquia(g):
    t0 = g["updated"].min()
    g = g.copy()
    g["min"] = (g["updated"] - t0).dt.total_seconds() / 60.0
    o = g.groupby("loc_id", as_index=False).agg(
        juntas=("votos", "size"), votos=("votos", "sum"),
        min_medio=("min", "mean"), sh_Arauz=("sh_Arauz", "mean"))
    return o.sort_values("min_medio").reset_index(drop=True)


def _junta_key(df):
    """Clave de mesa `prov-cant-parroquia-zona-junta-sexo` (sin circunscripción).

    Coincide con la clave de los dumps por mesa del CNE salvo el campo
    circunscripción (que en 2021 y 2023 no distingue juntas): la usamos para mapear
    el orden real de publicación de 2021 sobre las mesas de cualquier otro año.
    """
    z = lambda c, n: pd.to_numeric(df[c], errors="coerce").astype("Int64").astype(str).str.zfill(n)
    return (z("cod_prov", 2) + "-" + z("cod_cant", 3) + "-"
            + z("parroquia", 4) + "-" + z("recinto", 2) + "-"
            + z("junta", 3) + "-" + df["junta_genero"].astype(str).str.upper())


def orden_junta(g):
    """Mesa -> minuto medio de publicación (2021), para transferir el orden de carga
    real a las mesas de otro año."""
    t0 = g["updated"].min()
    g = g.copy()
    g["min"] = (g["updated"] - t0).dt.total_seconds() / 60.0
    g["key"] = _junta_key(g)
    o = g.groupby("key", as_index=False).agg(
        juntas=("votos", "size"), votos=("votos", "sum"), min_medio=("min", "mean"))
    return o.sort_values("min_medio").reset_index(drop=True)


def _corr(x, y):
    m = x.notna() & y.notna()
    if m.sum() < 10 or (x[m].std() == 0) or (y[m].std() == 0):
        return float("nan")
    return float(np.corrcoef(x[m], y[m])[0, 1])


def main():
    df = cargar()
    g = tabla_junta(df)
    cur = curva(g)
    gprov, por_prov = sesgo(g)
    orden = orden_parroquia(g)
    ojunta = orden_junta(g)

    out = rd.ruta_dir("backtest")
    cur.to_csv(os.path.join(out, "carga_2021_nacional.csv"), index=False)
    por_prov.to_csv(os.path.join(out, "sesgo_2021_provincia.csv"), index=False)
    orden.to_csv(os.path.join(out, "orden_parroquia_2021.csv"), index=False)
    ojunta.to_csv(os.path.join(out, "orden_junta_2021.csv"), index=False)

    dur = float(cur["min"].max())
    # fracción de votos contados a distintos % de juntas (curva no lineal)
    def pct_votos_en(p):
        return float(cur.loc[(cur["pct_juntas"] - p).abs().idxmin(), "pct_votos"])
    resumen = {
        "juntas": int(len(g)),
        "votos": int(g["votos"].sum()),
        "duracion_min": round(dur, 1),
        "corr_min_sh_Arauz": round(_corr(gprov["min"], gprov["sh_Arauz"]), 3),
        "corr_min_sh_Lasso": round(_corr(gprov["min"], gprov["sh_Lasso"]), 3),
        "pct_votos_con_10pct_juntas": round(pct_votos_en(10), 1),
        "pct_votos_con_20pct_juntas": round(pct_votos_en(20), 1),
        "pct_votos_con_50pct_juntas": round(pct_votos_en(50), 1),
        "prov_mas_temprana": por_prov.iloc[0]["prov"],
        "prov_mas_tardia": por_prov.iloc[-1]["prov"],
    }
    with open(os.path.join(out, "resumen_publicacion_2021.json"), "w",
              encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print("\nProvincias más tempranas / tardías (min medio):")
    print(por_prov.head(5).to_string(index=False))
    print("...")
    print(por_prov.tail(5).to_string(index=False))
    return resumen


if __name__ == "__main__":
    main()

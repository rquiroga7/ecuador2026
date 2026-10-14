# -*- coding: utf-8 -*-
"""
datos/exportar_familias.py — XLSX de partidos/familias 2019-2023-2026 para revisión.

Produce un Excel con varias hojas:
  * `Partidos`     — lista × año: nombres/siglas, familia propuesta y votos
                     (prefecto y alcalde) de 2019 y 2023, con nota de 2026.
  * `Familias`     — votos por familia y año (evolución).
  * `Ganadores`    — prefecturas/alcaldías ganadas por familia y año.
  * `Mapa_familias`— hoja EDITABLE (lista → familia) para que la revise el experto.
  * `Notas_2026`   — contexto 2026 (RC suspendida, Amigo 16, ADN 7, etc.).

Fuentes: `organizaciones polticas 2019.sav` (2019), `tabla_bloques_*_2023`,
`parr_partido_*` (votos), y una tabla curada de organizaciones 2026.

Uso:  python -m datos.exportar_familias
"""
import os

import numpy as np
import pandas as pd

import rutas_datos as rd
from backtest.bloques_familia import FAMILIA

# Organizaciones nacionales 2026 (número de lista -> nombre), de fuentes CNE/prensa.
NOMBRE_2026 = {
    "1": "Centro Democrático (CD)", "2": "Unidad Popular (UP)",
    "3": "Sociedad Patriótica (PSP)", "4": "Pueblo, Igualdad y Democracia (PID)",
    "5": "Revolución Ciudadana (RC) — SUSPENDIDA", "6": "Partido Social Cristiano (PSC)",
    "7": "Acción Democrática Nacional (ADN)", "8": "Avanza",
    "12": "Izquierda Democrática (ID)", "16": "AMIGO (correísmo)",
    "17": "Partido Socialista Ecuatoriano (PSE)", "18": "Pachakutik (MUPP)",
    "20": "Futuro (antes Democracia Sí)", "21": "CREO", "23": "SUMA",
    "25": "Construye", "33": "RETO", "35": "MOVER",
}

# Vehículos del correísmo en 2026 (RC lista 5 y Amigo lista 16, ambas suspendidas;
# el correísmo reparte candidatos en un "abanico" de organizaciones).
CORREISMO_2026 = {
    "5": "RC (suspendida TCE mar-2026)",
    "16": "Amigo (suspendido TCE jul-2026)",
    "17": "PSE — vehículo principal (Guayas, Azuay)",
    "2": "UP — Alianza Ciudadana (Pichincha)",
    "70": "Todos — Alianza Ciudadana (Pichincha)",
    "1": "CD — en conversaciones",
    "33": "RETO — en conversaciones",
}

NOTAS_2026 = [
    ["Revolución Ciudadana (lista 5)", "Suspendida por el TCE (6-mar-2026, caso Caja Chica). No inscribe candidatos propios."],
    ["Amigo (lista 16)", "Iba a ser el vehículo nacional del correísmo; también SUSPENDIDO por el TCE (17-jul-2026)."],
    ["Vehículos del correísmo 2026", "Ante las dos suspensiones, el correísmo reparte candidatos: PSE(17) principal (Guayas: Sofía Espín; Azuay: Lloret), Alianza Ciudadana = UP(2)+PSE(17)+Todos(70) en Pichincha (Muñoz, Tonello), y conversaciones con CD(1) y RETO(33)."],
    ["Reserva", "La dirigencia (Rivadeneira/Zambrano) mantiene en reserva parte de las alianzas para evitar más suspensiones; hay acuerdos territoriales no públicos."],
    ["ADN (lista 7)", "Acción Democrática Nacional (Noboa); debut en seccionales. Rival del correísmo."],
    ["Futuro (lista 20)", "Antes Democracia Sí (DSí). NO abre sus puertas al correísmo."],
    ["SUMA(23), ID(12), RETO(33)", "Impedidos de inscribir candidatos propios (no hicieron democracia interna a tiempo); pueden ir en alianza."],
    ["Escala", "53.534 solicitudes; 1.348 a alcaldía, 152 a prefectura; ~397 alianzas."],
]


def _z(s):
    s = pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)
    return s


def org_2019():
    p = next(f for f in os.listdir(rd.ruta_dir("raw"))
             if f.lower().startswith("organizaciones pol"))
    df = pd.read_spss(os.path.join(rd.ruta_dir("raw"), p))
    df = df.rename(columns={"OP_LISTA": "lista", "OP_NOMBRE": "nombre_2019",
                            "OP_SIGLAS": "siglas_2019", "OP_AMBITO": "ambito_2019"})
    df["lista"] = pd.to_numeric(df["lista"], errors="coerce")
    df = df.dropna(subset=["lista"]).copy()
    df["lista"] = df["lista"].astype(int).astype(str)
    return df[["lista", "nombre_2019", "siglas_2019", "ambito_2019"]].drop_duplicates("lista")


def votos_por_lista(dig, anio):
    v = pd.read_csv(rd.ruta(f"mesas/parr_partido_{dig}_{anio}.csv.gz"), dtype=str)
    v["votos"] = v["votos"].astype(int)
    v["partido"] = pd.to_numeric(v["partido"], errors="coerce")
    v = v.dropna(subset=["partido"])
    v["lista"] = v["partido"].astype(int).astype(str)
    return v.groupby("lista")["votos"].sum()


def nombres_2023(dig, anio=2023):
    p = rd.ruta(f"mesas/tabla_bloques_{dig}_{anio}.csv.gz")
    if not os.path.exists(p):
        return pd.Series(dtype=str)
    t = pd.read_csv(p, dtype=str)
    t["lista"] = pd.to_numeric(t["bloque"], errors="coerce").dropna().astype(int).astype(str)
    return t.set_index("lista")["partido_modal"]


def ganadores(dig, anio):
    """Cuenta territorios ganados por lista."""
    v = pd.read_csv(rd.ruta(f"mesas/parr_partido_{dig}_{anio}.csv.gz"), dtype=str)
    v["votos"] = v["votos"].astype(int)
    v["partido"] = pd.to_numeric(v["partido"], errors="coerce")
    v = v.dropna(subset=["partido"])
    v["terr"] = v["loc_id"].str.slice(0, 2) if dig == "prefecto" else v["loc_id"].str.slice(0, 6)
    g = v.groupby(["terr", "partido"])["votos"].sum().unstack(fill_value=0)
    w = g.idxmax(1).astype(int).astype(str)
    return w.value_counts()


def main():
    org = org_2019()
    n23_p = nombres_2023("prefecto")
    n23_a = nombres_2023("alcalde")
    vp19, va19 = votos_por_lista("prefecto", 2019), votos_por_lista("alcalde", 2019)
    vp23, va23 = votos_por_lista("prefecto", 2023), votos_por_lista("alcalde", 2023)

    listas = sorted(set(org["lista"]) | set(vp19.index) | set(vp23.index) |
                    set(va19.index) | set(va23.index) | set(NOMBRE_2026),
                    key=lambda x: int(x))
    df = pd.DataFrame({"lista": listas})
    df = df.merge(org, on="lista", how="left")
    df["nombre_2023"] = df["lista"].map(n23_p).fillna(df["lista"].map(n23_a))
    df["nombre_2026"] = df["lista"].map(NOMBRE_2026)
    df["correismo_2026"] = df["lista"].map(CORREISMO_2026).fillna("")
    df["familia"] = df["lista"].map(FAMILIA).fillna("")
    df["pref_2019"] = df["lista"].map(vp19).fillna(0).astype(int)
    df["alc_2019"] = df["lista"].map(va19).fillna(0).astype(int)
    df["pref_2023"] = df["lista"].map(vp23).fillna(0).astype(int)
    df["alc_2023"] = df["lista"].map(va23).fillna(0).astype(int)
    tp19, ta19 = vp19.sum(), va19.sum()
    tp23, ta23 = vp23.sum(), va23.sum()
    df["sh_pref_2019"] = (100 * df["pref_2019"] / tp19).round(3)
    df["sh_pref_2023"] = (100 * df["pref_2023"] / tp23).round(3)
    df["sh_alc_2019"] = (100 * df["alc_2019"] / ta19).round(3)
    df["sh_alc_2023"] = (100 * df["alc_2023"] / ta23).round(3)
    df["d_sh_pref"] = (df["sh_pref_2023"] - df["sh_pref_2019"]).round(2)
    df["d_sh_alc"] = (df["sh_alc_2023"] - df["sh_alc_2019"]).round(2)
    df = df.sort_values("pref_2023", ascending=False)

    # Familias (con los no mapeados agrupados como "LOCAL")
    df["familia_eff"] = df["familia"].replace("", "LOCAL")
    fam = df.groupby("familia_eff").agg(
        n_listas=("lista", "nunique"),
        pref_2019=("pref_2019", "sum"), pref_2023=("pref_2023", "sum"),
        alc_2019=("alc_2019", "sum"), alc_2023=("alc_2023", "sum")).reset_index()
    for c, tot in [("pref_2019", tp19), ("pref_2023", tp23),
                   ("alc_2019", ta19), ("alc_2023", ta23)]:
        fam["sh_" + c] = (100 * fam[c] / tot).round(2)
    fam = fam.sort_values("pref_2023", ascending=False).rename(
        columns={"familia_eff": "familia"})

    # Ganadores por familia
    gan = []
    for dig in ["prefecto", "alcalde"]:
        for anio in [2019, 2023]:
            w = ganadores(dig, anio).rename_axis("lista").reset_index(name="n")
            w["familia"] = w["lista"].map(FAMILIA).fillna("LOCAL")
            g = w.groupby("familia")["n"].sum().rename(f"{dig}_{anio}")
            gan.append(g)
    gan = pd.concat(gan, axis=1).fillna(0).astype(int).reset_index()

    mapa = df[["lista", "nombre_2019", "nombre_2023", "nombre_2026",
               "correismo_2026", "familia"]].copy()

    out = rd.ruta("familias_ecuador_2019_2023_2026.xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        df[["lista", "nombre_2019", "siglas_2019", "ambito_2019", "nombre_2023",
            "nombre_2026", "correismo_2026", "familia", "pref_2019", "pref_2023",
            "sh_pref_2019", "sh_pref_2023", "d_sh_pref", "alc_2019", "alc_2023",
            "sh_alc_2019", "sh_alc_2023", "d_sh_alc"]].to_excel(
                xl, sheet_name="Partidos", index=False)
        fam.to_excel(xl, sheet_name="Familias", index=False)
        gan.to_excel(xl, sheet_name="Ganadores", index=False)
        mapa.to_excel(xl, sheet_name="Mapa_familias", index=False)
        pd.DataFrame(NOTAS_2026, columns=["tema", "detalle"]).to_excel(
            xl, sheet_name="Notas_2026", index=False)
    print(f"[OK] XLSX -> {out}")
    print(f"     {len(df)} listas | pref2019={tp19:,} pref2023={tp23:,} "
          f"alc2019={ta19:,} alc2023={ta23:,}")


if __name__ == "__main__":
    main()

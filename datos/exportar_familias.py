# -*- coding: utf-8 -*-
"""
datos/exportar_familias.py — XLSX de partidos/familias 2019-2023-2026 para revisión.

Produce un Excel con hojas:
  * `Instrucciones`  — cómo completar `Mapa_familias`.
  * `Partidos`       — lista × año: nombres/siglas, familia propuesta y votos
                       (prefecto y alcalde) de 2019 y 2023, con nota de 2026.
  * `Familias`       — votos por familia y año (evolución).
  * `Ganadores`      — prefecturas/alcaldías ganadas por familia y año.
  * `Mapa_familias`  — hoja EDITABLE (lista → familia) para el experto (con desplegable).
  * `Vocabulario`    — familias válidas para el desplegable.
  * `Notas_2026`     — contexto 2026.

Fuentes: `organizaciones polticas 2019.sav`, `tabla_bloques_*_2023`, `parr_partido_*`
(votos), y una tabla curada de organizaciones 2026.

Uso:  python -m datos.exportar_familias
"""
import os

import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import FAMILIA, VOCAB, overrides_efectivos

# Organizaciones nacionales 2026 (número de lista -> nombre), de fuentes CNE/prensa.
NOMBRE_2026 = {
    "1": "Centro Democrático (CD)", "2": "Unidad Popular (UP)",
    "3": "Sociedad Patriótica (PSP)", "4": "Pueblo, Igualdad y Democracia (PID)",
    "5": "Revolución Ciudadana (RC) — SUSPENDIDA", "6": "Partido Social Cristiano (PSC)",
    "7": "Acción Democrática Nacional (ADN)", "8": "Avanza",
    "12": "Izquierda Democrática (ID)", "16": "AMIGO (correísmo)",
    "17": "Partido Socialista Ecuatoriano (PSE)", "18": "Pachakutik (MUPP)",
    "20": "Futuro (antes Democracia Sí)", "21": "CREO", "23": "SUMA",
    "25": "Construye", "33": "RETO", "35": "MOVER", "70": "Movimiento Todos",
}

CORREISMO_2026 = {
    "5": "RC (suspendida TCE mar-2026)",
    "16": "Amigo (suspendido TCE jul-2026)",
    "17": "PSE — vehículo principal (Guayas, Azuay)",
    "2": "UP — Alianza Ciudadana (Pichincha)",
    "70": "Todos — Alianza Ciudadana (Pichincha)",
    "1": "CD — en conversaciones",
    "33": "RETO — en conversaciones",
}

# (Vocabulario importado de `datos.familias`: fuente única.)


def _lineas_instructivo():
    """Instructivo (docs/INSTRUCTIVO_FAMILIAS.md) como lista de líneas."""
    p = os.path.join(rd.REPO, "docs", "INSTRUCTIVO_FAMILIAS.md")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read().splitlines()
    out = []
    for tema, det in INSTRUCCIONES:
        out += [f"# {tema}", det, ""]
    return out


INSTRUCCIONES = [
    ["Objetivo",
     "Agrupar cada partido/movimiento (número de lista) en una FAMILIA política estable, "
     "para poder medir el cambio de voto (swing) entre 2019, 2023 y 2026, ya que las "
     "candidaturas y las alianzas cambian de una elección a otra."],
    ["Qué llenar",
     "En la hoja `Mapa_familias`, columna `familia` (resaltada): escribí una familia de la "
     "lista del desplegable para cada `lista`. La columna `familia_sugerida` es lo que "
     "propusimos automáticamente; corregila si está mal."],
    ["Regla 1",
     "Usá SIEMPRE las mismas etiquetas del desplegable (hoja `Vocabulario`). No inventes "
     "nombres nuevos salvo que sea imprescindible (si lo hacés, agregalos al vocabulario)."],
    ["Regla 2",
     "La familia sigue la IDENTIDAD/LINAJE del partido, aunque cambie de nombre o de "
     "número de lista. Ej.: FCS-2019 y RC-2023 son la misma familia (`RC`); "
     "Alianza PAIS→MOVER es `MOVER`; Democracia Sí→Futuro es `DSI`."],
    ["Regla 3",
     "Movimientos puramente locales/provinciales sin familia nacional → `LOCAL` "
     "(o `LOCAL-<provincia>` si querés distinguirlos)."],
    ["Regla 4 (2026)",
     "En 2026 la RC (lista 5) y Amigo (16) están SUSPENDIDAS, y el correísmo corre bajo "
     "otras tiendas (PSE 17, UP 2, Todos 70, y acuerdos reservados). Marcá en `familia` "
     "a qué familia corresponde cada tienda en 2026 (p. ej. PSE→¿`PSE` o `RC`?). "
     "La columna `correismo_2026` ya trae pistas."],
    ["Alineación con el modelo",
     "El modelo agrupa por FAMILIA (no por candidato). Un acierto acá mejora la "
     "proyección de prefectos/alcaldes. Si dudás, dejá la celda VACÍA y anotá el caso en "
     "`notas` — es mejor vacío que equivocado."],
    ["Evolución",
     "Las hojas `Familias` y `Ganadores` muestran cómo evolucionó cada familia "
     "(votos y prefecturas/alcaldías ganadas) en 2019 y 2023."],
]

NOTAS_2026 = [
    ["Revolución Ciudadana (lista 5)", "Suspendida por el TCE (6-mar-2026, caso Caja Chica). No inscribe candidatos propios."],
    ["Amigo (lista 16)", "Iba a ser el vehículo nacional del correísmo; también SUSPENDIDO por el TCE (17-jul-2026)."],
    ["Vehículos del correísmo 2026", "PSE(17) principal (Guayas: Sofía Espín; Azuay: Lloret), Alianza Ciudadana = UP(2)+PSE(17)+Todos(70) en Pichincha, y conversaciones con CD(1) y RETO(33)."],
    ["Reserva", "La dirigencia mantiene en reserva parte de las alianzas; hay acuerdos territoriales no públicos."],
    ["ADN (lista 7)", "Acción Democrática Nacional (Noboa); debut en seccionales. Rival del correísmo."],
    ["Futuro (lista 20)", "Antes Democracia Sí (DSí). NO abre sus puertas al correísmo."],
    ["SUMA(23), ID(12), RETO(33)", "Impedidos de inscribir candidatos propios (no hicieron democracia interna a tiempo)."],
    ["Escala", "53.534 solicitudes; 1.348 a alcaldía, 152 a prefectura; ~397 alianzas."],
]


def _z(s):
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)


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
    ov = overrides_efectivos()                  # ediciones previas del XLSX, si las hay
    df["familia_sugerida"] = df["lista"].map(FAMILIA).fillna("")
    # editable: arranca con la edición previa del experto si existe, si no la sugerencia
    df["familia"] = [ov.get(l) or FAMILIA.get(l, "") for l in df["lista"]]
    df["notas"] = ""
    df["pref_2019"] = df["lista"].map(vp19).fillna(0).astype(int)
    df["alc_2019"] = df["lista"].map(va19).fillna(0).astype(int)
    df["pref_2023"] = df["lista"].map(vp23).fillna(0).astype(int)
    df["alc_2023"] = df["lista"].map(va23).fillna(0).astype(int)
    tp19, ta19, tp23, ta23 = vp19.sum(), va19.sum(), vp23.sum(), va23.sum()
    df["sh_pref_2019"] = (100 * df["pref_2019"] / tp19).round(3)
    df["sh_pref_2023"] = (100 * df["pref_2023"] / tp23).round(3)
    df["sh_alc_2019"] = (100 * df["alc_2019"] / ta19).round(3)
    df["sh_alc_2023"] = (100 * df["alc_2023"] / ta23).round(3)
    df["d_sh_pref"] = (df["sh_pref_2023"] - df["sh_pref_2019"]).round(2)
    df["d_sh_alc"] = (df["sh_alc_2023"] - df["sh_alc_2019"]).round(2)
    df = df.sort_values("pref_2023", ascending=False).reset_index(drop=True)

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

    gan = []
    for dig in ["prefecto", "alcalde"]:
        for anio in [2019, 2023]:
            w = ganadores(dig, anio).rename_axis("lista").reset_index(name="n")
            w["familia"] = w["lista"].map(FAMILIA).fillna("LOCAL")
            gan.append(w.groupby("familia")["n"].sum().rename(f"{dig}_{anio}"))
    gan = pd.concat(gan, axis=1).fillna(0).astype(int).reset_index()

    mapa = df[["lista", "nombre_2019", "nombre_2023", "nombre_2026",
               "correismo_2026", "familia_sugerida", "familia", "notas"]].copy()
    voc = pd.DataFrame({"familia": VOCAB})

    out = rd.ruta("familias_ecuador_2019_2023_2026.xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        pd.DataFrame({"Instructivo": _lineas_instructivo()}).to_excel(
            xl, sheet_name="Instructivo", index=False)
        df[["lista", "nombre_2019", "siglas_2019", "ambito_2019", "nombre_2023",
            "nombre_2026", "correismo_2026", "familia", "pref_2019", "pref_2023",
            "sh_pref_2019", "sh_pref_2023", "d_sh_pref", "alc_2019", "alc_2023",
            "sh_alc_2019", "sh_alc_2023", "d_sh_alc"]].to_excel(
                xl, sheet_name="Partidos", index=False)
        fam.to_excel(xl, sheet_name="Familias", index=False)
        gan.to_excel(xl, sheet_name="Ganadores", index=False)
        mapa.to_excel(xl, sheet_name="Mapa_familias", index=False)
        voc.to_excel(xl, sheet_name="Vocabulario", index=False)
        pd.DataFrame(NOTAS_2026, columns=["tema", "detalle"]).to_excel(
            xl, sheet_name="Notas_2026", index=False)

        # desplegable en la columna `familia` de Mapa_familias
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.utils import get_column_letter
        wb = xl.book
        ws = wb["Mapa_familias"]
        col = list(mapa.columns).index("familia") + 1
        letra = get_column_letter(col)
        dv = DataValidation(type="list",
                            formula1=f"Vocabulario!$A$2:$A${len(VOCAB) + 1}",
                            allow_blank=True, showDropDown=False)
        ws.add_data_validation(dv)
        dv.add(f"{letra}2:{letra}{len(mapa) + 1}")
        # ancho de columnas
        anchos = {"nombre_2019": 40, "nombre_2023": 40, "nombre_2026": 34,
                  "correismo_2026": 34, "familia_sugerida": 16, "familia": 16,
                  "notas": 30}
        for i, c in enumerate(mapa.columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = anchos.get(c, 12)
        # hoja Instructivo: ancho, ajuste de texto y negrita en títulos
        from openpyxl.styles import Alignment, Font
        wsi = wb["Instructivo"]
        wsi.column_dimensions["A"].width = 110
        for row in wsi.iter_rows(min_col=1, max_col=1):
            c = row[0]
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if c.value and str(c.value).startswith("#"):
                c.font = Font(bold=True)

    print(f"[OK] XLSX -> {out}")
    print(f"     {len(df)} listas | pref2019={tp19:,} pref2023={tp23:,} "
          f"alc2019={ta19:,} alc2023={ta23:,}")


if __name__ == "__main__":
    main()

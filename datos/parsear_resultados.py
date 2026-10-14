# -*- coding: utf-8 -*-
"""
datos/parsear_resultados.py — Convierte los `.txt` del CNE (resultados por MESA)
a tablas tidy por dignidad.

Formato de entrada (pipe-delimited, latin-1, sin cabecera). Una fila por
(mesa, candidato); cada mesa es una **junta single-sex** con su `cod_junta`.
Columnas decodificadas en `docs/FINDINGS.md` §4:

    c0  cod_dignidad            c8  cod_junta  (id único de la mesa)
    c1  cod_provincia           c9  lista
    c2  cod_canton              c10 cod_candidato
    c3  cod_circunscripcion     c11 votos_emitidos  (sufragantes de la mesa)
    c4  cod_parroquia           c12 votos_b         (blancos *o* nulos)
    c5  cod_zona                c13 votos_n         (el otro de blancos/nulos)
    c6  junta                   c14 votos_candidato
    c7  sexo (F/M)

Hallazgos (2023, prefecto): `cod_junta` es único y consistente (40.058 mesas);
hay 20.941 ubicaciones físicas, 19.117 de ellas con mesa F y mesa M (~291
votos/mesa).

Claves:
    `mesa_id` = ubicación + sexo (estable entre elecciones; **clave de join**).
    `loc_id`  = ubicación sin sexo (para agregar F+M).
    `cod_junta` se guarda pero **no** es estable entre elecciones.

Se verifica `c11 - c12 - c13 = sum(c14)` por mesa.

Salidas (D:\\ecuador2026_data\\mesas\\), comprimidas:
    votos_<dignidad>_<anio>.csv.gz   largo: mesa_id, cod_candidato, votos
    mesas_<dignidad>_<anio>.csv.gz   una fila por mesa con totales

Uso:
    python -m datos.parsear_resultados [zip] [--anio 2023] [--dignidad prefecto]
"""

import os
import sys
import json
import zipfile

import pandas as pd

import rutas_datos as rd

COLUMNAS = [
    "cod_dignidad", "cod_provincia", "cod_canton", "cod_circunscripcion",
    "cod_parroquia", "cod_zona", "junta", "sexo", "cod_junta", "lista",
    "cod_candidato", "votos_emitidos", "votos_b", "votos_n", "votos_candidato",
]

DIGNIDADES = {  # nombre lógico -> prefijo del archivo dentro del zip del CNE
    "prefecto": "PREFECTA_PREFECTO",
    "alcalde": "ALCALDESA_ALCALDE",
    "concejal_urbano": "CONCEJALES_URBANOS",
    "concejal_rural": "CONCEJALES_RURALES",
    "cpccs_mujeres": "CPCCS_MUJERES",
    "cpccs_hombres": "CPCCS_HOMBRES",
}

ANCHOS = {  # ancho con ceros para cada código de la clave de ubicación
    "cod_provincia": 2, "cod_canton": 3, "cod_circunscripcion": 1,
    "cod_parroquia": 4, "cod_zona": 2, "junta": 3,
}
CLAVE = list(ANCHOS)
COLS_ID = CLAVE + ["sexo"]


def _miembro(z, prefijo):
    return next(
        (n for n in z.namelist()
         if os.path.basename(n).upper().startswith(prefijo.upper())
         and n.lower().endswith(".txt")),
        None,
    )


def _normalizar(df):
    for col, ancho in ANCHOS.items():
        s = df[col].astype(str).str.strip().str.lstrip("0")
        df[col] = s.where(s != "", "0").str.zfill(ancho)
    df["sexo"] = df["sexo"].astype(str).str.strip().str.upper()
    df["cod_junta"] = df["cod_junta"].astype(str).str.strip()
    df["loc_id"] = df[CLAVE[0]]
    for col in CLAVE[1:]:
        df["loc_id"] = df["loc_id"].str.cat(df[col], sep="-")
    df["mesa_id"] = df["loc_id"].str.cat(df["sexo"], sep="-")
    return df


def parsear_dignidad(zip_path, nombre, anio=2023, catalogo=None, guardar=True):
    """Parsea una dignidad y devuelve (votos_largo, mesas_totales, resumen)."""
    with zipfile.ZipFile(zip_path) as z:
        miembro = _miembro(z, DIGNIDADES[nombre])
        if miembro is None:
            raise FileNotFoundError(f"No hay archivo para '{nombre}' en {zip_path}")
        with z.open(miembro) as raw:
            df = pd.read_csv(raw, sep="|", header=None, names=COLUMNAS,
                             dtype=str, encoding="latin-1",
                             on_bad_lines="skip", na_filter=False)

    for c in ["votos_emitidos", "votos_b", "votos_n", "votos_candidato"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    df = _normalizar(df)

    # --- totales por mesa: constantes entre candidatos; verificar consistencia ---
    tot = df.groupby("mesa_id", sort=False).agg(
        loc_id=("loc_id", "first"), cod_junta=("cod_junta", "first"),
        **{c: (c, "first") for c in CLAVE}, sexo=("sexo", "first"),
        votos_emitidos=("votos_emitidos", "max"),
        emin=("votos_emitidos", "min"),
        votos_b=("votos_b", "max"), bmin=("votos_b", "min"),
        votos_n=("votos_n", "max"), nmin=("votos_n", "min"),
        n_candidatos=("cod_candidato", "nunique"),
    ).reset_index()
    consistente = bool(
        (tot["votos_emitidos"] == tot["emin"]).all()
        and (tot["votos_b"] == tot["bmin"]).all()
        and (tot["votos_n"] == tot["nmin"]).all())
    tot = tot.drop(columns=["emin", "bmin", "nmin"])

    # --- votos por (mesa, candidato) ---
    votos = df.groupby(["mesa_id", "cod_candidato"], sort=False).agg(
        votos=("votos_candidato", "sum"),
        lista=("lista", "first"),
        loc_id=("loc_id", "first"),
        cod_junta=("cod_junta", "first"),
    ).reset_index()

    # --- validación aritmética por mesa ---
    chk = votos.groupby("mesa_id", sort=False)["votos"].sum().rename("suma_cand")
    chk = chk.reset_index().merge(
        tot[["mesa_id", "votos_emitidos", "votos_b", "votos_n"]],
        on="mesa_id", how="left")
    chk["esperado"] = chk["votos_emitidos"] - chk["votos_b"] - chk["votos_n"]
    chk["ok"] = chk["suma_cand"] == chk["esperado"]
    n_mesas, n_ok = len(chk), int(chk["ok"].sum())
    dif = (chk["suma_cand"] - chk["esperado"]).abs()

    if catalogo is not None and "candidatos" in catalogo:
        cand = catalogo["candidatos"].rename(columns={
            "COD_CANDIDATO": "cod_candidato", "NOM_CANDIDATO": "candidato",
            "COD_PARTIDO": "cod_partido"})
        votos = votos.merge(cand[["cod_candidato", "candidato", "cod_partido"]],
                            on="cod_candidato", how="left")
        part = catalogo.get("partido")
        if part is not None:
            part = part.rename(columns={"COD_PARTIDO": "cod_partido",
                                        "NOM_PARTIDO": "partido",
                                        "LIS_PARTIDO": "lis_partido",
                                        "NUM_PARTIDO": "num_partido"})
            votos = votos.merge(
                part[["cod_partido", "partido", "lis_partido", "num_partido"]],
                on="cod_partido", how="left")

    resumen = {
        "dignidad": nombre, "anio": anio,
        "archivo": os.path.basename(zip_path), "miembro": miembro,
        "filas_crudas": int(len(df)),
        "n_mesas": int(n_mesas),
        "n_ubicaciones": int(tot["loc_id"].nunique()),
        "n_candidatos": int(votos["cod_candidato"].nunique()),
        "totales_consistentes_por_mesa": consistente,
        "mesas_ok": n_ok, "mesas_mismatch": int(n_mesas - n_ok),
        "max_abs_diff": int(dif.max()),
        "pct_mesas_exactas": round(100.0 * n_ok / n_mesas, 2),
        "votos_emitidos": int(tot["votos_emitidos"].sum()),
        "votos_b": int(tot["votos_b"].sum()),
        "votos_n": int(tot["votos_n"].sum()),
    }
    if guardar:
        d = rd.ruta_dir("mesas")
        pv = os.path.join(d, f"votos_{nombre}_{anio}.csv.gz")
        pm = os.path.join(d, f"mesas_{nombre}_{anio}.csv.gz")
        votos.to_csv(pv, index=False, compression="gzip")
        tot.to_csv(pm, index=False, compression="gzip")
        resumen["salidas"] = {"votos": pv, "mesas": pm}
    return votos, tot, resumen


def parsear_todo(zip_path, anio=2023):
    from datos import catalogo as cat
    cats = cat.cargar(zip_path)
    cat.guardar(cats)
    resumen = []
    for nombre in DIGNIDADES:
        try:
            _, _, r = parsear_dignidad(zip_path, nombre, anio=anio, catalogo=cats)
            resumen.append(r)
            print(f"[OK] {nombre:<16} mesas={r['n_mesas']:>6} "
                  f"locs={r['n_ubicaciones']:>6} cands={r['n_candidatos']:>3} "
                  f"mismatch={r['mesas_mismatch']}")
        except FileNotFoundError as e:
            print(f"[!] {nombre}: {e}")
    p = os.path.join(rd.ruta_dir("mesas"), f"resumen_{anio}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"[OK] resumen -> {p}")
    return resumen


def main():
    args = sys.argv[1:]
    zip_path = next((a for a in args if a.lower().endswith(".zip")),
                    os.path.join(rd.REPO, "DATOS2023CNE.zip"))
    anio = int(args[args.index("--anio") + 1]) if "--anio" in args else 2023
    if "--dignidad" in args:
        nombre = args[args.index("--dignidad") + 1]
        from datos import catalogo as cat
        cats = cat.cargar(zip_path)
        _, _, r = parsear_dignidad(zip_path, nombre, anio=anio, catalogo=cats)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    parsear_todo(zip_path, anio=anio)


if __name__ == "__main__":
    main()

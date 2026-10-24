# -*- coding: utf-8 -*-
r"""
datos/exportar_gaona.py — Exporta cada elección al **esquema Gaona** (2021).

Columnas (idénticas a `raw\gaona_2021_presidencia_junta.csv`):
    updated · cod_dignidad · cod_prov · cod_cant · circunscripcion · parroquia ·
    recinto · junta · junta_genero · acta_numero · cod_org_pol · cod_candidato ·
    total_sufragantes · nulos · blancos · votos · voto_acumulado · nulo_acumulado ·
    blanco_acumulado · sufragantes_acumulado · porcentaje_votos_validos

Fuentes:
  * `recintos` — volcados del portal app01 (2023 anticipada 1ªv y 2025): por recinto
    (zona), partidos con votos; blancos/nulos/sufragantes del parcial HTML. Sin
    `updated` ni nivel junta (se dejan vacíos). Acumulados = suma corrida por recinto.
  * `mesas`  — seccionales 2023 (dump por mesa): a nivel **junta** con `junta_genero`.

Salida (D:\\ecuador2026_data\\gaona_format\\):
  gaona_<anio>_<eleccion>_d<dig>_<nivel>.csv

Uso:
    python -m datos.exportar_gaona
"""

import os
import re
import csv
import glob
import html
import json

import numpy as np
import pandas as pd

import rutas_datos as rd

COLS = ["updated", "cod_dignidad", "cod_prov", "cod_cant", "circunscripcion",
        "parroquia", "recinto", "junta", "junta_genero", "acta_numero",
        "cod_org_pol", "cod_candidato", "total_sufragantes", "nulos", "blancos",
        "votos", "voto_acumulado", "nulo_acumulado", "blanco_acumulado",
        "sufragantes_acumulado", "porcentaje_votos_validos"]

DIG_MESAS = {"prefecto": 11, "concejal_rural": 12, "alcalde": 13,
             "concejal_urbano": 14}


def _totales_html(h):
    t = re.sub(r"<[^>]+>", " ", html.unescape(h or ""))
    t = re.sub(r"\s+", " ", t)

    def g(pat):
        m = re.search(pat, t)
        return int(m.group(1).replace(".", "")) if m else 0
    return {"blancos": g(r"Blancos\s+([\d\.]+)"),
            "nulos": g(r"Nulos\s+([\d\.]+)"),
            "sufragantes": g(r"Sufragantes\s+([\d\.]+)")}


def _acumular(df):
    """Acumulados por orden geografico (updated no existe en estas fuentes)."""
    if df.empty:
        return df
    df = df.sort_values(["cod_prov", "cod_cant", "parroquia", "recinto", "junta",
                         "cod_org_pol"]).reset_index(drop=True)
    key = ["cod_prov", "cod_cant", "circunscripcion", "parroquia", "recinto", "junta",
           "junta_genero"]
    rec = df.drop_duplicates(subset=key).copy()
    rec["sufragantes_acumulado"] = rec["total_sufragantes"].cumsum()
    rec["nulo_acumulado"] = rec["nulos"].cumsum()
    rec["blanco_acumulado"] = rec["blancos"].cumsum()
    df = df.merge(rec[key + ["sufragantes_acumulado", "nulo_acumulado",
                             "blanco_acumulado"]], on=key, how="left")
    df["voto_acumulado"] = df.groupby("cod_org_pol")["votos"].cumsum()
    return df


def exportar_recintos(tag, anio, eleccion, destino_dir):
    base = os.path.join(rd.ruta_dir("vivo"), "crudo", "app01", tag)
    if not os.path.isdir(base):
        print(f"[!] no existe {base}"); return []
    salidas = []
    for dig in sorted(os.listdir(base)):
        d = os.path.join(base, dig)
        if not os.path.isdir(d):
            continue
        rows = []
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            key = os.path.basename(f)[:-5]           # prov-cant-parr-zona
            partes = key.split("-")
            if len(partes) != 4:
                continue
            j = json.load(open(f, encoding="utf-8"))
            tot = _totales_html(j.get("VistaParcialProcesamiento"))
            for p in j.get("datos") or []:
                rows.append({
                    "updated": "", "cod_dignidad": dig,
                    "cod_prov": partes[0], "cod_cant": partes[1],
                    "circunscripcion": "-1", "parroquia": partes[2],
                    "recinto": partes[3], "junta": "", "junta_genero": "",
                    "acta_numero": "",
                    "cod_org_pol": str(p.get("strOrdPartido", "")),
                    "cod_candidato": str(p.get("intCodPartido", "")),
                    "total_sufragantes": tot["sufragantes"], "nulos": tot["nulos"],
                    "blancos": tot["blancos"], "votos": int(p.get("intVotos") or 0),
                })
        if not rows:
            continue
        df = _acumular(pd.DataFrame(rows))
        val = (df["total_sufragantes"] - df["nulos"] - df["blancos"]).replace(0, np.nan)
        df["porcentaje_votos_validos"] = (df["votos"] / val).round(4).fillna(0)
        df = df[COLS]
        p = os.path.join(destino_dir, f"gaona_{anio}_{eleccion}_d{dig}_recinto.csv")
        df.to_csv(p, index=False)
        print(f"[OK] {p} ({len(df)} filas, {len(df[['cod_prov','cod_cant','parroquia','recinto']].drop_duplicates())} recintos)")
        salidas.append(p)
    return salidas


def exportar_juntas(tag, anio, eleccion, dignidad="11", destino_dir=None):
    """Exporta el crawl por **junta** (`<tag>/<dig>_junta/*.json`) al esquema Gaona.

    `junta` = número dentro de la zona (derivado de la etiqueta `1F`/`1M` del manifiesto);
    `junta_genero` = F/M. Sufragantes/blancos/nulos salen del parcial HTML.
    """
    base = rd.ruta(f"vivo/crudo/app01/{tag}/{dignidad}_junta")
    if not os.path.isdir(base):
        print(f"[!] no existe {base}"); return None
    manif = rd.ruta(f"vivo/manifiesto_junta_{tag}_{dignidad}.csv")
    gen = {}
    if os.path.exists(manif):
        for r in csv.DictReader(open(manif, encoding="utf-8")):
            gen[os.path.basename(r.get("archivo", ""))] = r.get("genero", "")
    rows = []
    for f in sorted(glob.glob(os.path.join(base, "*.json"))):
        key = os.path.basename(f)[:-5]
        p = key.split("-")
        if len(p) != 5:
            continue
        j = json.load(open(f, encoding="utf-8"))
        tot = _totales_html(j.get("VistaParcialProcesamiento"))
        lab = gen.get(os.path.basename(f), "")
        num = re.sub(r"\D", "", lab)
        sex = "F" if lab.upper().endswith("F") else ("M" if lab.upper().endswith("M") else "")
        for d in j.get("datos") or []:
            rows.append({
                "updated": "", "cod_dignidad": dignidad,
                "cod_prov": p[0], "cod_cant": p[1], "circunscripcion": "-1",
                "parroquia": p[2], "recinto": p[3], "junta": num, "junta_genero": sex,
                "acta_numero": "",
                "cod_org_pol": str(d.get("strOrdPartido", "")),
                "cod_candidato": str(d.get("intCodPartido", "")),
                "total_sufragantes": tot["sufragantes"], "nulos": tot["nulos"],
                "blancos": tot["blancos"], "votos": int(d.get("intVotos") or 0),
            })
    if not rows:
        print(f"[!] sin filas en {base}"); return None
    df = _acumular(pd.DataFrame(rows))
    val = (df["total_sufragantes"] - df["nulos"] - df["blancos"]).replace(0, np.nan)
    df["porcentaje_votos_validos"] = (df["votos"] / val).round(4).fillna(0)
    df = df[COLS]
    p = os.path.join(destino_dir, f"gaona_{anio}_{eleccion}_d{dignidad}_junta.csv")
    df.to_csv(p, index=False)
    print(f"[OK] {p} ({len(df)} filas, {df[['cod_prov','cod_cant','parroquia','recinto','junta','junta_genero']].drop_duplicates().shape[0]} juntas)")
    return p


def exportar_mesas(dignidad, anio=2023, eleccion="seccional", destino_dir=None):
    pv = rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz")
    pm = rd.ruta(f"mesas/mesas_{dignidad}_{anio}.csv.gz")
    if not (os.path.exists(pv) and os.path.exists(pm)):
        print(f"[!] faltan {dignidad} {anio}"); return None
    v = pd.read_csv(pv, dtype=str, usecols=["mesa_id", "cod_candidato", "lista",
                                            "votos", "cod_junta"])
    m = pd.read_csv(pm, dtype=str, usecols=["mesa_id", "votos_emitidos", "votos_b",
                                            "votos_n"])
    v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
    for c in ["votos_emitidos", "votos_b", "votos_n"]:
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0).astype(int)
    v = v.merge(m, on="mesa_id", how="left")
    s = v["mesa_id"].str.split("-")
    df = pd.DataFrame({
        "updated": "", "cod_dignidad": DIG_MESAS.get(dignidad, ""),
        "cod_prov": s.str[0], "cod_cant": s.str[1], "circunscripcion": s.str[2],
        "parroquia": s.str[3], "recinto": s.str[4], "junta": s.str[5],
        "junta_genero": s.str[6], "acta_numero": v["cod_junta"] if "cod_junta" in v else "",
        "cod_org_pol": v["lista"], "cod_candidato": v["cod_candidato"],
        "total_sufragantes": v["votos_emitidos"], "nulos": v["votos_n"],
        "blancos": v["votos_b"], "votos": v["votos"],
    })
    df = _acumular(df)
    val = (df["total_sufragantes"] - df["nulos"] - df["blancos"]).replace(0, np.nan)
    df["porcentaje_votos_validos"] = (df["votos"] / val).round(4).fillna(0)
    df = df[COLS]
    p = os.path.join(destino_dir, f"gaona_{anio}_{eleccion}_d{DIG_MESAS.get(dignidad,'')}_{dignidad}_junta.csv")
    df.to_csv(p, index=False)
    print(f"[OK] {p} ({len(df)} filas)")
    return p


def main():
    out = rd.ruta_dir("gaona_format")
    print("== 2023 seccional (junta) ==")
    for dig in ["prefecto", "alcalde"]:
        exportar_mesas(dig, 2023, "seccional", out)
    print("== 2023 anticipada 1a vuelta (junta) ==")
    exportar_juntas("resultados2023_anticipadas", 2023, "anticipada1v", "11", out)
    print("== 2025 general (junta) ==")
    exportar_juntas("resultados2025", 2025, "general", "11", out)
    print("== 2023 general anticipada 1a vuelta (recinto) ==")
    exportar_recintos("resultados2023_anticipadas", 2023, "anticipada1v", out)
    print("== 2025 general (recinto) ==")
    exportar_recintos("resultados2025", 2025, "general", out)
    print("[OK] ->", out)


if __name__ == "__main__":
    main()

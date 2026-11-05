# -*- coding: utf-8 -*-
"""
datos/procesar_2026.py — Limpia `Pref_y_Alc_2026.xlsx` (hojas provinciales heterogéneas)
y genera `Pref_y_Alc_2026.csv` con las candidaturas de **correísmo 2026**.

Salidas:
  Pref_y_Alc_2026.csv       -> solo correísmo (listas 2/5/17/70 y alianzas PSE/UP/RC/Todos)
  Pref_y_Alc_2026_full.csv  -> todas las filas extraídas (auditoría, con tipo_2026)

Uso: python -m datos.procesar_2026
"""
import os
import re
import sys
import unicodedata
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd

XLSX = os.path.join(rd.REPO, "Pref_y_Alc_2026.xlsx")
if not os.path.exists(XLSX):
    XLSX = r"C:\Users\Usuario\Documents\GitHub\ecuador2026\Pref_y_Alc_2026.xlsx"

CORE = {"2", "5", "17", "70"}
ALLY = {"1", "33"}
PROV_SHEET = {
    "Los Ríos": "Los Ríos", "Cañar": "Cañar", "Santo Domingo": "Santo Domingo",
    "Carchi": "Carchi", "LOJA": "Loja", "EL ORO ": "El Oro", "Chimborazo": "Chimborazo",
    "PICHINCHA": "Pichincha", "Guayas": "Guayas", "MANABI": "Manabí", "AZUAY": "Azuay",
    "SANTA ELENA": "Santa Elena", "ESMERALDAS": "Esmeraldas", "TUNGURAGUA": "Tungurahua",
    "IMBABURA": "Imbabura",
}
PROV_NAMES = {"SUCUMBIOS", "ORELLANA", "NAPO", "PASTAZA", "MORONA SANTIAGO",
              "ZAMORA CHINCHIPE"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().replace(".", " ").split())


def clean(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).replace("\n", " ").strip()
    return "" if s.lower() in ("nan", "none") else s


def listas(s):
    return set(re.findall(r"\d+", str(s)))


def tipo_2026(lista, partido):
    L = listas(lista)
    if L & CORE:
        return "correismo"
    p = norm(partido)
    keys = ["PSE", "PARTIDO SOCIALISTA", "UNIDAD POPULAR", "REVOLUCION CIUDADANA",
            "RC5", "ALIANZA CIUDADANA", "UNIDAD CIUDADANA",
            "JUNTOS POR LA TRANSFORMACION", "AMIGO"]
    if any(k in p for k in keys):
        return "correismo"
    if L & ALLY:
        return "aliado"
    return "otro"


def norm_dig(d):
    d = norm(d)
    if ("VICE" in d or d.startswith("V ")) and "PREF" in d:
        return "Viceprefecto"
    if "PREF" in d:
        return "Prefecto"
    if "ALCAL" in d:
        return "Alcalde"
    if "CONCEJ" in d:
        return "Concejal"
    if "JUNTA" in d:
        return "Junta"
    return d.title() if d else ""


def _header_row(df, maxr=15):
    keys = ["PROVINCIA", "APELLIDO", "DIGNIDAD", "CANTON", "LISTA", "NOMBRE",
            "CANDIDATO", "PARTIDO", "PUESTO", "CANDIDATURA", "SUJETO"]
    for i in range(min(maxr, len(df))):
        row = [norm(x) for x in df.iloc[i].tolist()]
        if sum(any(k in c for k in keys) for c in row) >= 3:
            return i
    return None


def _mapping(header):
    m = {}
    vals = set()
    for j, h in enumerate(header):
        if not h:
            continue
        if "PROVINCIA" in h and "provincia" not in vals:
            m[j] = "provincia"; vals.add("provincia")
        elif "DIGNIDAD" in h and "dignidad" not in vals:
            m[j] = "dignidad"; vals.add("dignidad")
        elif "PUESTO" in h and "puesto" not in vals:
            m[j] = "puesto"; vals.add("puesto")
        elif "CANTON" in h and "canton" not in vals:
            m[j] = "canton"; vals.add("canton")
        elif ("APELLIDO" in h or "CANDIDATO" in h) and "candidato" not in vals:
            m[j] = "candidato"; vals.add("candidato")
        elif ("NOMBRE DE LA ALIANZA" in h or h.startswith("PARTIDO")
              or h == "NOMBRE") and "partido" not in vals:
            m[j] = "partido"; vals.add("partido")
        elif "LISTA" in h and "lista" not in vals:
            m[j] = "lista"; vals.add("lista")
        elif "GENERO" in h and "genero" not in vals:
            m[j] = "genero"; vals.add("genero")
        elif "ESTADO" in h and "estado" not in vals:
            m[j] = "estado"; vals.add("estado")
    return m


def parse_standard(df, sheet):
    hdr = _header_row(df)
    if hdr is None:
        return []
    header = [norm(x) for x in df.iloc[hdr].tolist()]
    mp = _mapping(header)
    out = []
    last_prov = PROV_SHEET.get(sheet, sheet)
    last_cant = ""
    for i in range(hdr + 1, len(df)):
        vals = [clean(x) for x in df.iloc[i].tolist()]
        rec = {canon: (vals[j] if j < len(vals) else "") for j, canon in mp.items()}
        cand = rec.get("candidato", "")
        if not cand:
            continue
        prov = rec.get("provincia", "") or last_prov
        if prov:
            last_prov = prov
        cant = rec.get("canton", "") or last_cant
        if cant:
            last_cant = cant
        dig = norm_dig(rec.get("dignidad", "") or rec.get("puesto", ""))
        if not dig:  # p. ej. Cañar: la dignidad viene en la columna "Celular"
            for v in vals:
                if any(k in norm(v) for k in ("ALCALD", "PREFECT", "CONCEJ", "JUNTA")):
                    dig = norm_dig(v)
                    if dig:
                        break
        out.append({
            "provincia": PROV_SHEET.get(sheet, prov.strip().title()),
            "canton": cant.strip().title(),
            "dignidad": dig,
            "candidato": cand,
            "lista": rec.get("lista", ""),
            "partido_alianza": rec.get("partido", ""),
            "genero": rec.get("genero", ""),
            "estado": rec.get("estado", ""),
            "fuente": sheet,
        })
    return out


def parse_los_rios(df, sheet):
    out = []
    hdr = 3
    for i in range(hdr + 1, len(df)):
        v = [clean(x) for x in df.iloc[i].tolist()] + [""] * 5
        if not v[2]:
            continue
        out.append({"provincia": "Los Ríos", "canton": v[1].title(), "dignidad": "Alcalde",
                    "candidato": v[2], "lista": "", "partido_alianza": v[4],
                    "genero": v[3], "estado": "", "fuente": sheet})
    return out


def parse_guayas(df, sheet):
    out = []
    hdr = 4
    for i in range(hdr + 1, len(df)):
        v = [clean(x) for x in df.iloc[i].tolist()] + [""] * 5
        if not v[2]:
            continue
        out.append({"provincia": "Guayas", "canton": v[0].title(), "dignidad": norm_dig(v[1]),
                    "candidato": v[2], "lista": v[3], "partido_alianza": v[4],
                    "genero": "", "estado": "", "fuente": sheet})
    return out


def parse_amazonia(df, sheet):
    out = []
    prov = ""
    for i in range(len(df)):
        v = [clean(x) for x in df.iloc[i].tolist()] + ["", "", ""]
        c0, c1, c2 = v[0], v[1], v[2]
        if not c0 and not c1:
            continue
        if norm(c0) in PROV_NAMES:
            prov = c0.title()
            if not c1:
                continue
        d = norm(c0)
        if "PREFECT" in d:
            dig, cant = "Prefecto", prov
        elif "ALCAL" in d:
            dig = "Alcalde"
            cant = re.sub(r"\b(ALCALDIA|ALCALDE|ALCALDESA|DE|LA|EL)\b", " ", d)
            cant = " ".join(cant.split()).title()
        else:
            continue
        if not c1:
            continue
        out.append({"provincia": prov, "canton": cant, "dignidad": dig,
                    "candidato": c1, "lista": "", "partido_alianza": c2,
                    "genero": "", "estado": "", "fuente": sheet})
    return out


def extraer():
    x = pd.ExcelFile(XLSX)
    filas = []
    for s in x.sheet_names:
        if s == "Hoja2":
            continue
        df = pd.read_excel(XLSX, sheet_name=s, header=None, dtype=str)
        if s == "Los Ríos":
            filas += parse_los_rios(df, s)
        elif s == "Guayas":
            filas += parse_guayas(df, s)
        elif s == "Amazonía":
            filas += parse_amazonia(df, s)
        else:
            filas += parse_standard(df, s)
    d = pd.DataFrame(filas)
    d = d[d.candidato.str.strip().ne("")]
    d = d[~d.candidato.str.contains(r"NO HAY ALCALDE|CONCEJALES|JUNTA|VARIOS", case=False, na=False)]
    d = d[d.dignidad != "Concejal"]              # el archivo es Pref_y_Alc
    d["canton"] = (d["canton"].astype(str).str.replace(r":+$", "", regex=True)
                   .str.strip().str.title())
    d["lista_tipo"] = [tipo_2026(l, p) for l, p in zip(d.lista, d.partido_alianza)]
    d = d.drop_duplicates(["provincia", "canton", "dignidad", "candidato", "lista"])
    return d


def main():
    d = extraer()
    # Todo el xlsx son aliados del correísmo 2026 (confirmado por el usuario).
    d["aliado_correismo_2026"] = True
    full = os.path.join(rd.REPO, "Pref_y_Alc_2026_full.csv")
    d.to_csv(full, index=False, encoding="utf-8-sig")
    out = os.path.join(rd.REPO, "Pref_y_Alc_2026.csv")
    d.to_csv(out, index=False, encoding="utf-8-sig")

    print(f"[OK] {len(d)} filas -> {out}")
    print("\nPor dignidad:")
    print(d.groupby("dignidad").size().to_string())
    print("\nPrefecto por provincia:")
    print(d[d.dignidad == "Prefecto"][["provincia", "candidato", "lista", "partido_alianza"]]
          .sort_values("provincia").to_string(index=False))
    print("\nAlcalde por provincia (conteo):")
    print(d[d.dignidad == "Alcalde"].groupby("provincia").size().to_string())


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
datos/homologar_2019.py — Fase 1 (docs/backtest.md): homologación 2019 nombre→lista→familia.

El crawl 2019 del portal guarda **nombres** de partido/alianza (no códigos de lista). Aquí:
  * se construye un mapa `nombre → lista` desde `organizaciones politicas 2019.sav`
    (OP_NOMBRE / OP_SIGLAS / OP_LISTA), con reglas para alianzas ("LISTAS X", prefijo "6-…");
  * se mapea lista → familia/bloque (año-específico);
  * se reporta cobertura de votos.

Bloques (esquemas):
  * `familias`   — `datos.familias.familia`.
  * `2bloques`   — correísmo vs resto (2019: {5,35}; 2023: {5}).
  * `3bloques`   — correísmo / izquierda / derecha / **residual** (LOCAL/OTRO/no homologado).

Uso: python -m datos.homologar_2019
"""
import os
import re
import sys
import glob
import unicodedata
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from datos.familias import familia, normalizar_lista

RAW = rd.ruta("raw")

# --- año-específico: lista -> bloque (3 bloques + residual) ---
# 2019: la 35 (Alianza PAIS) se excluye del correísmo: en 2023 la 35 es MOVER (derecha)
# y su votante no se transfiere a RC, por lo que usarla como base inflaba el correísmo
# (caso Loja: base 29,5% vs. real 10,8%). Se usa solo lista 5 (FCS/RC) como linaje correísta
# y la 35 cae en "otros" (no se asigna a derecha).
CORRE = {2019: {"5"}, 2023: {"5"}}
IZQ = {2019: {"18", "12", "2", "17", "20"}, 2023: {"18", "12", "2", "17"}}
DER = {2019: {"6", "21", "23", "7", "19", "51", "3", "8", "4", "75", "1"},
       2023: {"6", "21", "23", "7", "19", "3", "8", "4", "75", "1", "33", "25"}}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _catalogo():
    p = next((f for f in glob.glob(os.path.join(RAW, "*rganizaciones*"))
              if f.lower().endswith(".sav")), None)
    d = pd.read_spss(p)
    d = d.rename(columns={"OP_NOMBRE": "nombre", "OP_SIGLAS": "siglas", "OP_LISTA": "lista"})
    d["lista"] = d["lista"].astype(str).str.split("-").str[0]  # cabeza
    d["n_nombre"] = d["nombre"].map(_norm)
    d["n_siglas"] = d["siglas"].map(_norm)
    return d


def mapa_lista_2019():
    """nombre/alianza normalizado -> lista (string)."""
    c = _catalogo()
    por_nombre = dict(zip(c["n_nombre"], c["lista"]))
    por_siglas = dict(zip(c["n_siglas"], c["lista"]))
    nombres = list(por_nombre.items())

    def f(nombre):
        n = _norm(nombre)
        if n in por_nombre:
            return por_nombre[n]
        # match por contención (el más largo)
        best = None
        for nn, lst in nombres:
            if nn and (nn in n or n in nn) and (best is None or len(nn) > len(best[0])):
                best = (nn, lst)
        if best:
            return best[1]
        # "LISTAS 6", "LISTA 21"
        m = re.search(r"LISTAS?\s*(\d{1,3})", n)
        if m:
            return str(int(m.group(1)))
        # prefijo tipo "6-MADERA..."
        m = re.match(r"^(\d{1,3})\s*-", n)
        if m:
            return str(int(m.group(1)))
        # siglas conocidas dentro del nombre
        for sig, lst in por_siglas.items():
            if sig and len(sig) >= 2 and re.search(r"\b%s\b" % re.escape(sig), n):
                return lst
        return None
    return f


def bloque(lista, anio, esquema):
    if lista is None:
        if esquema == "familias":
            return "LOCAL"
        return "resto" if esquema == "2bloques" else "otros"
    lst = str(lista)
    if esquema == "familias":
        return familia(lst)
    if esquema == "2bloques":
        return "correismo" if lst in CORRE[anio] else "resto"
    if esquema == "3bloques":            # correísmo / derecha / otros
        if lst in CORRE[anio]:
            return "correismo"
        return "derecha" if lst in DER[anio] else "otros"
    if esquema == "4bloques":            # correísmo / derecha / izquierda / otros
        if lst in CORRE[anio]:
            return "correismo"
        if lst in DER[anio]:
            return "derecha"
        return "izquierda" if lst in IZQ[anio] else "otros"
    return "otros"


def _fuente_2019(dig):
    p = rd.ruta(f"gaona_format/gaona_2019_seccional_{dig}_junta.csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, dtype=str, usecols=["cod_org_pol", "votos"])
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0).astype(int)
    return d


def cobertura(dig="d11_prefecto"):
    f = mapa_lista_2019()
    d = _fuente_2019(dig)
    if d is None:
        print("[!] falta", dig); return
    d = d.copy()
    d["lista"] = d["cod_org_pol"].map(f)
    tot = int(d["votos"].sum())
    mapeado = int(d.loc[d["lista"].notna(), "votos"].sum())
    print(f"\n== {dig} ==")
    print(f"  votos={tot:,} | con lista={mapeado:,} ({100*mapeado/tot:.1f}%)")
    for esq in ("familias", "2bloques", "3bloques"):
        bl = d["lista"].map(lambda x: bloque(x, 2019, esq))
        g = d.assign(bl=bl.values).groupby("bl")["votos"].sum().sort_values(ascending=False)
        print(f"  -- {esq}: " + ", ".join(f"{k}={100*v/tot:.1f}%" for k, v in g.head(8).items()))
    # top no mapeados
    nm = d[d["lista"].isna()].groupby("cod_org_pol")["votos"].sum().sort_values(ascending=False)
    print("  top no mapeados:")
    for k, v in nm.head(8).items():
        print(f"     {100*v/tot:5.2f}%  {k[:70]}")


def main():
    for dig in ("d11_prefecto", "d13_alcalde"):
        cobertura(dig)


if __name__ == "__main__":
    main()

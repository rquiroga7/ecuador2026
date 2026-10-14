# -*- coding: utf-8 -*-
"""
modelo/bloques.py — Agrupa las candidaturas en BLOQUES (partidos/movimientos).

En Ecuador las candidaturas cambian entre ciclos, pero las **organizaciones
políticas** persisten. El campo `lista` de los dumps del CNE codifica la lista (o
las listas, si es alianza) concatenando números de 3 dígitos:

    "005"               -> [5]            (Revolución Ciudadana)
    "018004035"         -> [18, 4, 35]    (alianza MUPP-PID-MOVER)
    "005072"            -> [5, 72]        (RC - Sí Podemos)

Definimos el **bloque** de una candidatura como su **lista principal** (la primera
de la alianza), que es la convención con que se identifica al movimiento cabeza.
Sobre ese bloque se mide el *swing* entre elecciones.

Uso:
    from modelo import bloques
    v = bloques.cargar_votos("prefecto", 2023)
    vb, tb = bloques.construir(v)
    bloques.guardar("prefecto", 2023, vb, tb)
"""

import os
import re

import pandas as pd

import rutas_datos as rd

LISTA_RE = re.compile(r"\d{3}")

# Etiqueta legible por lista (editable; los nombres completos salen de los datos).
FAMILIA = {
    "005": "RC", "033": "RETO", "006": "PSC", "018": "MUPP", "021": "CREO",
    "023": "SUMA", "001": "CD", "002": "UP", "003": "PSP", "004": "PID",
    "008": "Avanza", "012": "ID", "016": "AMIGO", "017": "PSE", "020": "DSí",
    "025": "Construye", "035": "MOVER", "072": "Sí Podemos", "100": "SUR",
}


def parsear_lista(s):
    """'018004035' -> ['018','004','035']"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return []
    return LISTA_RE.findall(str(s).replace("-", ""))


def bloque_principal(s):
    """Lista cabeza (primer número de 3 dígitos), o 'ZZZ' si no hay."""
    ls = parsear_lista(s)
    return ls[0] if ls else "ZZZ"


def cargar_votos(dignidad, anio=2023, bloque=None):
    p = rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    v = pd.read_csv(p, dtype=str)
    v["votos"] = v["votos"].astype(int)
    v["bloque"] = v["lista"].map(bloque_principal)
    return v


def construir(votos, etiquetas=True):
    """Añade `bloque` y devuelve (votos, tabla_bloques)."""
    v = votos.copy()
    if "bloque" not in v.columns:
        v["bloque"] = v["lista"].map(bloque_principal)

    tb = v.groupby("bloque", sort=False).agg(
        votos=("votos", "sum"),
        n_candidatos=("cod_candidato", "nunique"),
        n_listas=("lista", "nunique"),
        partido_modal=("partido", lambda s: s.mode().iloc[0] if len(s.mode()) else ""),
    ).reset_index()
    if etiquetas:
        tb["etiqueta"] = tb["bloque"].map(FAMILIA).fillna(tb["partido_modal"].str[:22])
    tb = tb.sort_values("votos", ascending=False).reset_index(drop=True)
    return v, tb


def guardar(dignidad, anio, votos_bloque, tabla_bloques):
    d = rd.ruta_dir("mesas")
    pv = os.path.join(d, f"bloques_{dignidad}_{anio}.csv.gz")
    pt = os.path.join(d, f"tabla_bloques_{dignidad}_{anio}.csv.gz")
    votos_bloque.groupby(["mesa_id", "loc_id", "cod_junta", "bloque"], sort=False)[
        "votos"].sum().reset_index().to_csv(pv, index=False, compression="gzip")
    tabla_bloques.to_csv(pt, index=False, compression="gzip")
    print(f"[OK] {dignidad} {anio}: {len(tabla_bloques)} bloques -> {pv}")
    return pv, pt


def _main():
    import sys
    anios = [int(a) for a in sys.argv[1:] if a.isdigit()] or [2023]
    for anio in anios:
        for dignidad in ["prefecto", "alcalde", "concejal_urbano", "concejal_rural"]:
            try:
                v, tb = construir(cargar_votos(dignidad, anio))
                guardar(dignidad, anio, v, tb)
            except FileNotFoundError:
                print(f"[!] sin datos: {dignidad} {anio}")
        v, tb = construir(cargar_votos("prefecto", anio))
        print(f"\n=== PREFECTO {anio}: bloques por votos nacionales ===")
        print(tb.head(20)[["bloque", "etiqueta", "votos", "n_candidatos"]].to_string(index=False))


if __name__ == "__main__":
    _main()

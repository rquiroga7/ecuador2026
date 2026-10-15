# -*- coding: utf-8 -*-
"""
datos/familias.py — Fuente única de verdad: número de lista → FAMILIA política.

Las candidaturas y las alianzas cambian entre elecciones, pero las **organizaciones
políticas** (familias) persisten. El modelo de proyección mide el *swing* por familia,
no por candidato, así que esta homologación es transversal a todo el proyecto.

Reglas:
  * La familia sigue la **identidad/linaje** del partido aunque cambie de nombre o de
    número de lista (p. ej. FCS-2019 → RC-2023 = `RC`; Democracia Sí → Futuro = `DSI`).
  * Movimientos puramente locales sin familia nacional → `LOCAL`.
  * Si no se sabe, `familia()` devuelve `LOCAL` (nunca revienta).

El mapa puede **sobreescribirse** sin tocar el código: si existe el XLSX curado por el
experto (`familias_ecuador_2019_2023_2026.xlsx`, hoja `Mapa_familias`, ver
`datos/exportar_familias.py`), las filas con la columna `familia` no vacía mandan.

Uso:
    from datos import familias
    familias.familia("018004035")          # -> 'MUPP'   (alianza, toma la cabeza)
    familias.familia("21-100")             # -> 'CREO'   (formato 2019 con guion)
    familias.a_familias(g)                 # pivote de partidos -> familias
    familias.mapa()                        # DataFrame (lista, familia) efectivo

CLI:
    python -m datos.familias               # muestra el mapa efectivo y si hay overrides
"""

import os
import re

import pandas as pd

import rutas_datos as rd

# ---------------------------------------------------------------------------
# Mapa por defecto: número de lista (canónico, sin ceros a la izquierda) -> familia.
# Cubre organizaciones nacionales de 2019, 2023 y 2026 conocidas.
# ---------------------------------------------------------------------------
FAMILIA = {
    "1": "CD", "2": "UP", "3": "PSP", "4": "PID", "5": "RC", "6": "PSC",
    "7": "ADN", "8": "Avanza", "12": "ID", "16": "AMIGO", "17": "PSE",
    "18": "MUPP", "20": "MF", "21": "CREO", "23": "SUMA", "25": "CONSTRUYE",
    "33": "RETO", "35": "MOVER", "70": "Todos", "72": "RC", "100": "SUR",
}

# Familias válidas (vocabulario del XLSX / desplegable). Alias del linaje correísta
# (AMIGO, PSE, UP, Todos) se mantienen separadas y se homologan en la hoja editable.
# Siglas alineadas con la tabla oficial de partidos/movimientos nacionales 2026.
VOCAB = ["RC", "PSC", "MUPP", "CREO", "SUMA", "ID", "UP", "PSP", "CD", "Avanza",
         "PSE", "MF", "MOVER", "CONSTRUYE", "PID", "AMIGO", "ADN", "RETO", "Todos",
         "LOCAL", "OTRO"]

XLSX_NOMBRE = "familias_ecuador_2019_2023_2026.xlsx"
HOJA_MAPA = "Mapa_familias"

_OVERRIDES_CACHE = {"mtime": None, "mapa": {}}


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
def normalizar_lista(lista):
    """Devuelve la **cabeza** de la(s) lista(s) como entero-string, o None.

    Acepta los formatos del CNE:
        "5" / "005" / 5        -> "5"
        "018004035"            -> "18"   (alianza 2023: 3 dígitos concatenados)
        "21-100"               -> "21"   (alianza 2019: guion)
        "ZZZ" / "" / None /NaN -> None
    """
    if lista is None:
        return None
    if isinstance(lista, float) and pd.isna(lista):
        return None
    s = str(lista).strip()
    if not s or s.lower() in ("nan", "none", "zzz"):
        return None
    if "-" in s:
        s = s.split("-")[0]
    d = re.sub(r"\D", "", s)
    if not d:
        return None
    if len(d) >= 3 and len(d) % 3 == 0:
        d = d[:3]
    return str(int(d))


def familia(lista, overrides=None):
    """Familia de una lista; `LOCAL` si es desconocida."""
    k = normalizar_lista(lista)
    if k is None:
        return "LOCAL"
    if overrides is None:
        overrides = overrides_efectivos()
    return overrides.get(k) or FAMILIA.get(k) or "LOCAL"


# ---------------------------------------------------------------------------
# Overrides del XLSX curado por el experto
# ---------------------------------------------------------------------------
def _ruta_xlsx(path=None):
    if path:
        return path
    p = rd.ruta(XLSX_NOMBRE)
    if os.path.exists(p):
        return p
    p2 = os.path.join(rd.REPO, XLSX_NOMBRE)
    return p2 if os.path.exists(p2) else None


def cargar_mapa_xlsx(path=None):
    """{lista_canónica: familia} de la hoja `Mapa_familias` (filas con `familia`).

    Ignora celdas vacías. Tolera que falten las columnas (devuelve {})."""
    path = _ruta_xlsx(path)
    if not path or not os.path.exists(path):
        return {}
    try:
        df = pd.read_excel(path, sheet_name=HOJA_MAPA, dtype=str)
    except Exception:
        return {}
    if "lista" not in df.columns or "familia" not in df.columns:
        return {}
    out = {}
    for lista, fam in zip(df["lista"], df["familia"]):
        if fam is None or (isinstance(fam, float) and pd.isna(fam)):
            continue
        fam = str(fam).strip()
        k = normalizar_lista(lista)
        if k and fam:
            out[k] = fam
    return out


def overrides_efectivos(path=None, refrescar=False):
    """Overrides del XLSX, cacheados por fecha de modificación del archivo."""
    p = _ruta_xlsx(path)
    mtime = os.path.getmtime(p) if p and os.path.exists(p) else None
    if refrescar or _OVERRIDES_CACHE["mtime"] != mtime:
        _OVERRIDES_CACHE["mapa"] = cargar_mapa_xlsx(p)
        _OVERRIDES_CACHE["mtime"] = mtime
    return _OVERRIDES_CACHE["mapa"]


# ---------------------------------------------------------------------------
# Transformaciones de tablas
# ---------------------------------------------------------------------------
def mapa(path=None):
    """DataFrame (lista, familia_sugerida, familia) con el mapa **efectivo**."""
    ov = overrides_efectivos(path)
    listas = sorted(set(FAMILIA) | set(ov), key=lambda x: int(x))
    return pd.DataFrame({
        "lista": listas,
        "familia_sugerida": [FAMILIA.get(k, "LOCAL") for k in listas],
        "familia": [ov.get(k) or FAMILIA.get(k, "LOCAL") for k in listas],
    })


def a_familias(g, overrides=None):
    """Colapsa las columnas de una tabla de partidos a columnas de FAMILIA.

    `g` es un DataFrame con columnas = números de lista (acepta 3 dígitos o enteros).
    Devuelve otro DataFrame con columnas = familias (suma de las listas de cada una).
    """
    if overrides is None:
        overrides = overrides_efectivos()
    cols = [familia(c, overrides) for c in g.columns]
    out = g.copy()
    out.columns = cols
    return out.T.groupby(level=0).sum().T


# ---------------------------------------------------------------------------
def _main():
    ov = overrides_efectivos(refrescar=True)
    m = mapa()
    print(f"[familias] {len(m)} listas | {len(ov)} overrides del XLSX "
          f"({_ruta_xlsx() or 'sin XLSX'})")
    print(m.to_string(index=False))


if __name__ == "__main__":
    _main()

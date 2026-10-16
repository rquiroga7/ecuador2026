# -*- coding: utf-8 -*-
"""
datos/distributivo.py — Electores habilitados por JUNTA desde el "Distributivo de
recintos electorales" del CNE.

El CNE publica el **Distributivo de Electores y Juntas Receptoras del Voto** (una fila
por *recinto* electoral) con el número de electores del recinto y cuántas juntas
tiene (por sexo, y el rango de numeración de cada sexo). Las juntas de un mismo
recinto son de tamaño ~constante, así que el padrón por junta se aproxima como

    electores_junta = electores_recinto / n_juntas_recinto

que es el padrón **por junta** que necesita el forense para la participación (mucho
mejor que repartir el padrón parroquial). Fuente y descarga:

    https://www.cne.gob.ec/download/distributivos-de-electores-y-juntas-receptoras-del-voto/

Producto (D:\\ecuador2026_data\\padron\\):
    electores_junta.csv.gz   clave `prov-cant-parroquia-zona-junta-sexo` -> electores

Uso:
    python -m datos.distributivo           # parsea el xlsx y escribe el csv
"""

import os
import glob
import numpy as np
import pandas as pd

import rutas_datos as rd

# Convención: `raw/distributivo_recintos_<anio>.xlsx` (un archivo por elección) o el
# genérico `raw/distributivo_recintos_cne.xlsx` (la edición vigente).
ARCHIVO = rd.ruta("raw/distributivo_recintos_cne.xlsx")
SALIDA = "padron/electores_junta.csv.gz"

RENOMBRE = {
    "CODIGO PROVINCIA": "prov", "CODIGO CANTON": "cant", "CODIGO PARROQUIA": "parr",
    "CODIGO ZONA": "zona", "JUN FEM": "jfem", "JUN MAS": "jmas", "NUM JUNR": "njun",
    "JUN INIF": "inif", "JUN FINF": "finf", "JUN INIM": "inim", "JUN FINM": "finm",
    "NUMERO ELECTORES": "electores",
}


def _archivo_de(anio=None, ruta=None):
    if ruta:
        return ruta
    if anio is not None:
        for p in (rd.ruta(f"raw/distributivo_recintos_{anio}.xlsx"),
                  rd.ruta(f"raw/distributivo_recintos_{anio}.xls")):
            if os.path.exists(p):
                return p
    return ARCHIVO


def _leer(ruta=None):
    ruta = ruta or ARCHIVO
    crudo = pd.read_excel(ruta, sheet_name="Consolidado", header=None, dtype=object)
    fila = None
    for i in range(min(20, len(crudo))):
        vals = [str(x).strip().upper() for x in crudo.iloc[i].tolist()]
        if "NUMERO ELECTORES" in vals:
            fila = i
            break
    if fila is None:
        raise ValueError("No encontré la cabecera (NUMERO ELECTORES) en el distributivo.")
    d = pd.read_excel(ruta, sheet_name="Consolidado", header=fila, dtype=object)
    d = d.rename(columns=RENOMBRE)
    faltan = [c for c in RENOMBRE.values() if c not in d.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el distributivo: {faltan}")
    for c in RENOMBRE.values():
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=["prov", "cant", "parr", "zona", "njun"])


def _z(s, n):
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).str.zfill(n)


def construir(d=None, ruta=None):
    """DataFrame por junta: key (`prov-cant-parroquia-zona-junta-sexo`) -> electores."""
    d = _leer(ruta) if d is None else d
    filas = []
    for r in d.itertuples():
        if not (r.njun and r.njun > 0) or not np.isfinite(r.electores):
            continue
        ej = float(r.electores) / float(r.njun)
        if np.isfinite(r.inif) and np.isfinite(r.finf):
            for j in range(int(r.inif), int(r.finf) + 1):
                filas.append((r.prov, r.cant, r.parr, r.zona, j, "F", ej))
        if np.isfinite(r.inim) and np.isfinite(r.finm):
            for j in range(int(r.inim), int(r.finm) + 1):
                filas.append((r.prov, r.cant, r.parr, r.zona, j, "M", ej))
    p = pd.DataFrame(filas, columns=["prov", "cant", "parr", "zona", "junta", "sexo",
                                     "electores"])
    p["key"] = (_z(p["prov"], 2) + "-" + _z(p["cant"], 3) + "-" + _z(p["parr"], 4)
                + "-" + _z(p["zona"], 2) + "-" + _z(p["junta"], 3) + "-" + p["sexo"])
    p = p.groupby("key", as_index=False)["electores"].mean()
    return p


def electores_junta(anio=None):
    """Serie `prov-cant-parroquia-zona-junta-sexo` -> electores habilitados.

    Usa el padrón del año pedido si existe; si no, el genérico (edición vigente).
    """
    rutas = []
    if anio is not None:
        rutas.append(rd.ruta(f"padron/electores_junta_{anio}.csv.gz"))
    rutas.append(rd.ruta(SALIDA))
    for p in rutas:
        if os.path.exists(p):
            d = pd.read_csv(p, dtype={"key": str})
            return d.set_index("key")["electores"]
    return pd.Series(dtype=float)


def construir_todo():
    """Parsea todos los `raw/distributivo_recintos_*.xlsx` a `padron/electores_junta[_anio].csv.gz`."""
    salidas = []
    for p in sorted(glob.glob(rd.ruta("raw/distributivo_recintos_*.xlsx"))):
        base = os.path.basename(p)
        import re
        m = re.search(r"(\d{4})", base)
        anio = m.group(1) if m else None
        df = construir(ruta=p)
        out = rd.ruta(f"padron/electores_junta_{anio}.csv.gz" if anio else SALIDA)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        df.to_csv(out, index=False, compression="gzip")
        salidas.append((base, out, len(df)))
        print(f"[OK] {base} -> {out} | juntas={len(df):,} "
              f"| electores={int(df['electores'].sum()):,}")
    return salidas


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Padrón por junta desde el distributivo CNE.")
    ap.add_argument("--anio", type=int, default=None)
    ap.add_argument("--archivo", default=None)
    ap.add_argument("--todos", action="store_true",
                    help="parsea todos los raw/distributivo_recintos_*.xlsx")
    a = ap.parse_args()
    if a.todos:
        construir_todo()
        return
    p = construir(ruta=_archivo_de(a.anio, a.archivo))
    out = rd.ruta(f"padron/electores_junta_{a.anio}.csv.gz" if a.anio else SALIDA)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p.to_csv(out, index=False, compression="gzip")
    print(f"[OK] {out} | juntas={len(p):,} | electores totales={int(p['electores'].sum()):,}")


if __name__ == "__main__":
    main()


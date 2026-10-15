# -*- coding: utf-8 -*-
"""
inferencia/web.py — Exporta las matrices de inferencia ecológica a `web/ei.json`.

El dashboard las muestra en la pestaña **Inferencia ecológica**. Cada par de
elecciones es una matriz theta[j,k] = P(votar/bastinerse del bloque k en el destino
| bloque j en el origen), estimada por EM a nivel parroquia.

Pares disponibles (según los CSV en `...\\ei\\`):
  * Prefecto  2019 → 2023
  * Alcalde   2019 → 2023
  * Presidencial 2021 → 2025

Uso:  python -m inferencia.web
"""

import os
import sys
import json

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd

PARES = [
    ("transicion_local_prefecto_2019_2023.csv", "Prefecto 2019 → 2023",
     "Seccionales · EM por parroquia"),
    ("transicion_local_alcalde_2019_2023.csv", "Alcalde 2019 → 2023",
     "Seccionales · EM por parroquia"),
    ("transicion_presidencial_2021_2025.csv", "Presidencial 2021 → 2025",
     "Generales · EM por parroquia"),
]


def _leer(archivo):
    p = rd.ruta(f"ei/{archivo}")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, index_col=0)
    d.index = [str(x) for x in d.index]
    d.columns = [str(x) for x in d.columns]
    return {"origen": list(d.index), "destino": list(d.columns),
            "matriz": d.fillna(0).round(1).values.tolist()}


def exportar(destino=None):
    pares = []
    for archivo, titulo, nota in PARES:
        m = _leer(archivo)
        if m:
            m.update({"id": archivo.rsplit(".", 1)[0], "titulo": titulo, "nota": nota})
            pares.append(m)
    doc = {"pares": pares,
           "nota": "Inferencia ecológica (EM) por parroquia. θ[j,k] = P(destino k | "
                   "origen j), en %. Estima la migración del voto entre fuerzas."}
    p = destino or os.path.join(rd.REPO, "web", "ei.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[OK] {p} ({len(pares)} pares: "
          + ", ".join(x['titulo'] for x in pares) + ")")
    return doc


if __name__ == "__main__":
    exportar()

# -*- coding: utf-8 -*-
"""
vivo/recapturar_circ.py — Recaptura focalizada del portal app01 (resultados2025):

  * **Asambleístas Provinciales por Circunscripción** en Guayas(9)/Manabí(13)/
    Pichincha(17). El crawl general los bajó vacíos porque en esas provincias la
    dignidad NO es 13 (Asambleístas Provinciales) sino **14 (por circunscripción)**,
    y hay que fijar la circunscripción (Guayas c1–c4, Manabí c1–c2, Pichincha c1–c4).
    Además los códigos de cantón/parroquia son **por circunscripción**, así que se
    enumera la jerarquía para cada circ.
  * **Dignidad 15 (Asambleístas del Exterior)** para 26/27/28 (si aún no están).

Salida: `...\\crudo\\app01\\resultados2025\\14\\<prov>-<cant>-<parr>-<zona>.json`
Cortés y reanudable. Uso:
    set PLAYWRIGHT_BROWSERS_PATH=D:\\ecuador2026_data\\pw-browsers
    python -m vivo.recapturar_circ
"""

import os
import json
import csv
import argparse
from datetime import datetime

import rutas_datos as rd
from vivo import captura_app01 as C

PROVS_CIRC = ("9", "13", "17")
EXTERIOR = ("26", "27", "28")
CIRCS = ("1", "2", "3", "4")


def _body(dig, prov, circ, cant, parr, zona):
    return {"objConsulta": {"Dignidad": dig, "AbrirActa": False,
            "Provincia": prov, "Circunscripcion": circ, "Canton": cant,
            "Parroquia": parr, "Zona": zona, "Junta": "-1",
            "nomDignidad": "", "strJurisdiccion": "", "tokenCaptcha": "",
            "Pregunta": "-1"}}


def _nom(prov, cant, parr, zona):
    return f"{prov}-{cant}-{parr}-{zona}.json"


def _ya_tiene(ruta):
    if not os.path.exists(ruta):
        return False
    try:
        return bool(json.load(open(ruta, encoding="utf-8")).get("datos"))
    except Exception:
        return False


def _recintos_circ(ctx, tok, prov):
    """{key: circ} enumerando la jerarquía para cada circunscripción."""
    out = {}
    for circ in CIRCS:
        for cant in C._cat(ctx, tok, "Canton", {"intProvincia": prov,
                                                "intCircunscripcion": circ}):
            for parr in C._cat(ctx, tok, "Parroquia", {"intCanton": cant["value"],
                                                       "intCircunscripcion": circ}):
                for zona in C._cat(ctx, tok, "Zona", {"intParroquia": parr["value"],
                                                      "intCircunscripcion": circ}):
                    out[_nom(prov, cant["value"], parr["value"], zona["value"])] = circ
    return out


def recapturar(pmin=2.5, pmax=6.0):
    from playwright.sync_api import sync_playwright
    manif = os.path.join(rd.ruta_dir("vivo"), "manifiesto_app01_circ14.csv")
    nuevo = not os.path.exists(manif)
    fm = open(manif, "a", newline="", encoding="utf-8")
    w = csv.writer(fm)
    if nuevo:
        w.writerow(["capturado_en", "dignidad", "circ", "key", "ok", "archivo"])

    with sync_playwright() as p:
        ctx, page = C._abrir(p, False)
        tok = C._preparar(page)

        # 1) dignidad 14 por circunscripción
        for prov in PROVS_CIRC:
            recintos = _recintos_circ(ctx, tok, prov)
            pend = [(k, c) for k, c in recintos.items()
                    if not _ya_tiene(os.path.join(C._crudo_dir("14"), k))]
            print(f"[14] prov {prov}: {len(recintos)} recintos, {len(pend)} pendientes")
            for i, (k, circ) in enumerate(pend, 1):
                prov_, cant, parr, zona = k[:-5].split("-")
                ruta = os.path.join(C._crudo_dir("14"), k)
                C._dormir(pmin, pmax)
                try:
                    js = C._consulta(page, _body("14", prov_, circ, cant, parr, zona))
                except Exception as e:
                    print(f"  [!] {k}: {e}"); continue
                if js.get("datos"):
                    json.dump(js, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    w.writerow([datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                                "14", circ, k, 1, ruta]); fm.flush()
                if i % 20 == 0:
                    print(f"  {i}/{len(pend)} …")

        # 2) dignidad 15 exterior
        cp = next((rd.ruta(f"vivo/{n}") for n in ("catalogo_app01_2025.json",
                  "catalogo_app01_resultados2025.json")
                  if os.path.exists(rd.ruta(f"vivo/{n}"))), None)
        cat = json.load(open(cp, encoding="utf-8")) if cp else {}
        pend15 = [z for z in C._zonas_de(cat) if z["prov"] in EXTERIOR
                  and not _ya_tiene(os.path.join(C._crudo_dir("15"), _nom(
                      z["prov"], z["cant"], z["parr"], z["zona"])))]
        print(f"[15 exterior] {len(pend15)} pendientes")
        for z in pend15:
            ruta = os.path.join(C._crudo_dir("15"), _nom(z["prov"], z["cant"],
                                                          z["parr"], z["zona"]))
            for circ in ("-1", "1", "2", "3"):
                C._dormir(pmin, pmax)
                try:
                    js = C._consulta(page, _body("15", z["prov"], circ, z["cant"],
                                                 z["parr"], z["zona"]))
                except Exception:
                    continue
                if js.get("datos"):
                    json.dump(js, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    w.writerow([datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                                "15", circ, _nom(z["prov"], z["cant"], z["parr"], z["zona"]),
                                1, ruta]); fm.flush()
                    break
        ctx.close()
    fm.close()
    print("[OK] recaptura d14 (circ) + d15 (exterior) terminada")


def main():
    ap = argparse.ArgumentParser(description="Recaptura d14 (por circunscripción) y d15.")
    ap.add_argument("--pmin", type=float, default=2.5)
    ap.add_argument("--pmax", type=float, default=6.0)
    a = ap.parse_args()
    recapturar(a.pmin, a.pmax)


if __name__ == "__main__":
    main()

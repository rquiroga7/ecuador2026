# -*- coding: utf-8 -*-
"""
vivo/scraper_cne.py — Captura del escrutinio en vivo del CNE (por junta + timestamp).

Los portales del CNE son efímeros: se levantan el día de la elección y se apagan
después (p. ej. `resultados2021.cne.gob.ec` y `resultados2025.cne.gob.ec` ya no
resuelven). Por eso el scraper es **configurable** y su prioridad es **guardar la
respuesta cruda** de cada consulta junto con nuestro reloj (`capturado_en`), para
normalizar después. Nunca se pierde información.

Adaptadores (según la elección):
  * `post2021`  — POST form a `.../Home/ConsultarResultados`
                  con `request[intCodDignidad|intCodProvincia|intCodCanton|intCodCircunscripcion]`.
  * `certero`   — GET JSON a `.../certero-cne/api/v1/total-provincias?codDignidad=&codProvincia=`
                  (requiere `Authorization: Bearer <JWT>` corto).

Uso:
    python -m vivo.scraper_cne --base "https://<host>/Home/ConsultarResultados" \
        --patron post2021 --una-pasada
    python -m vivo.scraper_cne --base "https://<host>/certero-cne/api/v1" \
        --patron certero --token "<JWT>" --dignidades 11,13,14

Salida (D:\\ecuador2026_data\\vivo\\):
    crudo/<AAAAMMDD-HHMMSS>/<patron>-<dign>-<prov>.json
    manifiesto.csv                (capturado_en, patron, dignidad, provincia, ok, bytes, archivo)
"""

import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime

import requests

import rutas_datos as rd

# Provincias del CNE (orden alfabético) + exterior + "todas"
PROVINCIAS = [-1] + list(range(1, 25)) + [26, 27, 28]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
           "Accept": "application/json, text/plain, */*"}


def consultar_post2021(host, dignidad, provincia, circunscripcion=-1, session=None):
    """POST form al API estilo 2021. Devuelve (ok, payload_dict_o_texto)."""
    s = session or requests
    body = {
        "request[intCodDignidad]": dignidad,
        "request[intCodProvincia]": provincia,
        "request[intCodCanton]": -1,
        "request[intCodCircunscripcion]": circunscripcion,
    }
    r = s.post(host, data=body, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return False, {"_http": r.status_code, "_texto": r.text[:1000]}
    try:
        return True, r.json()
    except ValueError:
        return True, {"_texto": r.text}


def consultar_certero(host, dignidad, provincia, token=None, session=None):
    """GET JSON al API estilo 2023 (`certero-cne`)."""
    s = session or requests
    url = f"{host.rstrip('/')}/total-provincias"
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = s.get(url, params={"codDignidad": dignidad, "codProvincia": provincia},
              headers=headers, timeout=20)
    if r.status_code != 200:
        return False, {"_http": r.status_code, "_texto": r.text[:1000]}
    try:
        return True, r.json()
    except ValueError:
        return True, {"_texto": r.text}


def _manifiesto_path():
    return rd.ruta("vivo/manifiesto.csv")


def guardar(destino, patron, dignidad, provincia, ok, payload):
    os.makedirs(destino, exist_ok=True)
    archivo = os.path.join(destino, f"{patron}-{dignidad}-{provincia}.json")
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    p = _manifiesto_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    nuevo = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["capturado_en", "patron", "dignidad", "provincia", "ok",
                        "bytes", "archivo"])
        w.writerow([datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                    patron, dignidad, provincia, int(ok),
                    os.path.getsize(archivo), archivo])


def barrido(host, patron, dignidades, provincias, token=None, intervalo=30.0,
            pausa=0.5, una_pasada=True):
    s = requests.Session()
    carpeta = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(rd.ruta_dir("vivo"), "crudo", carpeta)
    print(f"[*] Captura -> {destino} | patron={patron} | dignidades={dignidades}")
    while True:
        n_ok = 0
        for dign in dignidades:
            for prov in provincias:
                try:
                    if patron == "certero":
                        ok, payload = consultar_certero(host, dign, prov, token, s)
                    else:
                        ok, payload = consultar_post2021(host, dign, prov, -1, s)
                except requests.RequestException as e:
                    ok, payload = False, {"_error": str(e)}
                guardar(destino, patron, dign, prov, ok, payload)
                n_ok += int(ok)
                time.sleep(pausa)
        print(f"[{datetime.now():%H:%M:%S}] capturas ok={n_ok}/{len(dignidades)*len(provincias)}")
        if una_pasada:
            return destino
        time.sleep(intervalo)


def main():
    ap = argparse.ArgumentParser(description="Captura en vivo del CNE (junta+corte).")
    ap.add_argument("--base", required=True, help="URL base o endpoint POST 2021.")
    ap.add_argument("--patron", choices=["post2021", "certero"], default="post2021")
    ap.add_argument("--token", default=os.environ.get("CNE_TOKEN", ""))
    ap.add_argument("--dignidades", default="11", help="códigos separados por coma")
    ap.add_argument("--provincias", default="-1", help="códigos o 'todas'")
    ap.add_argument("--intervalo", type=float, default=30.0)
    ap.add_argument("--una-pasada", action="store_true")
    args = ap.parse_args()

    dignidades = [int(x) for x in args.dignidades.split(",") if x.strip()]
    if args.provincias == "todas":
        provincias = PROVINCIAS
    else:
        provincias = [int(x) for x in args.provincias.split(",") if x.strip()]
    barrido(args.base, args.patron, dignidades, provincias, token=args.token or None,
            intervalo=args.intervalo, una_pasada=args.una_pasada)


if __name__ == "__main__":
    main()

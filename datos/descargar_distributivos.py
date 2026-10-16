# -*- coding: utf-8 -*-
"""
datos/descargar_distributivos.py — Descarga los "Distributivos de Electores y Juntas
Receptoras del Voto" del CNE (electores por recinto → padrón por junta).

El CNE publica, por elección, un distributivo de recintos con el número de electores y
el rango de juntas de cada recinto. Es la fuente del padrón **por junta** que usa el
forense para la participación (`datos.distributivo`).

IMPORTANTE: el portal `cne.gob.ec` está detrás de **Incapsula**, que exige resolver un
desafío JS. `requests`/`Invoke-WebRequest` normalmente reciben la página del desafío en
vez del archivo. Este script:
  * intenta la descarga con cabeceras de navegador;
  * detecta el desafío (HTML en vez de xlsx) y avisa;
  * deja el archivo en `raw/distributivo_recintos_<anio>.xlsx` cuando lo consigue.
Si falla, descargá el archivo manualmente desde la página indicada y guardalo con ese
nombre; luego corré `python -m datos.distributivo --todos`.

Fuentes conocidas (por elección → página de descarga):
    * 2027 (seccionales)  https://www.cne.gob.ec/distributivo-de-recintos-electorales/
                          (y "Distributivos de Electores y Juntas Receptoras del Voto")
    * 2023 (seccionales)  https://www.cne.gob.ec/distributivo-de-recintos-electorales/
                          (archivo publicado en sep-2022) · /distributivo-electores/
    * 2021 (generales)    https://www.cne.gob.ec/images/d/2020/elecciones_generales_2021/
                          distributivo_nacional_de_recintos_electorales.pdf   (sin electores)
    * 2019 / 2025         (buscar en https://www.cne.gob.ec/registro-electoral-y-circunscripciones/
                          y https://www.cne.gob.ec/estadisticas/bases-de-datos/)

Uso:
    python -m datos.descargar_distributivos 2023 2027 --url "https://.../?wpdmdl=29585"
"""

import os
import sys
import argparse

import requests

import rutas_datos as rd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
              "application/vnd.ms-excel,application/zip,*/*",
    "Referer": "https://www.cne.gob.ec/",
}

FUENTES = {
    2027: "https://www.cne.gob.ec/download/distributivos-de-electores-y-juntas-receptoras-del-voto/",
    2023: "https://www.cne.gob.ec/download/distributivo-de-recintos-electorales/",
    2021: "https://www.cne.gob.ec/images/d/2020/elecciones_generales_2021/"
          "distributivo_nacional_de_recintos_electorales.pdf",
}


def _es_xlsx(datos):
    # xlsx/xls = ZIP ("PK") ; algunos .xls son OLE2 (D0 CF 11 E0)
    return datos[:2] == b"PK" or datos[:4] == b"\xd0\xcf\x11\xe0"


def descargar(anio, url=None, destino=None):
    url = url or FUENTES.get(anio)
    if not url:
        print(f"[!] No tengo URL para {anio}. Pasá --url.")
        return None
    destino = destino or rd.ruta(f"raw/distributivo_recintos_{anio}.xlsx")
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    except requests.RequestException as e:
        print(f"[!] {anio}: error de red ({e})")
        return None
    if r.status_code != 200 or not _es_xlsx(r.content):
        print(f"[!] {anio}: no se obtuvo el archivo (posible desafío Incapsula). "
              f"Descargalo manualmente desde:\n    {url}\n"
              f"    y guardalo como: {destino}")
        return None
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(r.content)
    print(f"[OK] {destino} ({len(r.content):,} bytes)")
    return destino


def main():
    ap = argparse.ArgumentParser(description="Descarga distributivos de recintos CNE.")
    ap.add_argument("anios", nargs="*", type=int, default=[2027])
    ap.add_argument("--url", default=None, help="URL directa (wpdmdl) para un año")
    a = ap.parse_args()
    anios = a.anios or [2027]
    ok = False
    for an in anios:
        ok = bool(descargar(an, a.url if len(anios) == 1 else None)) or ok
    print("[i] Si descargaste manualmente, corré: python -m datos.distributivo --todos")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
vivo/azure.py — Espejo incremental de la share de Azure Files del CNE.

El CNE distribuyó resultados a medios por **Azure Files**
(`https://stresultadoscne2025.file.core.windows.net/{cne-medios,cne-ops}`). Los SAS
de prueba de `Claves_Azure_File_Storage_test.txt` ya expiraron; para 2026 hay que
obtener una SAS vigente.

Este módulo:
  * lista la share y **baja solo lo nuevo/cambiado** (por tamaño + ETag),
  * guarda un registro `(ruta, capturado_en, etag, bytes)` para reproducibilidad,
  * prioriza **no depender** de Azure: es un canal más (junto al scraper del API).

Requiere `azure-storage-file-share` (`pip install azure-storage-file-share`).

Uso:
  set AZURE_SAS=https://st....file.core.windows.net/<share>?<sas>
  python -m vivo.azure --listar
  python -m vivo.azure --sincronizar --destino crudo_azure
"""

import os
import csv
import sys
import argparse
from datetime import datetime

import rutas_datos as rd


def _creds():
    sas = os.environ.get("AZURE_SAS", "").strip()
    if sas:
        return sas
    # intento de leer de la carpeta de claves del repo (si existiera con nombre nuevo)
    return None


def _clientes(sas_url):
    """Devuelve (service_client, share_client, share, base_url)."""
    from azure.storage.fileshare import ShareServiceClient
    from urllib.parse import urlparse
    u = urlparse(sas_url)
    cuenta_url = f"{u.scheme}://{u.netloc}"
    partes = u.path.strip("/").split("/")
    share = partes[0] if partes else ""
    service = ShareServiceClient(account_url=cuenta_url, credential="?" + u.query)
    return service, service.get_share_client(share), share, cuenta_url


def _registro_path():
    return rd.ruta("vivo/azure_registro.csv")


def _registro():
    p = _registro_path()
    if not os.path.exists(p):
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["ruta"]: r for r in csv.DictReader(f)}


def _anotar(filas):
    p = _registro_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    nuevo = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["ruta", "capturado_en", "etag", "bytes", "archivo"])
        w.writerows(filas)


def listar(sas_url, ruta=""):
    _, share, _, _ = _clientes(sas_url)
    d = share.get_directory_client(ruta) if ruta else share
    for item in d.list_files_and_directories():
        tipo = "dir" if item.get("is_directory") else "file"
        print(f"{tipo:4} {item['size']:>12} {item['name']}")


def sincronizar(sas_url, destino, ruta=""):
    _, share, _, _ = _clientes(sas_url)
    reg = _registro()
    out = rd.ruta_dir(destino)
    filas = []
    d = share.get_directory_client(ruta) if ruta else share
    for item in d.list_files_and_directories():
        if item.get("is_directory"):
            continue
        name = item["name"]
        etag = item.get("etag") or (item.get("properties") or {}).get("etag")
        prev = reg.get(name)
        if prev and prev.get("etag") == str(etag):
            continue
        local = os.path.join(out, name.replace("/", "__"))
        with open(local, "wb") as f:
            f.write(share.get_file_client(name).download_file().readall())
        print(f"[+] {name} ({item['size']} B)")
        filas.append([name,
                      datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                      etag, item["size"], local])
    if filas:
        _anotar(filas)
    print(f"[OK] {len(filas)} archivos nuevos/cambiados -> {out}")


def main():
    ap = argparse.ArgumentParser(description="Espejo de Azure Files del CNE.")
    ap.add_argument("--sas", default=_creds(), help="SAS completa (o env AZURE_SAS).")
    ap.add_argument("--ruta", default="", help="subcarpeta dentro de la share")
    ap.add_argument("--destino", default="crudo_azure")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--sincronizar", action="store_true")
    args = ap.parse_args()
    if not args.sas:
        print("[-] Falta la SAS (--sas o AZURE_SAS). Consíguela vigente para 2026.")
        sys.exit(2)
    if args.listar:
        listar(args.sas, args.ruta)
    if args.sincronizar:
        sincronizar(args.sas, args.destino, args.ruta)
    if not (args.listar or args.sincronizar):
        ap.print_help()


if __name__ == "__main__":
    main()

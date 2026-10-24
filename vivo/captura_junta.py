# -*- coding: utf-8 -*-
r"""
vivo/captura_junta.py — Baja resultados a nivel **JUNTA (mesa single-sex)** de un
portal app01 (SIER), enumerando zona → junta vía `CatalogoJuntaJson` y consultando
`ConsultaInformacionResultados` por junta.

La junta del portal equivale a la mesa del dump histórico: el catálogo las etiqueta
"1F"/"1M" (sexo). Sirve para 2025 (`resultados2025`, dignidad 11 presidente) y 2023
general anticipada 1ª vuelta (`resultados2023_anticipadas`).

Cortés y reanudable. Uso:
    set PLAYWRIGHT_BROWSERS_PATH=D:\\ecuador2026_data\\pw-browsers
    python -m vivo.captura_junta --base https://app01.cne.gob.ec/resultados2025 --dignidad 11
"""

import os
import json
import glob
import random
import time
import argparse
from datetime import datetime

import rutas_datos as rd
from vivo import captura_app01 as C

# catálogo (prov→cant→parr→zona) por portal
CATALOGOS = {
    "resultados2025": "catalogo_app01_2025.json",
    "resultados2023_anticipadas": "catalogo_app01_resultados2023_anticipadas.json",
}


def _catalogo(base):
    tag = os.path.basename(base.rstrip("/"))
    cands = [CATALOGOS.get(tag), f"catalogo_app01_{tag}.json",
             f"catalogo_app01_{tag.replace('resultados', '')}.json"]
    for c in cands:
        if c and os.path.exists(rd.ruta("vivo/" + c)):
            return rd.ruta("vivo/" + c)
    hits = glob.glob(rd.ruta(f"vivo/catalogo_app01_*{tag.split('_')[-1]}*.json"))
    return hits[0] if hits else None


def crawl(base, dignidad="11", pmin=1.5, pmax=4.0, maximo=None):
    from playwright.sync_api import sync_playwright
    C.PORTAL = base.rstrip("/")
    tag = os.path.basename(C.PORTAL)
    catf = _catalogo(base)
    if not catf:
        print(f"[!] no encuentro catálogo para {tag}"); return
    cat = json.load(open(catf, encoding="utf-8"))
    zonas = list(C._zonas_de(cat))
    outdir = os.path.join(rd.ruta_dir("vivo"), "crudo", "app01", tag, f"{dignidad}_junta")
    os.makedirs(outdir, exist_ok=True)
    manif = os.path.join(rd.ruta_dir("vivo"), f"manifiesto_junta_{tag}_{dignidad}.csv")
    nuevo = not os.path.exists(manif)
    fm = open(manif, "a", newline="", encoding="utf-8")
    import csv
    w = csv.writer(fm)
    if nuevo:
        w.writerow(["capturado_en", "prov", "cant", "parr", "zona", "junta", "genero",
                    "ok", "archivo"])

    print(f"[junta] {tag} dig={dignidad} | zonas={len(zonas)} | salida={outdir}")
    zdone_p = os.path.join(rd.ruta_dir("vivo"), f"juntas_zonas_done_{tag}_{dignidad}.txt")
    zdone = set(open(zdone_p, encoding="utf-8").read().split()) if os.path.exists(zdone_p) else set()
    fz = open(zdone_p, "a", encoding="utf-8")
    print(f"[junta] zonas ya completas (se saltan sin catálogo): {len(zdone)}")
    hechas = 0
    with sync_playwright() as p:
        ctx, page = C._abrir(p, False)
        tok = C._preparar(page)
        for z in zonas:
            zkey = f'{z["prov"]}-{z["cant"]}-{z["parr"]}-{z["zona"]}'
            if zkey in zdone:
                continue
            if maximo and hechas >= maximo:
                break
            juntas = C._cat(ctx, tok, "Junta", {"intZona": z["zona"],
                                                "intParroquia": z["parr"],
                                                "intCircunscripcion": 0})
            for j in juntas:
                if maximo and hechas >= maximo:
                    break
                key = f'{z["prov"]}-{z["cant"]}-{z["parr"]}-{z["zona"]}-{j["value"]}'
                ruta = os.path.join(outdir, key + ".json")
                if os.path.exists(ruta):
                    continue
                C._dormir(pmin, pmax)
                try:
                    js = C._consulta(page, {"objConsulta": {
                        "Dignidad": dignidad, "AbrirActa": False,
                        "Provincia": z["prov"], "Circunscripcion": "-1",
                        "Canton": z["cant"], "Parroquia": z["parr"],
                        "Zona": z["zona"], "Junta": j["value"],
                        "nomDignidad": "", "strJurisdiccion": "", "tokenCaptcha": "",
                        "Pregunta": "-1"}})
                except Exception as e:
                    print(f"  [!] {key}: {e}"); continue
                ok = not js.get("Error", False)
                tmp = ruta + ".part"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(js, fh, ensure_ascii=False)
                os.replace(tmp, ruta)   # escritura atómica (reanudable sin archivos truncados)
                w.writerow([datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                            z["prov"], z["cant"], z["parr"], z["zona"], j["value"],
                            j["text"], int(ok), ruta])
                fm.flush()
                hechas += 1
                if hechas % 50 == 0:
                    print(f"  {hechas} juntas… ({key})")
            jkeys = [f'{zkey}-{j["value"]}.json' for j in juntas]
            if jkeys and all(os.path.exists(os.path.join(outdir, k)) for k in jkeys):
                fz.write(zkey + "\n"); fz.flush(); zdone.add(zkey)
        ctx.close()
    fm.close(); fz.close()
    print(f"[OK] {tag} dig={dignidad}: {hechas} juntas nuevas -> {outdir}")


def main():
    ap = argparse.ArgumentParser(description="Resultados por JUNTA (portal app01).")
    ap.add_argument("--base", required=True)
    ap.add_argument("--dignidad", default="11")
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--pmin", type=float, default=1.5)
    ap.add_argument("--pmax", type=float, default=4.0)
    a = ap.parse_args()
    crawl(a.base, a.dignidad, a.pmin, a.pmax, a.max)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
r"""
vivo/captura_app01.py — Captura **cortés** de los portales de resultados del CNE
detrás de Incapsula (familia `app01`: `resultados2019`, `resultados2025`, `resultadosjp`).

Por qué: a nivel de **junta** (⇒ recinto/zona) los resultados 2019/2025 **no** están en
las bases `.sav` (parroquia×sexo); solo están en el portal. Un `requests` simple no
sirve (Incapsula responde un challenge JS) → usamos un navegador real (Playwright), que
sí lo resuelve. Cortesía: 1 navegador, 1 hilo, pausas aleatorias, backoff, tope por
corrida y estado reanudable, para no gatillar baneo de IP.

Hallazgos (resultados2025, MVC + anti-CSRF, **sin captcha**):
  * `POST /resultados2025/Resultados/CatalogoProvinciaJson`        (form)
  * `POST /resultados2025/Resultados/CatalogoCantonJson`      intProvincia, intCircunscripcion
  * `POST /resultados2025/Resultados/CatalogoParroquiaJson`   intCanton, intCircunscripcion
  * `POST /resultados2025/Resultados/CatalogoZonaJson`        intParroquia, intCircunscripcion
  * `POST /resultados2025/Resultados/ConsultaInformacionResultados`  (JSON)
        body: {"objConsulta":{"Dignidad","Provincia","Circunscripcion","Canton",
                              "Parroquia","Zona","Junta","nomDignidad","Pjurisdiccion",
                              "tokenCaptcha":"","Pregunta":"-1"}}
        Devuelve JSON con `datos` (votos por partido del nivel consultado),
        `objInformacionResultados` (electores, procesadas, …), y parciales HTML.
        **Agrega al nivel más específico fijado**: con `Zona` fijada y `Junta=-1`
        devuelve el agregado del **recinto**.
  * Todo requiere el header `__requestverificationtoken` (valor del input oculto).

NOTA (resultados2019): ese portal es ASP.NET WebForms + DevExpress + **reCAPTCHA** y
sin API JSON; no se automatiza igual. Requiere flujo human-in-the-loop (`--headed`).

Uso (exporta el path de navegadores):
    set PLAYWRIGHT_BROWSERS_PATH=D:\ecuador2026_data\pw-browsers
    python -m vivo.captura_app01 recon   --url https://app01.cne.gob.ec/resultados2025
    python -m vivo.captura_app01 catalogo                        # enumera prov/cant/parr/zona
    python -m vivo.captura_app01 crawl --dignidad 11 --max 50    # muestra de 50 zonas
    python -m vivo.captura_app01 crawl --dignidad 11             # todas las zonas (lento)
"""

import os
import csv
import sys
import json
import time
import random
import argparse
from urllib.parse import urlparse
from datetime import datetime

import rutas_datos as rd

DEFAULT_BROWSERS = r"D:\ecuador2026_data\pw-browsers"
BASE2025 = "https://app01.cne.gob.ec/resultados2025"
# Portal objetivo (configurable con --base). Misma app SIER para:
#   resultados2025 · resultados2023_anticipadassv · resultados2023 (seccionales)
PORTAL = BASE2025
TAG = "resultados2025"


def _tag(portal=None):
    return os.path.basename((portal or PORTAL).rstrip("/"))


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DIGNIDADES = {"11": "PRESIDENTE Y VICEPRESIDENTE",
              "13": "ASAMBLEISTAS PROVINCIALES",
              "12": "ASAMBLEISTAS NACIONALES", "16": "PARLAMENTARIOS ANDINOS"}


# ---------------------------------------------------------------------------
def _perfil_dir(portal=None):
    d = os.path.join(rd.ruta_dir("vivo"), f"perfil_{_tag(portal)}")
    os.makedirs(d, exist_ok=True)
    return d


def _crudo_dir(sub, portal=None):
    d = os.path.join(rd.ruta_dir("vivo"), "crudo", "app01", _tag(portal), sub)
    os.makedirs(d, exist_ok=True)
    return d


def _dormir(pmin, pmax):
    t = random.uniform(pmin, pmax)
    time.sleep(t)


def _abrir(p, headed=False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", DEFAULT_BROWSERS)
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=_perfil_dir(), headless=not headed, locale="es-EC",
        user_agent=UA, viewport={"width": 1366, "height": 768})
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def _preparar(page, url=None, intentos=15):
    """Pasa Incapsula y devuelve el token anti-CSRF."""
    page.goto(url or PORTAL, wait_until="domcontentloaded", timeout=90000)
    for _ in range(intentos):
        page.wait_for_timeout(2000)
        try:
            if "_Incapsula_Resource" not in page.content():
                break
        except Exception:
            pass
    tok = page.eval_on_selector(
        "input[name=__RequestVerificationToken]", "e=>e.value")
    return tok


def _headers(tok):
    return {"__requestverificationtoken": tok, "x-requested-with": "XMLHttpRequest",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "origin": "https://app01.cne.gob.ec", "referer": PORTAL}


def _lista(j):
    """Normaliza la respuesta de un catálogo a [{value,text}]."""
    if isinstance(j, list):
        it = j
    elif isinstance(j, dict):
        it = next((v for v in j.values() if isinstance(v, list)), [])
    else:
        it = []
    out = []
    for x in it:
        if isinstance(x, dict):
            val = next((x[k] for k in ("intCodigo", "value", "Value", "id", "codigo")
                        if k in x), None)
            txt = next((x[k] for k in ("strNombre", "text", "Text", "nombre", "descripcion")
                        if k in x), None)
            out.append({"value": str(val), "text": str(txt) if txt is not None else ""})
        else:
            out.append({"value": str(x), "text": str(x)})
    return out


def _cat(ctx, tok, nombre, datos, pmin=0.4, pmax=1.0):
    _dormir(pmin, pmax)
    r = ctx.request.post(f"{PORTAL}/Resultados/Catalogo{nombre}Json",
                         form=datos, headers=_headers(tok), timeout=60000)
    return _lista(r.json())


def _consulta(page, body):
    """Consulta vía `fetch` in-page (el ctx.request no supera el anti-CSRF)."""
    path = urlparse(PORTAL).path.rstrip("/")
    js = ('async b => { const t=document.querySelector('
          '"input[name=__RequestVerificationToken]").value;'
          'const r=await fetch("%s/Resultados/ConsultaInformacionResultados",'
          '{method:"POST",headers:{"Content-Type":"application/json",'
          '"__RequestVerificationToken":t},body:JSON.stringify(b)});'
          'return await r.json(); }') % path
    return page.evaluate(js, body)


# ---------------------------------------------------------------------------
def recon(url=None, headed=False):
    from playwright.sync_api import sync_playwright
    url = url or PORTAL
    with sync_playwright() as p:
        ctx, page = _abrir(p, headed)
        tok = _preparar(page, url)
        print(f"[recon] {url} | token={'sí' if tok else 'no'} | titulo={page.title()!r}")
        prov = _cat(ctx, tok, "Provincia", {})
        print("provincias:", prov[:6], "... total", len(prov))
        ctx.close()


def catalogo(headed=False, salida=None, solo_prov=None):
    """Enumera provincia→cantón→parroquia→zona y lo guarda en JSON.

    `solo_prov`: lista de códigos de provincia para probar/limitar (p. ej. ["1"]).
    """
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        ctx, page = _abrir(p, headed)
        tok = _preparar(page)
        # las provincias vienen embebidas en el <select> (no hay endpoint JSON)
        provincias = [{"value": v, "text": t} for v, t in page.eval_on_selector_all(
            "#ddlProvincia option", "els=>els.filter(e=>e.value).map(e=>[e.value,e.text.trim()])")]
        if solo_prov:
            provincias = [x for x in provincias if x["value"] in solo_prov]
        print(f"[cat] {len(provincias)} provincias")
        for i, pr in enumerate(provincias, 1):
            datos = {"intProvincia": pr["value"], "intCircunscripcion": 0}
            cants = _cat(ctx, tok, "Canton", datos)
            out[pr["value"]] = {"text": pr["text"], "cantones": {}}
            for ca in cants:
                d2 = {"intCanton": ca["value"], "intCircunscripcion": 0}
                parrs = _cat(ctx, tok, "Parroquia", d2)
                out[pr["value"]]["cantones"][ca["value"]] = {"text": ca["text"], "parroquias": {}}
                for pa in parrs:
                    d3 = {"intParroquia": pa["value"], "intCircunscripcion": 0}
                    zonas = _cat(ctx, tok, "Zona", d3)
                    out[pr["value"]]["cantones"][ca["value"]]["parroquias"][pa["value"]] = {
                        "text": pa["text"], "zonas": zonas}
            print(f"  [{i}/{len(provincias)}] {pr['text']}: "
                  f"{sum(len(c['parroquias']) for c in out[pr['value']]['cantones'].values())} parroquias")
        p_ = salida or os.path.join(rd.ruta_dir("vivo"), f"catalogo_app01_{_tag()}.json")
        json.dump(out, open(p_, "w", encoding="utf-8"), ensure_ascii=False)
        print("[OK] catálogo ->", p_)
        ctx.close()
    return out


def _zonas_de(cat):
    for pr, v in cat.items():
        for ca, cv in v["cantones"].items():
            for pa, pv in cv["parroquias"].items():
                for zo in pv["zonas"]:
                    yield {"prov": pr, "cant": ca, "parr": pa, "zona": zo["value"],
                           "text": zo["text"]}


def crawl(dignidad="11", maximo=None, headed=False, pmin=2.5, pmax=6.0,
          catalogo_path=None):
    """Consulta `dignidad` por **zona (recinto)** y guarda el JSON crudo (reanudable)."""
    from playwright.sync_api import sync_playwright
    cp = catalogo_path or os.path.join(rd.ruta_dir("vivo"), f"catalogo_app01_{_tag()}.json")
    if not os.path.exists(cp):
        print("[!] falta el catálogo; corré primero `catalogo`."); return
    cat = json.load(open(cp, encoding="utf-8"))
    zonas = list(_zonas_de(cat))
    print(f"[crawl] dignidad={dignidad} zonas={len(zonas)}")
    d = _crudo_dir(dignidad)
    manif = os.path.join(rd.ruta_dir("vivo"), f"manifiesto_app01_{_tag()}.csv")
    nuevo = not os.path.exists(manif)
    fm = open(manif, "a", newline="", encoding="utf-8")
    w = csv.writer(fm)
    if nuevo:
        w.writerow(["capturado_en", "dignidad", "prov", "cant", "parr", "zona", "ok", "bytes", "archivo"])
    hechas = 0
    with sync_playwright() as p:
        ctx, page = _abrir(p, headed)
        tok = _preparar(page)
        for z in zonas:
            if maximo and hechas >= maximo:
                break
            clave = f'{z["prov"]}-{z["cant"]}-{z["parr"]}-{z["zona"]}'
            ruta = os.path.join(d, clave + ".json")
            if os.path.exists(ruta):
                continue
            body = {"objConsulta": {"Dignidad": dignidad, "AbrirActa": False,
                    "Provincia": z["prov"], "Circunscripcion": "-1", "Canton": z["cant"],
                    "Parroquia": z["parr"], "Zona": z["zona"], "Junta": "-1",
                    "nomDignidad": DIGNIDADES.get(dignidad, ""), "strJurisdiccion": "",
                    "tokenCaptcha": "", "Pregunta": "-1"}}
            ok = False
            for intento in range(3):
                try:
                    _dormir(pmin, pmax)
                    js = _consulta(page, body)
                    ok = not js.get("Error", False) and bool(js.get("datos"))
                    json.dump(js, open(ruta, "w", encoding="utf-8"), ensure_ascii=False)
                    break
                except Exception as e:
                    print(f"  [!] {clave} intento {intento+1}: {e}")
                    _dormir(10, 20)   # backoff cortés
            w.writerow([datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                        dignidad, z["prov"], z["cant"], z["parr"], z["zona"], int(ok),
                        os.path.getsize(ruta) if os.path.exists(ruta) else 0, ruta])
            fm.flush()
            hechas += 1
            if hechas % 10 == 0:
                print(f"  {hechas} zonas… ({clave})")
        ctx.close()
    fm.close()
    print(f"[OK] {hechas} zonas nuevas -> {d}")


# ---------------------------------------------------------------------------
def main():
    global PORTAL
    ap = argparse.ArgumentParser(description="Captura cortés de portales app01 (CNE).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recon"); r.add_argument("--url", default=None)
    r.add_argument("--headed", action="store_true")
    c = sub.add_parser("catalogo"); c.add_argument("--headed", action="store_true")
    c.add_argument("--salida", default=None)
    c.add_argument("--base", default=None, help="URL del portal (p.ej. .../resultados2023_anticipadassv)")
    c.add_argument("--prov", default=None, help="códigos de provincia separados por coma")
    g = sub.add_parser("crawl")
    g.add_argument("--dignidad", default="11")
    g.add_argument("--max", type=int, default=None)
    g.add_argument("--base", default=None, help="URL del portal")
    g.add_argument("--headed", action="store_true")
    g.add_argument("--pmin", type=float, default=2.5)
    g.add_argument("--pmax", type=float, default=6.0)
    g.add_argument("--catalogo", default=None)
    a = ap.parse_args()
    if getattr(a, "base", None):
        PORTAL = a.base.rstrip("/")
    if a.cmd == "recon":
        recon(a.url, a.headed)
    elif a.cmd == "catalogo":
        solo = a.prov.split(",") if a.prov else None
        catalogo(a.headed, a.salida, solo)
    else:
        crawl(a.dignidad, a.max, a.headed, a.pmin, a.pmax, a.catalogo)


if __name__ == "__main__":
    main()

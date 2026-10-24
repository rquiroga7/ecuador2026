# -*- coding: utf-8 -*-
r"""
vivo/captura_2019.py — Seccionales 2019 por **junta** desde `app01.cne.gob.ec/resultados2019`.

Diseño robusto (el portal WebForms **resetea los combos** al mostrar resultados, así que
no se puede encadenar de una zona a otra tras un submit):

  * **Fase A (enumerar)**: cascada provincia→cantón→parroquia→zona (postbacks AJAX vía
    evento `change`) y, por zona, se leen sus juntas ("1F"/"1M"). Se cachea en
    `vivo/zonas2019.json` (no hay submits → estable).
  * **Fase B (capturar)**: por cada zona, **se recarga el portal** y se re-cascada a esa
    zona; luego se hace un submit por junta (sin captcha: `form.submit()` nativo +
    `btnConsultar=CONSULTAR`). Se **saltea** toda zona cuyas juntas ya están en `.done`.

Reanudable: `gaona2019_junta_d<dig>.csv` + `gaona2019_junta_d<dig>.done` (una clave por
junta). Salida en formato Gaona (con `junta_genero`).

Uso:
    set PLAYWRIGHT_BROWSERS_PATH=D:\\ecuador2026_data\\pw-browsers
    python -m vivo.captura_2019 --dignidad 2 --fase enum
    python -m vivo.captura_2019 --dignidad 2 --max-zonas 5      # prueba de captura
    python -m vivo.captura_2019 --dignidad 2                    # todo
"""

import os
import re
import csv
import json
import html as _html
import random
import time
import argparse

import rutas_datos as rd

BASE = "https://app01.cne.gob.ec/resultados2019"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

COLS = ["updated", "cod_dignidad", "cod_prov", "cod_cant", "circunscripcion",
        "parroquia", "recinto", "junta", "junta_genero", "acta_numero",
        "cod_org_pol", "cod_candidato", "total_sufragantes", "nulos", "blancos",
        "votos", "voto_acumulado", "nulo_acumulado", "blanco_acumulado",
        "sufragantes_acumulado", "porcentaje_votos_validos"]

ZONAS = "vivo/zonas2019.json"


def _num(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else 0


def _opts(html, cid):
    m = re.search(r'<select[^>]*id="%s"[^>]*>(.*?)</select>' % cid, html, re.S | re.I)
    if not m:
        return []
    out = []
    for o in re.finditer(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(1), re.S | re.I):
        out.append((o.group(1), re.sub(r"\s+", " ",
                    _html.unescape(re.sub(r"<[^>]+>", "", o.group(2)))).strip()))
    return out


def _parse_resultados(html):
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        cells = [c for c in cells if c != ""]
        if len(cells) >= 4 and re.fullmatch(r"[\d\.]+", cells[2] or "") and "%" in cells[3]:
            rows.append({"partido": cells[0], "candidato": cells[1],
                         "votos": _num(cells[2]), "pct": cells[3]})
    return rows


def _totales(html):
    t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", html)))
    def g(pat):
        m = re.search(pat, t)
        return _num(m.group(1)) if m else 0
    return {"sufragantes": g(r"Sufragantes\s+([\d\.]+)"),
            "blancos": g(r"Blancos\s+([\d\.]+)"),
            "nulos": g(r"Nulos\s+([\d\.]+)")}


def _pasar(page):
    page.goto(BASE, wait_until="domcontentloaded", timeout=90000)
    for _ in range(12):
        page.wait_for_timeout(1500)
        try:
            if "_Incapsula_Resource" not in page.content():
                return
        except Exception:
            pass


def _set(page, cid, val, wait=1500):
    page.evaluate("([c,v])=>{const e=document.getElementById(c); if(e){e.value=v;"
                  "e.dispatchEvent(new Event('change'));}}", [cid, val])
    page.wait_for_timeout(wait)


def _opts_page(page, cid):
    try:
        return [(v, t) for v, t in _opts(page.content(), cid) if v != "-1"]
    except Exception:
        return []


# ---------------------------------------------------------------------------
def enumerar(page, force=False, max_prov=None):
    p = rd.ruta(ZONAS)
    if os.path.exists(p) and not force:
        return json.load(open(p, encoding="utf-8"))
    zonas = []
    _set(page, "comboDignidad", "2", wait=3000)
    provs = _opts_page(page, "comboPro")
    if max_prov:
        provs = provs[:max_prov]
    parts = rd.ruta_dir("vivo/zonas2019_parts")
    print(f"[enum] provincias={len(provs)} | partes previas={len(os.listdir(parts))}")
    for pro, pn in provs:
        pf = os.path.join(parts, f"{pro}.json")
        if os.path.exists(pf):
            zonas.extend(json.load(open(pf, encoding="utf-8")))
            print(f"  [enum] {pn}: ya estaba (saltada)")
            continue
        # recargar por provincia (evita cuelgues de sesión larga)
        _pasar(page)
        _set(page, "comboDignidad", "2", wait=3000)
        _set(page, "comboPro", pro, wait=2500)
        cants = _opts_page(page, "comboCanton")
        zprov = []
        for cant, cn in cants:
            _set(page, "comboCanton", cant)
            for parr, prn in _opts_page(page, "comboParro"):
                _set(page, "comboParro", parr)
                for zona, zn in _opts_page(page, "comboZona"):
                    _set(page, "comboZona", zona)
                    juntas = _opts_page(page, "comboJunta")
                    zprov.append({"prov": pro, "cant": cant, "parr": parr,
                                  "zona": zona, "juntas": juntas})
        json.dump(zprov, open(pf, "w", encoding="utf-8"), ensure_ascii=False)
        zonas.extend(zprov)
        print(f"  [enum] {pn}: cantones={len(cants)} zonas={len(zprov)} acumuladas={len(zonas)}")
    json.dump(zonas, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[enum OK] {len(zonas)} zonas -> {p}")
    return zonas


def capturar(page, zonas, dignidad, max_zonas=None, pmin=1.5, pmax=4.0,
             prov=None, sufijo="", worker=None, nworkers=None):
    out = rd.ruta_dir("vivo")
    base = f"gaona2019_junta_d{int(dignidad)}"
    if prov:
        prov = set(str(p) for p in prov)
        zonas = [z for z in zonas if z["prov"] in prov]
    if nworkers:
        nw = int(nworkers); wk = int(worker or 0)
        zonas = [z for i, z in enumerate(zonas) if i % nw == wk]
    pv = os.path.join(out, base + sufijo + ".csv")
    nuevo = not os.path.exists(pv)
    fv = open(pv, "a", newline="", encoding="utf-8")
    w = csv.writer(fv)
    if nuevo:
        w.writerow(COLS)
    done_p = os.path.join(out, base + sufijo + ".done")
    # cargar la unión de TODOS los .done de esta dignidad (base + workers)
    import glob as _glob
    done = set()
    for f in _glob.glob(os.path.join(out, base + "*.done")):
        done |= set(open(f, encoding="utf-8").read().split())
    fdone = open(done_p, "a", encoding="utf-8")

    def dormir():
        time.sleep(random.uniform(pmin, pmax))

    hechas = zonas_proc = 0
    for z in zonas:
        keys = [f'{z["prov"]}-{z["cant"]}-{z["parr"]}-{z["zona"]}-{jv}'
                for jv, _ in z["juntas"]]
        if keys and all(k in done for k in keys):
            continue
        if max_zonas and zonas_proc >= max_zonas:
            break
        # recargar y re-cascada a esta zona
        _pasar(page)
        _set(page, "comboDignidad", str(dignidad))
        _set(page, "comboPro", z["prov"])
        _set(page, "comboCanton", z["cant"])
        _set(page, "comboParro", z["parr"])
        _set(page, "comboZona", z["zona"])
        for jv, jt in _opts_page(page, "comboJunta"):
            key = f'{z["prov"]}-{z["cant"]}-{z["parr"]}-{z["zona"]}-{jv}'
            if key in done:
                continue
            dormir()
            try:
                with page.expect_navigation(timeout=40000):
                    page.evaluate("""v=>{const f=document.getElementById('form1');
                        document.getElementById('comboJunta').value=v;
                        let i=document.getElementById('__bc');
                        if(!i){i=document.createElement('input'); i.type='hidden';
                          i.name='btnConsultar'; i.id='__bc'; f.appendChild(i);}
                        i.value='CONSULTAR'; f.submit();}""", jv)
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(700)
            try:
                html = page.content()
            except Exception:
                page.wait_for_timeout(1200)
                try:
                    html = page.content()
                except Exception:
                    continue
            tot = _totales(html)
            filas = _parse_resultados(html)
            if not filas:
                continue          # no marcar como hecha: reintentar en otra corrida
            gen = "F" if jt.upper().endswith("F") else ("M" if jt.upper().endswith("M") else "")
            for r in filas:
                w.writerow(["", dignidad, z["prov"], z["cant"], "-1", z["parr"],
                            z["zona"], re.sub(r"\D", "", jt), gen, "", r["partido"],
                            r["candidato"], tot["sufragantes"], tot["nulos"],
                            tot["blancos"], r["votos"], "", "", "", "", r["pct"]])
            fv.flush()
            fdone.write(key + "\n"); fdone.flush()
            done.add(key); hechas += 1
        zonas_proc += 1
        if zonas_proc % 10 == 0:
            print(f"  {zonas_proc} zonas | {hechas} juntas nuevas | última {z['prov']}-{z['cant']}-{z['parr']}-{z['zona']}")
    fv.close(); fdone.close()
    print(f"[OK] dig={dignidad}: {hechas} juntas nuevas -> {pv}")


def main():
    ap = argparse.ArgumentParser(description="Seccionales 2019 por junta (robusto).")
    ap.add_argument("--dignidad", default="2")
    ap.add_argument("--fase", choices=["enum", "cap", "todo"], default="todo")
    ap.add_argument("--max-zonas", type=int, default=None)
    ap.add_argument("--pmin", type=float, default=1.5)
    ap.add_argument("--pmax", type=float, default=4.0)
    ap.add_argument("--reenumerar", action="store_true")
    ap.add_argument("--max-prov", type=int, default=None)
    ap.add_argument("--prov", default=None, help="provincias separadas por coma")
    ap.add_argument("--sufijo", default="", help="sufijo de output por worker")
    ap.add_argument("--worker", type=int, default=None, help="índice de worker (round-robin)")
    ap.add_argument("--nworkers", type=int, default=None, help="nº total de workers")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(locale="es-EC", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        _pasar(page)
        zonas = None
        if a.fase in ("enum", "todo"):
            zonas = enumerar(page, force=a.reenumerar, max_prov=a.max_prov)
        if a.fase in ("cap", "todo"):
            if zonas is None:
                zonas = json.load(open(rd.ruta(ZONAS), encoding="utf-8"))
            provs = a.prov.split(",") if a.prov else None
            capturar(page, zonas, a.dignidad, a.max_zonas, a.pmin, a.pmax, provs,
                     a.sufijo, a.worker, a.nworkers)
        ctx.close()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
datos/geo.py — GeoJSON de provincias y cantones con **códigos del CNE**.

Fuente: servicio ArcGIS del INEC (Provincias/Cantones del Ecuador, DPA), con salida
GeoJSON WGS84. Se guarda una copia cruda en `raw/geo/` (cache) y se generan versiones
normalizadas en `web/` con el código que usa el dashboard:

  web/provincias.geojson   properties: {cod (2d), nombre}
  web/cantones.geojson     properties: {cod (CNE), cod_provincia (2d), nombre}

Provincias: el código DPA (01..24) coincide con el del CNE → mapeo directo.
Cantones: el CNE usa un **código secuencial nacional** (no DPA); se construye un cruce
por **nombre + provincia** contra `catalogo/canton.csv.gz` (exacto y difuso).

Uso:
    python -m datos.geo                 # descarga (o usa cache) y genera web/*.geojson
    python -m datos.geo --no-descargar  # solo normaliza lo cacheado
"""

import os
import re
import sys
import json
import time
import unicodedata
import difflib

import requests

import rutas_datos as rd

ARCGIS = "https://services7.arcgis.com/iFGeGXTAJXnjq0YN/ArcGIS/rest/services"
URLS = {
    "provinces": f"{ARCGIS}/Provincias_del_Ecuador/FeatureServer/0/query"
                 "?where=1%3D1&outFields=*&f=geojson&outSR=4326",
    "cantons": f"{ARCGIS}/Cantones_del_Ecuador/FeatureServer/0/query"
               "?where=1%3D1&outFields=*&f=geojson&outSR=4326",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (ecuador2026)"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9 ]", " ", s).upper()
    return re.sub(r"\s+", " ", s).strip()


def _descargar(nombre, url, intentos=4):
    d = rd.ruta_dir("raw/geo")
    p = os.path.join(d, f"{nombre}.geojson")
    for i in range(intentos):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            with open(p, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"[+] {nombre} -> {p} ({len(r.content)/1e6:.1f} MB)")
            return p
        except requests.RequestException as e:
            print(f"[!] {nombre} intento {i+1}: {e}")
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"no pude descargar {nombre}")


def _leer(nombre, no_descargar=False):
    p = os.path.join(rd.ruta_dir("raw/geo"), f"{nombre}.geojson")
    if no_descargar and os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    if not os.path.exists(p):
        p = _descargar(nombre, URLS[nombre])
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------------------
SIMPLIFY = {"provinces": 0.010, "cantons": 0.004}   # grados (~1.1 km / ~0.4 km)
ROUND = 5

# Variantes ortográficas DPA -> nombre del catálogo CNE (por provincia).
ALIAS = {("19", "YANTZAZA"): "YANZATZA"}

# Las "zonas no delimitadas" (DPA prov 90) se incorporaron luego a una provincia/cantón
# (Las Golondrinas→Imbabura, Manga del Cura→Manabí, El Piedrero→Guayas). Se **fusionan**
# con su cantón actual resolviendo por **frontera compartida** (shapely).
PROV_ZONA = "90"
OVERRIDES_CSV = "canton_overrides.csv"   # datos/canton_overrides.csv (editable)

# Fusión de cada zona no delimitada con su cantón actual (asignación legal, no
# geométrica): Manga del Cura→El Carmen (Manabí); El Piedrero→El Triunfo (Guayas);
# Las Golondrinas→Imbabura (se asigna a Cotacachi, su cantón occidental).
# Valor = (cod_provincia 2d, cod_canton CNE 3d).
ZONAS_FUSION = {
    "MANGA DEL CURA": ("13", "500"),
    "EL PIEDRERO": ("09", "505"),
    "LAS GOLONDRINAS": ("10", "040"),
}


def _round_coords(obj, nd=ROUND):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(x), nd) for x in obj]
        return [_round_coords(x, nd) for x in obj]
    return obj


def _simplificar(gj, tol):
    """Simplifica y redondea la geometría (shapely) para que pese poco en la web."""
    from shapely.geometry import shape, mapping
    feats = []
    for f in gj["features"]:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        g = g.simplify(tol, preserve_topology=True)
        f = dict(f)
        f["geometry"] = _round_coords(mapping(g))
        feats.append(f)
    return {"type": "FeatureCollection", "features": feats}


def _cat_canton():
    p = rd.ruta("catalogo/canton.csv.gz")
    if not os.path.exists(p):
        return None
    import pandas as pd
    d = pd.read_csv(p, dtype=str)
    d["prov"] = d["COD_PROVINCIA"].str.zfill(2)
    d["cod"] = d["COD_CANTON"].str.zfill(3)
    d["nn"] = d["NOM_CANTON"].map(norm)
    return d


def _overrides():
    """{nombre_normalizado: cod_cne} editables (datos/canton_overrides.csv)."""
    p = rd.ruta(OVERRIDES_CSV)
    if not os.path.exists(p):
        return {}
    import pandas as pd
    d = pd.read_csv(p, dtype=str)
    if "nombre_geo" not in d.columns or "cod_cne" not in d.columns:
        return {}
    return {norm(r["nombre_geo"]): str(r["cod_cne"]).zfill(3) for _, r in d.iterrows()
            if str(r["cod_cne"]).strip()}


def _cruce_cantones(gj, cats):
    """Asigna a cada feature el código CNE de cantón (exacto por nombre+prov, o difuso)."""
    if cats is None:
        return 0, len(gj["features"])
    por_prov = {pr: g for pr, g in cats.groupby("prov")}
    ovr = _overrides()
    exacto = difuso = 0

    def _buscar(nom, g):
        """Devuelve (cod, prov, how); `prov` es la provincia del cantón del catálogo."""
        hit = g[g["nn"] == nom]
        if len(hit):
            return hit.iloc[0]["cod"], hit.iloc[0]["prov"], "exacto"
        # contención (DPA trae prefijos: SAN PEDRO DE PELILEO vs PELILEO)
        cont = g[g["nn"].apply(lambda x: bool(x) and (x in nom or nom in x))]
        if len(cont):
            r = cont.sort_values("nn", key=lambda s: s.str.len()).iloc[-1]
            return r["cod"], r["prov"], "cont"
        # último token significativo
        toks = [t for t in nom.split() if t not in ("SAN", "SANTA", "SANTIAGO", "DE",
                                                     "LA", "EL", "GNRAL", "GRAL")]
        for key in reversed(toks or nom.split()):
            m = g[g["nn"].str.split(" ").apply(lambda xs: key in xs)]
            if len(m) == 1:
                return m.iloc[0]["cod"], m.iloc[0]["prov"], "token"
        m = difflib.get_close_matches(nom, g["nn"].tolist(), n=1, cutoff=0.82)
        if m:
            r = g[g["nn"] == m[0]].iloc[0]
            return r["cod"], r["prov"], "difuso"
        return None, None, None

    for f in gj["features"]:
        pr = str(f["properties"].get("DPA_PROVIN", "")).zfill(2)
        nom = norm(f["properties"].get("DPA_DESCAN", ""))
        props = {"cod_provincia": pr, "nombre": f["properties"].get("DPA_DESCAN", "")}

        # 1) zona no delimitada: fusión explícita a su cantón actual
        if pr == PROV_ZONA:
            props["zona_no_delimitada"] = True
            if nom in ZONAS_FUSION:
                pv, cc = ZONAS_FUSION[nom]
                props.update({"cod_provincia": pv, "cod": cc,
                              "fusionado_en": f"cantón {cc} (prov {pv})"})
            elif ovr.get(nom):
                props["cod"] = ovr[nom]
            # si no, queda marcada para el resolvedor geométrico
            f["properties"] = props
            continue

        # 2) alias ortográfico DPA -> catálogo
        nom = ALIAS.get((pr, nom), nom)
        # 3) override manual por nombre
        cod, prov = ovr.get(nom), None
        how = "override" if cod else None
        if cod is None:
            cod, prov, how = _buscar(nom, por_prov[pr]) if pr in por_prov else (None, None, None)
        if cod is None:                      # fallback global (nombres únicos)
            cod, prov, how = _buscar(nom, cats)
        if how == "exacto":
            exacto += 1
        elif how:
            difuso += 1
        props["cod"] = cod
        if prov:                             # corrige provincias traspasadas (p.ej. La Concordia)
            props["cod_provincia"] = prov
        f["properties"] = props
    return exacto, difuso


def _resolver_zonas(gj):
    """Fusiona las zonas no delimitadas con el cantón (con código CNE) cuya **frontera
    comparte** más longitud; si no toca ninguna, el de **centroide** más cercano.
    Les asigna `cod` y `cod_provincia` del cantón padre."""
    from shapely.geometry import shape
    cantones = [(i, shape(f["geometry"]), f)
                for i, f in enumerate(gj["features"])
                if f["properties"].get("cod")]
    if not cantones:
        return 0
    resueltos = 0
    for f in gj["features"]:
        if not f["properties"].get("zona_no_delimitada"):
            continue
        if f["properties"].get("cod"):
            continue
        zg = shape(f["geometry"])
        zb = zg.boundary
        mejor, mejor_largo, mejor_dist = None, 0.0, 1e9
        for _, cg, cf in cantones:
            largo = zb.intersection(cg.boundary).length
            if largo > mejor_largo:
                mejor, mejor_largo = cf, largo
        if mejor is None:                        # sin contacto: el más cercano
            for _, cg, cf in cantones:
                d = zg.distance(cg)
                if d < mejor_dist:
                    mejor, mejor_dist = cf, d
        f["properties"]["cod"] = mejor["properties"]["cod"]
        f["properties"]["cod_provincia"] = mejor["properties"]["cod_provincia"]
        f["properties"]["fusionado_en"] = mejor["properties"]["nombre"]
        resueltos += 1
    return resueltos


def _mascara(prov_out, tol=0.02):
    """GeoJSON 'mundo menos Ecuador' (polígono con agujero): tapa los países vecinos."""
    import shapely
    from shapely.geometry import box, shape, mapping

    def _union(geoms):
        if hasattr(shapely, "union_all"):
            return shapely.union_all(geoms)
        from shapely.ops import unary_union
        return unary_union(geoms)

    mundo = box(-180, -89, 180, 89)
    ec = _union([shape(f["geometry"]).buffer(0) for f in prov_out["features"]])
    ec = ec.simplify(tol, preserve_topology=True)
    resto = mundo.difference(ec)
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"tipo": "resto"},
                          "geometry": _round_coords(mapping(resto))}]}


def preparar(no_descargar=False):
    gj_p = _leer("provinces", no_descargar)
    gj_c = _leer("cantons", no_descargar)

    provs = []
    for f in gj_p["features"]:
        cod = str(f["properties"].get("DPA_PROVIN", "")).zfill(2)
        if not (cod.isdigit() and 1 <= int(cod) <= 24):
            continue  # descarta zonas no codificadas
        f["properties"] = {"cod": cod,
                           "nombre": f["properties"].get("DPA_DESPRO", "")}
        provs.append(f)
    prov_out = {"type": "FeatureCollection", "features": provs}

    cats = _cat_canton()
    exacto, difuso = _cruce_cantones(gj_c, cats)
    n_zonas = _resolver_zonas(gj_c)

    # simplificar para la web (menos MB, carga rápida)
    prov_out = _simplificar(prov_out, SIMPLIFY["provinces"])
    gj_c = _simplificar(gj_c, SIMPLIFY["cantons"])

    # máscara: mundo menos Ecuador, para tapar los países vecinos en los mapas
    mask = _mascara(prov_out)

    d = os.path.join(rd.REPO, "web")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "provincias.geojson"), "w", encoding="utf-8") as f:
        json.dump(prov_out, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(d, "cantones.geojson"), "w", encoding="utf-8") as f:
        json.dump(gj_c, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(d, "mascara.geojson"), "w", encoding="utf-8") as f:
        json.dump(mask, f, ensure_ascii=False, separators=(",", ":"))

    n_c = len(gj_c["features"])
    zonas = [(f["properties"]["nombre"], f["properties"].get("fusionado_en"))
             for f in gj_c["features"] if f["properties"].get("zona_no_delimitada")]
    sin_cod = [f["properties"]["nombre"] for f in gj_c["features"]
               if not f["properties"].get("cod")]
    con_cod = n_c - len(sin_cod)
    print(f"[OK] provincias={len(provs)} -> web/provincias.geojson")
    print(f"[OK] cantones={n_c} (con código CNE={con_cod}: exactos={exacto}, "
          f"difusos={difuso}) -> web/cantones.geojson")
    for nombre, padre in zonas:
        print(f"     + zona '{nombre}' fusionada en '{padre}'")
    if sin_cod:
        print(f"     + sin código ({len(sin_cod)}): {', '.join(sin_cod[:20])}")
    return prov_out, gj_c


if __name__ == "__main__":
    preparar(no_descargar="--no-descargar" in sys.argv)

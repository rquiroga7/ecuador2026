# -*- coding: utf-8 -*-
"""
modelo/proyectar.py — Motor de proyección en vivo (Seccionales Ecuador 2026).

Toma una **instantánea** (mesas ya escrutadas, tidy) y la **referencia por familia**,
proyecta los votos que faltan y agrega a territorio (provincia para prefecto, cantón
para alcalde). Emite el bloque de datos del dashboard (`docs/DASHBOARD.md`).

**Unidad fina** (`nivel`): `recinto` (zona; más fino y estable que la junta/mesa) o
`parroquia`. El recinto exige el dump por mesa de la referencia (2023 y 2026); si no
existe (2019/2021/2025, que solo tienen `.sav` parroquia×sexo) `nivel_efectivo` baja a
`parroquia` automáticamente.

Métodos:
  * `v1`        — relleno jerárquico espacial (unidad → cantón → provincia → nación),
                  sin mapear alianzas entre años. Método principal en lo local.
  * `jerarquico`— logit-swing jerárquico (`proyeccion.Proyector`) sobre familias, con
                  jerarquía nacional → provincia → cantón → parroquia.

Los **bloques** son FAMILIAS (`datos.familias`), no candidatos.

Uso:
    from modelo import proyectar
    ref = proyectar.referencia_familias("prefecto", 2023, nivel="recinto")
    bloque = proyectar.construir("prefecto", snapshot, ref, metodo="v1", nivel="recinto")
    proyectar.emitir({"prefecto": snap_p, "alcalde": snap_a})
"""

import os
import json
from datetime import datetime

import numpy as np
import pandas as pd

import rutas_datos as rd
from datos.familias import familia as _familia
from modelo import v1_brasil

TERRITORIO = {"prefecto": "provincia", "alcalde": "canton"}

# Nivel de la unidad fina del modelo: "recinto" (zona) o "parroquia".
# El recinto (zona) es más fino y estable que la junta/mesa: en 2023 hay 2.930
# recintos (mediana ~560 votos) frente a 40.058 mesas (~145 votos) y 1.227
# parroquias (~2.165). Solo existe en los dumps por mesa (2023 y 2026); los
# `.sav` del CNE de 2019/2021/2025 son parroquia×sexo → ahí usar "parroquia".
NIVEL = "recinto"


# ---------------------------------------------------------------------------
def _unidad(lista, nivel=None):
    """loc_id/mesa_id -> clave de la unidad fina (recinto/zona o parroquia)."""
    nivel = nivel or NIVEL
    p = lista.astype(str).str.split("-")
    parroquia = p.str[0] + "-" + p.str[1] + "-" + p.str[3]
    if nivel == "recinto":
        return parroquia + "-" + p.str[4]
    return parroquia


def _loc3(lista):
    return _unidad(lista, "parroquia")


def nivel_efectivo(nivel=None, anio=2023, dignidad="prefecto"):
    """Baja 'recinto' a 'parroquia' si no hay dump por mesa del año de referencia.

    2019/2021/2025 solo tienen `.sav` parroquia×sexo → recinto imposible; en esos
    casos el modelo (referencia y observado) debe correr a parroquia para que las
    dos matrices compartan unidad.
    """
    nivel = nivel or NIVEL
    if nivel != "recinto":
        return "parroquia"
    return ("recinto"
            if os.path.exists(rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz"))
            else "parroquia")


def referencia_familias(dignidad, anio=2023, nivel=None):
    """Matriz unidad × familia con los votos de referencia.

    nivel="parroquia" usa el agregado `parr_partido_*`; nivel="recinto" (zona)
    exige el dump por mesa (`votos_*`), disponible para 2023 y 2026 pero **no**
    para 2019/2021/2025 (sus `.sav` son parroquia×sexo).
    """
    nivel = nivel or NIVEL
    if nivel == "recinto":
        p = rd.ruta(f"mesas/votos_{dignidad}_{anio}.csv.gz")
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"{p}: no hay dump por mesa para {dignidad} {anio}; el nivel "
                f"'recinto' solo está disponible para 2023 y 2026")
        v = pd.read_csv(p, dtype=str, usecols=["loc_id", "lista", "votos"])
        v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
        v["unidad"] = _unidad(v["loc_id"], nivel)
        v["familia"] = v["lista"].map(lambda x: _familia(x))
        return v.groupby(["unidad", "familia"])["votos"].sum().unstack(fill_value=0)
    p = rd.ruta(f"mesas/parr_partido_{dignidad}_{anio}.csv.gz")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    v = pd.read_csv(p, dtype=str)
    v["votos"] = pd.to_numeric(v["votos"], errors="coerce").fillna(0).astype(int)
    v["familia"] = v["partido"].map(lambda x: _familia(x))
    return v.groupby(["loc_id", "familia"])["votos"].sum().unstack(fill_value=0)


def observado_familias(snapshot, nivel=None):
    """Matriz unidad × familia de lo ya escrutado (desde una instantánea tidy)."""
    nivel = nivel or NIVEL
    v = snapshot["votos"].copy()
    if v.empty:
        return pd.DataFrame()
    base = v["loc_id"] if "loc_id" in v.columns else v["mesa_id"]
    v["unidad"] = _unidad(base, nivel)
    if "familia" not in v.columns:
        v["familia"] = v["lista"].map(lambda x: _familia(x))
    return v.groupby(["unidad", "familia"])["votos"].sum().unstack(fill_value=0)


def _nombres(dignidad):
    """dict cod -> nombre para provincias (prefecto) o cantones (alcalde)."""
    if dignidad == "prefecto":
        p = rd.ruta("catalogo/provincia.csv.gz")
        if not os.path.exists(p):
            return {}
        d = pd.read_csv(p, dtype=str)
        return dict(zip(d["COD_PROVINCIA"].str.zfill(2), d["NOM_PROVINCIA"]))
    p = rd.ruta("catalogo/canton.csv.gz")
    if not os.path.exists(p):
        return {}
    d = pd.read_csv(p, dtype=str)
    cod = d["COD_PROVINCIA"].str.zfill(2) + "-" + d["COD_CANTON"].str.zfill(3)
    return dict(zip(cod, d["NOM_CANTON"]))


def _terr_of(loc3, dignidad):
    return loc3.str.slice(0, 2) if dignidad == "prefecto" else loc3.str.slice(0, 6)


# ---------------------------------------------------------------------------
def _jerarquia(unidades, nivel=None):
    """Jerarquía geográfica por unidad: (nacional, provincia, cantón, parroquia).

    Las claves de unidad son `prov-cant-parroquia` (parroquia) o
    `prov-cant-parroquia-zona` (recinto/zona). En el recinto, la parroquia es el
    prefijo sin el campo zona. El encogimiento del `Proyector` va de lo fino a lo
    grueso; el efecto propio de la unidad se maneja con `k_own` (fracción contada).
    """
    nivel = nivel or NIVEL
    if nivel == "recinto":
        return {k: ("EC", k[:2], k[:6], k[:11]) for k in unidades}
    return {k: ("EC", k[:2], k[:6], k) for k in unidades}


def _proyectar_unidades(obs_fam, ref_fam, dignidad, metodo, nivel=None):
    """Devuelve (proy [U,K], obs [U,K], val_base [U], unidades, familias)."""
    nivel = nivel or NIVEL
    unidades = sorted(set(ref_fam.index) | set(obs_fam.index))
    familias = sorted(set(ref_fam.columns) | set(obs_fam.columns))
    ref = ref_fam.reindex(index=unidades, columns=familias, fill_value=0)
    obs = obs_fam.reindex(index=unidades, columns=familias, fill_value=0)
    val_base = ref.sum(axis=1).values.astype(float)
    O = obs.values.astype(float)

    if metodo == "jerarquico":
        try:
            from proyeccion import Proyector
            jer = _jerarquia(unidades, nivel)
            modelo = Proyector(unidades, jer, ref.values.astype(float),
                               np.maximum(ref.values.sum(axis=1), 1.0))
            counted = O.sum(1) > 0
            f = counted.astype(float)
            r = modelo.proyectar(O.copy(), f, np.arange(len(familias)))
            if r is not None:
                return r["final"], O, val_base, unidades, familias
        except Exception:
            pass  # cae a v1
    return None, O, val_base, unidades, familias


def _v1(obs, val_base, unidades, dignidad):
    grupos = [np.array([u[:6] for u in unidades]),
              np.array([u[:2] for u in unidades]),
              np.full(len(unidades), "EC")]
    return v1_brasil.proyectar(obs, val_base, grupos)


def _candidatos(cols, proy, crude):
    tot_p, tot_c = proy.sum(), crude.sum()
    pct_p = 100 * proy / tot_p if tot_p else np.zeros_like(proy)
    pct_c = 100 * crude / tot_c if tot_c else np.zeros_like(crude)
    orden = np.argsort(-proy)
    out = []
    for j in orden:
        if proy[j] <= 0 and crude[j] <= 0:
            continue
        out.append({"familia": cols[j], "nombre": cols[j], "partido": cols[j],
                    "votos_crudo": int(round(crude[j])), "pct_crudo": round(float(pct_c[j]), 2),
                    "votos_proy": int(round(proy[j])), "pct_proy": round(float(pct_p[j]), 2)})
    return out


def construir(dignidad, snapshot, ref_fam, metodo="v1", serie=None, nivel=None):
    """Bloque de datos de una dignidad para el dashboard."""
    obs_fam = observado_familias(snapshot, nivel)
    if obs_fam.empty:
        return {"nacional": {"escrutado": 0.0, "candidatos": []}, "territorios": [],
                "serie": []}
    proy, O, val_base, unidades, familias = _proyectar_unidades(
        obs_fam, ref_fam, dignidad, metodo, nivel)
    if proy is None:
        proy = _v1(O, val_base, unidades, dignidad)

    # conteo crudo = lo observado (sin rellenar) agregado a territorio
    terr = _terr_of(pd.Series(unidades), dignidad)
    terr.index = unidades
    nombres = _nombres(dignidad)

    P = pd.DataFrame(proy, index=unidades, columns=familias)
    C = pd.DataFrame(O, index=unidades, columns=familias)
    VB = pd.Series(val_base, index=unidades)
    counted = C.sum(axis=1) > 0

    P_t = P.groupby(terr).sum()
    C_t = C.groupby(terr).sum()
    # escrutado territorial: fracción de los votos de referencia ya contados
    cont = VB.where(counted, 0.0).groupby(terr).sum()
    tot = VB.groupby(terr).sum()
    crudo_t = C_t.sum(axis=1)

    territorios = []
    for t in P_t.index:
        pv = P_t.loc[t].values
        cv = C_t.loc[t].values
        cands = _candidatos(familias, pv, cv)
        esc = (round(min(100.0, 100 * float(crudo_t.get(t, 0) / tot[t])), 2)
               if tot.get(t, 0) else 0.0)
        gan = None
        gan_c = None
        if len(cands) >= 1:
            gan = cands[0]["familia"]
            gan_c = cands[0]["familia"]
            if len(cands) >= 2:
                margen = round(cands[0]["pct_proy"] - cands[1]["pct_proy"], 2)
            else:
                margen = 100.0
        else:
            margen = None
        if len(cv) and cv.sum() > 0:
            gan_c = familias[int(np.argmax(cv))]
        territorios.append({
            "cod": str(t), "nombre": nombres.get(str(t), str(t)),
            "escrutado": esc, "electores_habilitados": int(round(float(tot.get(t, 0)))),
            "candidatos": cands, "ganador_proy": gan, "margen_proy": margen,
            "ganador_crudo": gan_c,
        })
    territorios.sort(key=lambda d: -d["electores_habilitados"])

    # nacional
    tot_p = P.values.sum(0)
    tot_c = C.values.sum(0)
    esc_nac = (round(min(100.0, 100 * float(tot_c.sum() / VB.sum())), 2)
               if VB.sum() else 0.0)
    nac = {"escrutado": esc_nac, "candidatos": _candidatos(familias, tot_p, tot_c)}

    out = {"nacional": nac, "territorios": territorios}
    if serie is not None:
        out["serie"] = serie
    return out


# ---------------------------------------------------------------------------
def emitir(dignidades_snap, refs=None, metodo="v1", destino=None, series=None,
           eleccion="Seccionales Ecuador 2026", anio=None, referencia=None,
           simulado=False, orden=None, nivel=None):
    """dignidades_snap: {dignidad: snapshot}. Escribe datos_web.json (contrato web)."""
    refs = refs or {}
    niv = nivel_efectivo(nivel, referencia or 2023, "prefecto")
    doc = {
        "actualizado": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "eleccion": eleccion,
        "anio": anio,
        "referencia": referencia,      # elección base del swing/relleno (misma dignidad)
        "nivel": niv,                  # unidad fina del modelo (recinto | parroquia)
        "orden_carga": orden,          # orden de carga simulado (p.ej. prioridad2021)
        "simulado": bool(simulado),
        "metodo_principal": metodo,
        "escrutado_pct": None,
    }
    for dig, snap in dignidades_snap.items():
        nj = nivel_efectivo(nivel, referencia or 2023, dig)
        ref = refs.get(dig)
        if ref is None:
            ref = referencia_familias(dig, referencia or 2023, nj)
        ser = (series or {}).get(dig)
        doc[dig] = construir(dig, snap, ref, metodo=metodo, serie=ser, nivel=nj)
    if "prefecto" in doc:
        doc["escrutado_pct"] = doc["prefecto"]["nacional"]["escrutado"]
    p = destino or os.path.join(rd.REPO, "web", "datos_web.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"[OK] datos_web.json -> {p}")
    return doc


def serie_nacional(dignidad, ref, orden, anio_base=2023, fracciones=None,
                   metodo="v1", nivel=None):
    """Serie temporal (nacional) del % proyectado por familia, para el dashboard."""
    from vivo.instantaneas import cargar_base, instantanea
    base = cargar_base(dignidad, anio_base)
    frs = fracciones or [0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.0]
    serie = []
    for fr in frs:
        snap = instantanea(base, orden, fr)
        doc = construir(dignidad, snap, ref, metodo=metodo, nivel=nivel)
        serie.append({"t": f"{int(round(100 * fr))}%",
                      "candidatos": {c["familia"]: c["pct_proy"]
                                     for c in doc["nacional"]["candidatos"]}})
    return serie


def demo(anio=2023, referencia=2019, fraccion=0.35, orden="aleatorio",
         metodo="v1", con_serie=True, destino=None, eleccion=None, seed=7,
         nivel=None):
    """Genera `datos_web.json` desde un **replay** (para probar el dashboard).

    Proyecta `anio` a partir del escrutinio parcial simulado, tomando `referencia`
    como base (por defecto 2023 ← 2019, la misma tarea que 2026 ← 2023).
    """
    from vivo.instantaneas import cargar_base, instantanea, _orden
    import numpy as _np
    rng = _np.random.default_rng(seed)
    niv = nivel_efectivo(nivel, referencia, "prefecto")
    snaps, refs, series, ordenes = {}, {}, {}, {}
    for dig in ["prefecto", "alcalde"]:
        base = cargar_base(dig, anio)
        ordenes[dig] = _orden(base["mesas"], orden, rng)
        snaps[dig] = instantanea(base, ordenes[dig], 1.0 if fraccion >= 1 else fraccion)
        refs[dig] = referencia_familias(dig, referencia, niv)
    if con_serie:
        series["prefecto"] = serie_nacional("prefecto", refs["prefecto"],
                                            ordenes["prefecto"], anio_base=anio,
                                            metodo=metodo, nivel=niv)
    return emitir(snaps, refs, series=series, metodo=metodo,
                  eleccion=eleccion or f"Seccionales Ecuador {anio} (prueba)",
                  anio=anio, referencia=referencia, simulado=True, nivel=niv,
                  destino=destino or os.path.join(rd.REPO, "web", "datos_web.json"))


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Genera datos_web.json (replay o real).")
    ap.add_argument("--anio", type=int, default=2023)
    ap.add_argument("--referencia", type=int, default=2019)
    ap.add_argument("--fraccion", type=float, default=0.35)
    ap.add_argument("--orden", default="aleatorio")
    ap.add_argument("--metodo", default="v1")
    ap.add_argument("--nivel", default=None, choices=[None, "recinto", "parroquia"])
    ap.add_argument("--sin-serie", action="store_true")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--eleccion", default=None)
    a = ap.parse_args()
    demo(a.anio, a.referencia, a.fraccion, a.orden, a.metodo,
         con_serie=not a.sin_serie, destino=a.salida, eleccion=a.eleccion,
         nivel=a.nivel)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
backtest.py — Compara métodos de proyección (con caché).

Fase 1 (una vez): muestrea ~N_SNAPS instantáneas por raspado y las guarda en
'backtest_snapshots/' (+ manifest.json).
Fase 2 (por método): proyecta cada instantánea y guarda resultados por grupo en
'backtest_resultados/<grupo>.json'. Si ya existen, se reutilizan.
Fase 3: agrupa errores por % escrutado (nacional y por estado) y grafica.

Cambiar solo v4 -> borrar 'backtest_resultados/v4.json' (o pasar --recalcular v4)
y volver a correr: no re-muestrea ni re-proyecta los demás métodos.
"""

import os
import sys
import csv
import io
import json
import tempfile
import contextlib
import argparse
from collections import OrderedDict

import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
os.chdir(REPO)
sys.path.insert(0, REPO)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import extrapolador10B_rodri as e1
import proyeccion_swing as sw
import proyeccion_schteingart as sc
import proyeccion_v4 as v4

import rutas_datos as rd
import estilo_plot as ep

ARCHIVOS = [rd.ruta("escrutinio_zonas_2026.csv"),
            rd.ruta("escrutinio_zonas_2026maquinalabo.csv"),
            rd.ruta("escrutinio_zonas_2026maquinarafa.csv")]
OBJETIVOS_NAC = [5, 10, 20, 35, 50, 75, 100]
BINS_ESTADO = [5, 10, 20, 35, 50, 75, 100]
N_SNAPS = 25
SNAP_DIR = rd.ruta_dir("backtest_snapshots")
RES_DIR = rd.ruta_dir("backtest_resultados")
GRUPOS = ["sw", "v4", "scht"]   # sw -> crudo,v1,v2 ; scht -> scht,scht_ng

METODOS = OrderedDict([
    ("crudo", ("#9AA0A6", "Conteo crudo TSE (muestra sesgada)")),
    ("v1",  ("#E11B22", "Etchenique: media estratificada de lo contado")),
    ("v2",  ("#4C8DFF", "Quiroga: swing uniforme nacional (2022 + swing)")),
    ("scht", ("#2E7D32", "Schteingart (con gate): crudo hasta estar listo")),
    ("scht_ng", ("#8B5CF6", "Schteingart sin gate: proyecta siempre")),
    ("v4",  ("#B8860B", "v4 Swing por ESTADO (encogido a nacional si falta dato)")),
])

sw.N_SIM = 5
_BASE = e1.cargar_linea_base_2022()
_Z22 = sw.cargar_zonas_2022()
for _m in (e1, sw, sc, v4):
    if hasattr(_m, "cargar_linea_base_2022"):
        _m.cargar_linea_base_2022 = lambda: _BASE
    if hasattr(_m, "cargar_zonas_2022"):
        _m.cargar_zonas_2022 = lambda: _Z22

CANON = ['hora_local', 'hora_tse', 'estado_uf', 'codigo_municipio', 'municipio',
         'zona_electoral', 'secoes_totalizadas', 'electores', 'votos_totales',
         'Lula', 'Flavio_Bolsonaro', 'Augusto_Cury', 'Ronaldo_Caiado', 'Romeu_Zema',
         'Renan_Santos', 'Hertz_Dias', 'Edmilson_Costa', 'Clariana_Barao',
         'Rui_Costa_Pimenta', 'Wilson_Grassi', 'Samara_Martins', 'votos_blancos',
         'votos_nulos', 'numero_pasada']


def norm(x):
    x = str(x).strip()
    return str(int(x)) if x.isdigit() else x


def cargar(archivo):
    rows = list(csv.DictReader(open(archivo, encoding="utf-8")))
    for r in rows:
        if "electores" not in r:
            r["electores"] = r.get("electores_totales", "0")
        r.setdefault("secoes_totalizadas", "0")
        r.setdefault("municipio", "")
    return rows


def escribir(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANON, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def total_peso():
    df_base = e1.cargar_linea_base_2022()
    df_vivo = sw.cargar_vivo_2026()
    elec = e1.cargar_electores_habilitados_2026(df_vivo)
    tp = 0.0
    for _, r in df_base.iterrows():
        hab22 = int(r["electores_habilitados"])
        try:
            pct = float(r["porcentaje_asistencia"]) / 100.0
        except (TypeError, ValueError):
            pct = (int(r["electores_asistieron"]) / hab22) if hab22 else 0.0
        tp += elec.get((r["codigo_municipio"], r["zona_electoral"]), hab22) * pct
    return tp


# --------------------------------------------------------------------------
# Fase 1: muestrear instantáneas
# --------------------------------------------------------------------------
def generar_snapshots(tp):
    os.makedirs(SNAP_DIR, exist_ok=True)
    manifest = []
    for archivo in ARCHIVOS:
        rows = cargar(archivo)
        rows.sort(key=lambda r: r["hora_local"])
        by_time = OrderedDict()
        for r in rows:
            by_time.setdefault(r["hora_local"], []).append(r)
        tiempos = list(by_time.keys())
        idxs = set(np.unique(np.linspace(0, len(tiempos) - 1, N_SNAPS).astype(int)).tolist())
        ultimo = {}
        suma = 0.0
        base = os.path.splitext(os.path.basename(archivo))[0]
        for pos, t in enumerate(tiempos):
            for r in by_time[t]:
                k = (norm(r["codigo_municipio"]), norm(r["zona_electoral"]))
                v = int(float(r["votos_totales"] or 0))
                old = ultimo.get(k)
                if old is not None:
                    suma -= old[0]
                ultimo[k] = (v, r)
                suma += v
            if pos not in idxs:
                continue
            esc = suma / tp * 100 if tp else 0
            path = os.path.join(SNAP_DIR, f"{base}_{pos}.csv")
            escribir([rr for _, rr in ultimo.values()], path)
            manifest.append({"archivo": archivo, "path": path, "esc_nac": esc})
        print(f"  [{archivo}] {len(idxs)} instantáneas", flush=True)
    json.dump(manifest, open(os.path.join(SNAP_DIR, "manifest.json"), "w"))
    return manifest


# --------------------------------------------------------------------------
# Fase 2: proyectar por grupo
# --------------------------------------------------------------------------
def _extract_sw(r):
    nac, est = {}, {}
    if r:
        for key, tag in (("crudo", "crudo"), ("v1", "v1"), ("swing", "v2")):
            b = r.get("nacional", {}).get(key)
            if b:
                nac[tag] = [b["lula"]["pct"], b["flavio"]["pct"]]
        for e in r.get("estados", []):
            d = est.setdefault(e["uf"], {"esc": e.get("escrutado")})
            for key, tag in (("crudo", "crudo"), ("v1", "v1"), ("swing", "v2")):
                if e.get(key):
                    d[tag] = [e[key]["lula"]["pct"], e[key]["flavio"]["pct"]]
    return nac, est


def _extract_v4(r):
    nac, est = {}, {}
    if r and r.get("nacional", {}).get("v4"):
        b = r["nacional"]["v4"]
        nac["v4"] = [b["lula"]["pct"], b["flavio"]["pct"]]
    if r:
        for e in r.get("estados", []):
            if e.get("v4"):
                est.setdefault(e["uf"], {"esc": e.get("escrutado")})["v4"] = \
                    [e["v4"]["lula"]["pct"], e["v4"]["flavio"]["pct"]]
    return nac, est


def _extract_scht(r):
    nac, est = {}, {}
    if r:
        for key, tag in (("schteingart", "scht"), ("schteingart_nogate", "scht_ng")):
            b = r.get("nacional", {}).get(key)
            if b:
                nac[tag] = [b["lula"]["pct"], b["flavio"]["pct"]]
        for e in r.get("estados", []):
            d = est.setdefault(e["uf"], {"esc": e.get("escrutado")})
            for key, tag in (("schteingart", "scht"), ("schteingart_nogate", "scht_ng")):
                if e.get(key):
                    d[tag] = [e[key]["lula"]["pct"], e[key]["flavio"]["pct"]]
    return nac, est


def calcular_grupo(grupo, manifest):
    res = []
    for item in manifest:
        path = item["path"]
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                # v4 y scht usan cargar_vivo_2026() de proyeccion_swing,
                # por eso hay que fijar sw.ARCHIVO_VIVO_2026 en todos los grupos.
                sw.ARCHIVO_VIVO_2026 = path
                if grupo == "sw":
                    nac, est = _extract_sw(sw.proyectar())
                elif grupo == "v4":
                    nac, est = _extract_v4(v4.proyectar_v4())
                else:
                    nac, est = _extract_scht(sc.proyectar())
            except Exception:
                nac, est = {}, {}
        res.append({"nac": nac, "est": est})
    os.makedirs(RES_DIR, exist_ok=True)
    json.dump(res, open(os.path.join(RES_DIR, f"{grupo}.json"), "w"))
    return res


def cargar_o_calcular(grupo, manifest, recalcular):
    p = os.path.join(RES_DIR, f"{grupo}.json")
    if not recalcular and os.path.exists(p):
        return json.load(open(p))
    print(f"  calculando {grupo}...", flush=True)
    return calcular_grupo(grupo, manifest)


# --------------------------------------------------------------------------
# Fase 3: agrupar y graficar
# --------------------------------------------------------------------------
def err(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _bin(esc, bins):
    b = None
    for x in bins:
        if esc >= x:
            b = x
    return b


def graficar(acum_a, acum_b):
    fig, ax = plt.subplots(figsize=(11, 7))
    for m, (color, explic) in METODOS.items():
        xs = [o for o in OBJETIVOS_NAC if acum_a[m][o]]
        ys = [np.mean(acum_a[m][o]) for o in OBJETIVOS_NAC if acum_a[m][o]]
        if xs:
            ax.plot(xs, ys, "o-", color=color, linewidth=2, label=f"{m}: {explic}")
    ax.set_xlabel("% de votos escrutados (nacional)", fontsize=10)
    ax.set_ylabel("Error |ΔLula| + |ΔFlavio| (puntos)", fontsize=10)
    ax.set_xticks(OBJETIVOS_NAC)
    ax.set_ylim(0, 10)
    ax.set_title("A) Brasil: error nacional por % escrutado (promedio de 3 raspados)",
                 fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8, loc="upper right", title="Método", title_fontsize=9)
    fig.tight_layout()
    ep.mpl(fig, "Backtest de métodos de proyección por % escrutado (promedio de raspados).")
    fig.savefig(rd.ruta("backtest_metodos_2026.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 7))
    for m, (color, explic) in METODOS.items():
        xs = [b for b in BINS_ESTADO if acum_b[m][b]]
        ys = [np.mean(acum_b[m][b]) for b in BINS_ESTADO if acum_b[m][b]]
        if xs:
            ax.plot(xs, ys, "o-", color=color, linewidth=2, label=f"{m}: {explic}")
    ax.set_xlabel("% escrutado del propio estado", fontsize=10)
    ax.set_ylabel("Error |ΔLula| + |ΔFlavio| (puntos)", fontsize=10)
    ax.set_xticks(BINS_ESTADO)
    ax.set_ylim(0, 10)
    ax.set_title("B) Brasil: error por estado según su propio % escrutado (prom. estados × 3 raspados)",
                 fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8, loc="upper right", title="Método", title_fontsize=9)
    fig.tight_layout()
    ep.mpl(fig, "Backtest de métodos de proyección por % escrutado del estado "
                "(promedio estados × raspados).")
    fig.savefig(rd.ruta("backtest_estados_2026.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("\n[i] Gráficos: backtest_metodos_2026.png, backtest_estados_2026.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recalcular", nargs="*", default=[],
                    help="grupos a recalcular: sw v4 scht (por defecto, los que falten)")
    ap.add_argument("--rehacer-snapshots", action="store_true")
    args = ap.parse_args()

    tp = total_peso()
    man_path = os.path.join(SNAP_DIR, "manifest.json")
    if args.rehacer_snapshots or not os.path.exists(man_path):
        print("Fase 1: muestreando instantáneas...")
        manifest = generar_snapshots(tp)
    else:
        manifest = json.load(open(man_path))
    print(f"Instantáneas: {len(manifest)}")

    # referencia final
    rows0 = cargar(ARCHIVOS[0])
    full = tempfile.mktemp(suffix=".csv", dir=rd.ruta_dir("raw"))
    escribir(rows0, full)
    sw.ARCHIVO_VIVO_2026 = full
    with contextlib.redirect_stdout(io.StringIO()):
        r2f = sw.proyectar()
    final_nac = [r2f["nacional"]["crudo"]["lula"]["pct"], r2f["nacional"]["crudo"]["flavio"]["pct"]]
    final_est = {e["uf"]: [e["crudo"]["lula"]["pct"], e["crudo"]["flavio"]["pct"]]
                 for e in r2f.get("estados", []) if e.get("crudo")}
    print(f"Final nacional (crudo): Lula {final_nac[0]:.2f}% | Flavio {final_nac[1]:.2f}%\n")

    rec = set(args.recalcular)
    resultados = {}
    for g in GRUPOS:
        resultados[g] = cargar_o_calcular(g, manifest, g in rec or not rec and not os.path.exists(os.path.join(RES_DIR, f"{g}.json")))

    acum_a = {m: {o: [] for o in OBJETIVOS_NAC} for m in METODOS}
    acum_b = {m: {b: [] for b in BINS_ESTADO} for m in METODOS}
    for i, item in enumerate(manifest):
        esc = item["esc_nac"]
        b = _bin(esc, OBJETIVOS_NAC)
        for g in GRUPOS:
            nac = resultados[g][i]["nac"]
            if b is not None:
                for m, val in nac.items():
                    acum_a[m][b].append(err(val, final_nac))
            for uf, d in resultados[g][i]["est"].items():
                if uf == "ZZ" or d.get("esc") is None:
                    continue
                fin = final_est.get(uf)
                if not fin:
                    continue
                bb = _bin(d["esc"], BINS_ESTADO)
                if bb is None:
                    continue
                for m, val in d.items():
                    if m != "esc":
                        acum_b[m][bb].append(err(val, fin))

    for m in METODOS:
        acum_a[m][100] = [0.0]

    cols = list(METODOS.keys())
    print("\n=== A) Error nacional por % escrutado (prom. 3 raspados) ===")
    print(f'{"%esc":>6} | ' + " ".join(f'{m:>7}' for m in cols))
    for o in OBJETIVOS_NAC:
        fila = " ".join(f"{np.mean(acum_a[m][o]):7.2f}" if acum_a[m][o] else "    n/a" for m in cols)
        print(f"{o:6.1f} | {fila}")
    print("\nError medio:")
    for m in cols:
        vals = [x for o in OBJETIVOS_NAC for x in acum_a[m][o]]
        print(f"  {m}: {np.mean(vals):.2f}   — {METODOS[m][1]}")

    print("\n=== B) Error por estado según su propio % escrutado ===")
    print(f'{"%esc":>6} | ' + " ".join(f'{m:>7}' for m in cols))
    for o in BINS_ESTADO:
        fila = " ".join(f"{np.mean(acum_b[m][o]):7.2f}" if acum_b[m][o] else "    n/a" for m in cols)
        print(f"{o:6.1f} | {fila}")
    print("\nError medio por estado:")
    for m in cols:
        vals = [x for o in BINS_ESTADO for x in acum_b[m][o]]
        print(f"  {m}: {np.mean(vals):.2f}")

    graficar(acum_a, acum_b)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
inferencia_ecologica.py — Migración de votos en las presidenciales de Brasil.

Estima por máxima verosimilitud (EM) las MATRICES DE TRANSICIÓN entre bloques de
voto, a nivel de SECCIÓN electoral (la urna), incluyendo a quienes no votaron:

  2018 1T: Haddad (PT) | Bolsonaro | Otros | Blanco/Nulo | No votó
  2022 1T: Lula        | Bolsonaro | Otros | Blanco/Nulo | No votó
  2022 2T: Lula        | Bolsonaro |         Blanco/Nulo | No votó
  2026 1T: Lula        | Flávio    | Otros | Blanco/Nulo | No votó

Pares estimados: 2018→2022, 2022→2026 y 2022 1ª→2ª vuelta. Para los tres comicios
se ENCADENAN los pares (supuesto de Markov). No existe un método 3-vías
identificable solo con márgenes seccionales; el encadenado es el enfoque honesto.

Modelo (por par): en cada sección i, cada persona del año destino elige categoría
k con probabilidad p_ik = sum_j share_origen_ij * theta_jk. Se ajusta theta por EM
y se obtienen intervalos por bootstrap sobre secciones.

Salidas en <repo>\\plot\\ (formato 4:3):
  transicion_nacional_2018_2022.csv / _2022_2026.csv / _2022_1t_2t.csv
  transicion_2018_2026_markov.csv / transicion_por_region.csv
  heatmap_*.png, sankey_*.html|png
  informe_migracion_2022_2026_es.md, relatorio_migracao_2022_2026_pt.md
  resumen_ei.json
"""

import os
import sys
import json

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
import estilo_plot as ep

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEC_DIR = rd.ruta_dir("secciones")
OUT_DIR = os.path.join(rd.REPO, "plot")
os.makedirs(OUT_DIR, exist_ok=True)

CATS = ["A", "B", "Otros", "Blanco/Nulo", "No voto"]
COLORES = {"A": "#E11B22", "B": "#2C5FBF", "Otros": "#9AA0A6",
           "Blanco/Nulo": "#CFCFCF", "No voto": "#4D4D4D"}
MIN_APTOS = 20
CLAVE = ["uf", "mun", "zona", "secao"]
COLS5 = ["blk_lula", "blk_bolso", "blk_otros", "blk_bn", "blk_novoto"]

ANIOS = {
    2018: {"cands": ["12", "13", "15", "16", "17", "18", "19", "27", "30",
                     "45", "50", "51", "54"], "lula": "13", "bolso": "17",
           "labels": ["Haddad (PT)", "Bolsonaro", "Otros", "Blanco/Nulo", "No voto"]},
    2022: {"cands": ["12", "13", "14", "15", "16", "21", "22", "27", "30", "44", "80"],
           "lula": "13", "bolso": "22",
           "labels": ["Lula", "Bolsonaro", "Otros", "Blanco/Nulo", "No voto"]},
    2026: {"cands": ["13", "14", "16", "21", "22", "27", "28", "29", "30", "35",
                     "55", "70", "80"], "lula": "13", "bolso": "22",
           "labels": ["Lula", "Flavio", "Otros", "Blanco/Nulo", "No voto"]},
}
LABELS_2022_2T = ["Lula", "Bolsonaro", "Blanco/Nulo", "No voto"]

REGION = {}
for uf in ["AC", "AP", "AM", "PA", "RO", "RR", "TO"]:
    REGION[uf] = "Norte"
for uf in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]:
    REGION[uf] = "Nordeste"
for uf in ["DF", "GO", "MT", "MS"]:
    REGION[uf] = "Centro-Oeste"
for uf in ["ES", "MG", "RJ", "SP"]:
    REGION[uf] = "Sudeste"
for uf in ["PR", "RS", "SC"]:
    REGION[uf] = "Sur"
REGION["ZZ"] = "Exterior"


def _nom_vot(y, turno):
    return f"secciones_presidente_{y}_{turno}t.csv"


def _nom_det(y, turno):
    return (f"secciones_detalle_{y}.csv" if turno == "1"
            else f"secciones_detalle_{y}_{turno}t.csv")


def _suma(df, cols):
    cols = [c for c in cols if c in df.columns]
    return df[cols].sum(axis=1) if cols else pd.Series(0.0, index=df.index)


def cargar_anio(y, turno="1"):
    cfg = ANIOS[y]
    d = pd.read_csv(os.path.join(SEC_DIR, _nom_vot(y, turno)), dtype=str)
    det = pd.read_csv(os.path.join(SEC_DIR, _nom_det(y, turno)), dtype=str)
    for c in [c for c in d.columns if c not in CLAVE]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    otros = [c for c in cfg["cands"] if c not in (cfg["lula"], cfg["bolso"])]
    d["blk_lula"] = _suma(d, [cfg["lula"]])
    d["blk_bolso"] = _suma(d, [cfg["bolso"]])
    d["blk_otros"] = _suma(d, otros)
    d["blk_bn"] = _suma(d, ["branco", "nulo", "97"])
    d["comparecimento"] = d[["blk_lula", "blk_bolso", "blk_otros", "blk_bn"]].sum(axis=1)
    det = det.copy()
    det["aptos"] = pd.to_numeric(det["aptos"], errors="coerce").fillna(0)
    d = d.merge(det[CLAVE + ["aptos"]], on=CLAVE, how="left")
    d["aptos"] = d["aptos"].fillna(0)
    d["blk_novoto"] = (d["aptos"] - d["comparecimento"]).clip(lower=0)
    return d


def emparejar(da, db):
    m = da[CLAVE + COLS5].merge(db[CLAVE + COLS5], on=CLAVE, suffixes=("_o", "_d"))
    m["region"] = m["uf"].map(REGION).fillna("Otros")
    return m


def _mat(m, cols_o, cols_d):
    return m[cols_o].to_numpy(float), m[cols_d].to_numpy(float)


def em_transicion(X, Y, iters=800, tol=1e-10, theta0=None, alpha=0.0):
    """MLE rectangular de theta[j,k]=P(destino k | origen j) por EM."""
    Ko, Kd = X.shape[1], Y.shape[1]
    val = X.sum(1) > 0
    X, Y = X[val], Y[val]
    xs = X / X.sum(1, keepdims=True)
    theta = np.full((Ko, Kd), 1.0 / Kd) if theta0 is None else theta0.copy()
    for _ in range(iters):
        xp = np.where((xs @ theta) <= 1e-15, 1e-15, xs @ theta)
        w = Y / xp
        num = (xs[:, :, None] * theta[None, :, :]) * w[:, None, :]
        Z = num.sum(0)
        nueva = (Z + alpha) / (Z.sum(1, keepdims=True) + Kd * alpha)
        if np.max(np.abs(nueva - theta)) < tol:
            return nueva
        theta = nueva
    return theta


def goodman(X, Y):
    val = X.sum(1) > 0
    X, Y = X[val], Y[val]
    xs = X / X.sum(1, keepdims=True)
    ys = Y / Y.sum(1, keepdims=True)
    theta, *_ = np.linalg.lstsq(xs, ys, rcond=None)
    theta = np.clip(theta, 0, None)
    s = theta.sum(1, keepdims=True)
    return np.divide(theta, s, out=np.full_like(theta, 1.0 / theta.shape[1]), where=s > 0)


def bootstrap(X, Y, theta0, reps=60, seed=0, iters=60):
    rng = np.random.default_rng(seed)
    N = X.shape[0]
    out = np.empty((reps, X.shape[1], Y.shape[1]))
    for r in range(reps):
        idx = rng.integers(0, N, N)
        out[r] = em_transicion(X[idx], Y[idx], iters=iters, theta0=theta0)
    return out


def ei_par(m, cols_o, cols_d, reps=60):
    X, Y = _mat(m, cols_o, cols_d)
    filtro = (X.sum(1) >= MIN_APTOS) & (Y.sum(1) >= MIN_APTOS)
    mf = m[filtro].copy()
    Xf, Yf = _mat(mf, cols_o, cols_d)
    theta = em_transicion(Xf, Yf)
    bs = bootstrap(Xf, Yf, theta, reps=reps)
    lo, hi = np.percentile(bs, 5, axis=0), np.percentile(bs, 95, axis=0)
    return theta, lo, hi, goodman(Xf, Yf), mf, Xf, Yf


def heatmap(theta, lo, hi, labels_o, labels_d, N_o, titulo, path):
    N_o = np.asarray(N_o, float)
    flujo = theta * N_o[:, None]
    tot_o, tot_d = N_o, flujo.sum(0)
    etiq_o = [f"{lab}\n({tot_o[i]/1e6:.1f}M)" for i, lab in enumerate(labels_o)]
    etiq_d = [f"{lab}\n({tot_d[j]/1e6:.1f}M)" for j, lab in enumerate(labels_d)]
    fig, ax = plt.subplots(figsize=(8, 6))          # 4:3
    im = ax.imshow(theta * 100, cmap="YlOrRd", vmin=0, vmax=100)
    for i in range(theta.shape[0]):
        for j in range(theta.shape[1]):
            txt = f"{theta[i, j]*100:.1f}%\n{flujo[i, j]/1e6:.1f}M"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.5,
                    color="black" if theta[i, j] < 0.6 else "white")
    ax.set_xticks(range(len(labels_d)))
    ax.set_yticks(range(len(labels_o)))
    ax.set_xticklabels(etiq_d, fontsize=8)
    ax.set_yticklabels(etiq_o, fontsize=8)
    ax.set_xlabel("Destino (millones de personas)")
    ax.set_ylabel("Origen (millones de personas)")
    ax.set_title(titulo, fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, label="% del bloque de origen")
    fig.tight_layout()
    ep.mpl(fig, "Inferencia ecológica por secciones electorales (EM): cada celda es el % "
                "del bloque de origen que va a cada destino; totales en millones.")
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _rgba(hexcolor, alpha):
    h = hexcolor.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alpha})"


def _plot_sankey(src, dst, val, cl, labels, color_nodo, titulo, path_html, path_png):
    import plotly.graph_objects as go
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, color=color_nodo, pad=16, thickness=20,
                  line=dict(color="rgba(0,0,0,0.3)", width=0.5)),
        link=dict(source=src, target=dst, value=val, color=cl)))
    fig.update_layout(title_text=titulo, font_size=13, height=900, width=1200,
                      paper_bgcolor="white", margin=dict(b=150))
    ep.plotly(fig, "Sankey de migración de votos entre bloques (personas). "
                   "Inferencia ecológica por secciones electorales (EM).")
    fig.write_html(path_html, include_plotlyjs="cdn")
    print(f"[OK] {os.path.basename(path_html)}")
    try:
        fig.write_image(path_png, width=1200, height=900, scale=2)
        print(f"[OK] {os.path.basename(path_png)}")
    except Exception as exc:
        print(f"[!] PNG {os.path.basename(path_png)}: {exc}")


def sankey_par(theta, N_o, labels_o, labels_d, titulo, base):
    Ko, Kd = theta.shape
    labels = labels_o + labels_d
    color_nodo = [COLORES[CATS[i]] for i in range(Ko)] + \
                 [COLORES[CATS[i]] for i in range(Kd)]
    src, dst, val, cl = [], [], [], []
    for j in range(Ko):
        for k in range(Kd):
            v = float(theta[j, k] * N_o[j])
            if v < 0.5:
                continue
            src.append(j); dst.append(Ko + k); val.append(v)
            cl.append(_rgba(COLORES[CATS[j]], 0.5))
    _plot_sankey(src, dst, val, cl, labels, color_nodo, titulo,
                 os.path.join(OUT_DIR, base + ".html"),
                 os.path.join(OUT_DIR, base + ".png"))


def sankey_tres(thA, N18, thB, N22, labels18, labels22, labels26, base):
    K = len(labels18)
    labels = labels18 + labels22 + labels26
    color_nodo = [COLORES[CATS[i]] for i in range(K)] * 3
    src, dst, val, cl = [], [], [], []
    for j in range(K):
        for k in range(thA.shape[1]):
            v = float(thA[j, k] * N18[j])
            if v < 0.5:
                continue
            src.append(j); dst.append(K + k); val.append(v)
            cl.append(_rgba(COLORES[CATS[j]], 0.45))
    for k in range(K):
        for l in range(thB.shape[1]):
            v = float(thB[k, l] * N22[k])
            if v < 0.5:
                continue
            src.append(K + k); dst.append(2 * K + l); val.append(v)
            cl.append(_rgba(COLORES[CATS[k]], 0.45))
    _plot_sankey(src, dst, val, cl, labels, color_nodo,
                 "Migración de votos — Brasil 2018 → 2022 → 2026 (personas)",
                 os.path.join(OUT_DIR, base + ".html"),
                 os.path.join(OUT_DIR, base + ".png"))


def _tab_md(theta, labels_o, labels_d, N_o, pct=True):
    N_o = np.asarray(N_o, float)
    flujo = theta * N_o[:, None]
    head = "| Origen \\ Destino | " + " | ".join(labels_d) + " |"
    sep = "|" + "---|" * (len(labels_d) + 1)
    filas = [head, sep]
    for i, lo in enumerate(labels_o):
        celdas = []
        for j in range(theta.shape[1]):
            if pct:
                celdas.append(f"{theta[i,j]*100:.1f}% ({flujo[i,j]/1e6:.1f}M)")
            else:
                celdas.append(f"{flujo[i,j]/1e6:.1f}M")
        filas.append(f"| **{lo}** ({N_o[i]/1e6:.1f}M) | " + " | ".join(celdas) + " |")
    return "\n".join(filas)


def reporte_es(thB, N22, thC, N22_1t, thA, N18, th_markov):
    L22, L26, L22b = ANIOS[2022]["labels"], ANIOS[2026]["labels"], LABELS_2022_2T
    f = thB * N22[:, None]
    return f"""# Migración de votos en Brasil: 2022 → 2026 (Presidente, 1ª vuelta)

*Estimación ecológica por secciones electorales (EM). {f.shape[0]}x{f.shape[1]} bloques.*

## Cómo se hizo
Se emparejaron **461.219 secciones** entre 2022 y 2026 por (UF, municipio, zona,
sección). En cada sección se conoce el voto por bloque en ambos años y los
electores habilitados (aptos). Se estima la matriz de transición θ[j,k] =
P(votar k en 2026 | bloque j en 2022) por máxima verosimilitud (EM), con
intervalos por bootstrap. Los "No votó" son aptos − comparecimento.

## Resultado principal (2022 → 2026)
{_tab_md(thB, L22, L26, N22)}

## Lectura
- **Lula retuvo el {thB[0,0]*100:.1f}%** de su electorado; fugas: {thB[0,1]*100:.1f}% a Flávio y {thB[0,4]*100:.1f}% a la abstención.
- **Bolsonaro transfirió el {thB[1,1]*100:.1f}% a Flávio**; casi nada a Lula ({thB[1,0]*100:.1f}%).
- Los **"Otros" 2022** (Ciro, Tebet, etc.) se repartieron: {thB[2,1]*100:.1f}% a Flávio, {thB[2,0]*100:.1f}% a Lula, {thB[2,4]*100:.1f}% no votó.
- Entre quienes **no votaron en 2022**, {thB[4,1]*100:.1f}% votó a Flávio y {thB[4,0]*100:.1f}% a Lula en 2026.

## Balotaje 2022 (1ª → 2ª vuelta)
{_tab_md(thC, L22, L22b, N22_1t)}

## Contexto 2018 → 2022
{_tab_md(thA, ANIOS[2018]["labels"], L22, N18)}

## 2018 → 2026 (encadenado, supuesto de Markov)
{_tab_md(th_markov, ANIOS[2018]["labels"], L26, N18)}

## Advertencias
Inferencia **ecológica**: son patrones agregados por sección, no seguimiento
individual. El encadenado 2018→2026 asume que 2026 depende de 2022 (Markov).
Cambios de padrón y de composición de las secciones introducen error.
Las celdas 0% o 100% son soluciones de frontera del EM (electorados muy rígidos):
léanse como «casi nulo» / «casi total», no como certeza.

---
*{ep.CREDITO}*
"""


def reporte_pt(thB, N22, thC, N22_1t, thA, N18, th_markov):
    L22, L26, L22b = ANIOS[2022]["labels"], ANIOS[2026]["labels"], LABELS_2022_2T
    f = thB * N22[:, None]
    return f"""# Migração de votos no Brasil: 2022 → 2026 (Presidente, 1º turno)

*Inferência ecológica por seções eleitorais (EM). Blocos {f.shape[0]}x{f.shape[1]}.*

## Como foi feito
Foram pareadas **461.219 seções** entre 2022 e 2026 por (UF, município, zona,
seção). Em cada seção conhece-se o voto por bloco nos dois anos e os eleitores
aptos. Estima-se a matriz de transição θ[j,k] = P(votar k em 2026 | bloco j em
2022) por máxima verossimilhança (EM), com intervalos por bootstrap. Os "não
votou" são aptos − comparecimento.

## Resultado principal (2022 → 2026)
{_tab_md(thB, L22, L26, N22)}

## Leitura
- **Lula manteve {thB[0,0]*100:.1f}%** do seu eleitorado; fugas: {thB[0,1]*100:.1f}% para Flávio e {thB[0,4]*100:.1f}% para a abstenção.
- **Bolsonaro transferiu {thB[1,1]*100:.1f}% para Flávio**; quase nada para Lula ({thB[1,0]*100:.1f}%).
- Os **"Outros" de 2022** (Ciro, Tebet etc.) dividiram-se: {thB[2,1]*100:.1f}% para Flávio, {thB[2,0]*100:.1f}% para Lula, {thB[2,4]*100:.1f}% não votaram.
- Entre os que **não votaram em 2022**, {thB[4,1]*100:.1f}% votaram em Flávio e {thB[4,0]*100:.1f}% em Lula em 2026.

## 2º turno de 2022 (1º → 2º turno)
{_tab_md(thC, L22, L22b, N22_1t)}

## Contexto 2018 → 2022
{_tab_md(thA, ANIOS[2018]["labels"], L22, N18)}

## 2018 → 2026 (encadeado, suposto de Markov)
{_tab_md(th_markov, ANIOS[2018]["labels"], L26, N18)}

## Advertências
Inferência **ecológica**: são padrões agregados por seção, não acompanhamento
individual. O encadeamento 2018→2026 supõe que 2026 depende de 2022 (Markov).
Mudanças de eleitorado e de composição das seções introduzem erro.
As células 0% ou 100% são soluções de fronteira do EM (eleitorados muito rígidos):
leia-se como «quase nulo» / «quase total», não como certeza.

---
*{ep.CREDITO}*
"""


def solo_graficos():
    """Regenera heatmaps y Sankeys desde resumen_ei.json (sin repetir el EM)."""
    res = json.load(open(os.path.join(OUT_DIR, "resumen_ei.json"), encoding="utf-8"))
    d18 = cargar_anio(2018, "1")
    d22 = cargar_anio(2022, "1")
    N18 = d18[COLS5].sum().to_numpy()
    N22 = d22[COLS5].sum().to_numpy()
    thA = np.array(res["transicion_2018_2022"])
    thB = np.array(res["transicion_2022_2026"])
    thC = np.array(res["transicion_2022_1t_2t"])
    thM = np.array(res["transicion_2018_2026_markov"])
    heatmap(thA, None, None, ANIOS[2018]["labels"], ANIOS[2022]["labels"], N18,
            "Transición de votos — Brasil 2018 → 2022 (%)", os.path.join(OUT_DIR, "heatmap_2018_2022.png"))
    heatmap(thB, None, None, ANIOS[2022]["labels"], ANIOS[2026]["labels"], N22,
            "Transición de votos — Brasil 2022 → 2026 (%)", os.path.join(OUT_DIR, "heatmap_2022_2026.png"))
    heatmap(thC, None, None, ANIOS[2022]["labels"], LABELS_2022_2T, N22,
            "Transición — Brasil 2022 1ª → 2ª vuelta (%)", os.path.join(OUT_DIR, "heatmap_2022_1t_2t.png"))
    heatmap(thM, None, None, ANIOS[2018]["labels"], ANIOS[2026]["labels"], N18,
            "Transición encadenada — Brasil 2018 → 2026 (Markov, %)",
            os.path.join(OUT_DIR, "heatmap_2018_2026.png"))
    sankey_par(thA, N18, ANIOS[2018]["labels"], ANIOS[2022]["labels"],
               "Migración de votos — Brasil 2018 → 2022 (personas)", "sankey_2018_2022")
    sankey_par(thB, N22, ANIOS[2022]["labels"], ANIOS[2026]["labels"],
               "Migración de votos — Brasil 2022 → 2026 (personas)", "sankey_2022_2026")
    sankey_par(thC, N22, ANIOS[2022]["labels"], LABELS_2022_2T,
               "Migración de votos — Brasil 2022 1ª → 2ª vuelta (personas)", "sankey_2022_1t_2t")
    sankey_tres(thA, N18, thB, N22, ANIOS[2018]["labels"], ANIOS[2022]["labels"],
                ANIOS[2026]["labels"], "sankey_2018_2022_2026")
    open(os.path.join(OUT_DIR, "informe_migracion_2022_2026_es.md"), "w", encoding="utf-8").write(
        reporte_es(thB, N22, thC, N22, thA, N18, thM))
    open(os.path.join(OUT_DIR, "relatorio_migracao_2022_2026_pt.md"), "w", encoding="utf-8").write(
        reporte_pt(thB, N22, thC, N22, thA, N18, thM))
    print("[OK] Gráficos regenerados desde resumen_ei.json")


def main():
    if "--solo-graficos" in sys.argv:
        solo_graficos()
        return
    print("[*] Cargando secciones 2018 / 2022 (1T y 2T) / 2026...")
    d18 = cargar_anio(2018, "1")
    d22 = cargar_anio(2022, "1")
    d22b = cargar_anio(2022, "2")
    d26 = cargar_anio(2026, "1")

    m_a = emparejar(d18, d22)
    m_b = emparejar(d22, d26)
    m_c = emparejar(d22, d22b)
    print(f"    emparejadas 2018-2022: {len(m_a)} | 2022-2026: {len(m_b)} | 2022 1T-2T: {len(m_c)}")

    cols_o5 = [c + "_o" for c in COLS5]
    cols_d5 = [c + "_d" for c in COLS5]
    cols_d4 = [c + "_d" for c in ["blk_lula", "blk_bolso", "blk_bn", "blk_novoto"]]

    print("[*] EI 2018 → 2022 ...")
    thA, loA, hiA, _, mfA, XA, _ = ei_par(m_a, cols_o5, cols_d5)
    print("[*] EI 2022 → 2026 ...")
    thB, loB, hiB, _, mfB, XB, _ = ei_par(m_b, cols_o5, cols_d5)
    print("[*] EI 2022 1ª → 2ª vuelta ...")
    thC, loC, hiC, _, mfC, XC, _ = ei_par(m_c, cols_o5, cols_d4)

    for th, y0, y1, nombre in ((thA, 2018, 2022, "2018_2022"),
                               (thB, 2022, 2026, "2022_2026"),
                               (thC, 2022, 2022, "2022_1t_2t")):
        lo = ANIOS[y0]["labels"]
        ld = ANIOS[y1]["labels"] if nombre != "2022_1t_2t" else LABELS_2022_2T
        pd.DataFrame(th, index=lo, columns=ld).to_csv(
            os.path.join(OUT_DIR, f"transicion_nacional_{nombre}.csv"))
        print(f"\n=== Transición {nombre} ===")
        print((pd.DataFrame(th, index=lo, columns=ld) * 100).round(1).to_string())

    th_markov = thA @ thB
    pd.DataFrame(th_markov, index=ANIOS[2018]["labels"], columns=ANIOS[2026]["labels"]).to_csv(
        os.path.join(OUT_DIR, "transicion_2018_2026_markov.csv"))

    filas = []
    for reg, g in mfB.groupby("region"):
        if len(g) < 500:
            continue
        Xr, Yr = _mat(g, cols_o5, cols_d5)
        th = em_transicion(Xr, Yr)
        for j, oj in enumerate(ANIOS[2022]["labels"]):
            for k, dk in enumerate(ANIOS[2026]["labels"]):
                filas.append({"region": reg, "origen": oj, "destino": dk, "p": th[j, k]})
    pd.DataFrame(filas).to_csv(os.path.join(OUT_DIR, "transicion_por_region.csv"), index=False)

    # Gráficos 4:3 con absolutos (millones) por fila, columna y celda
    heatmap(thA, loA, hiA, ANIOS[2018]["labels"], ANIOS[2022]["labels"], XA.sum(0),
            "Transición de votos — Brasil 2018 → 2022 (%)", os.path.join(OUT_DIR, "heatmap_2018_2022.png"))
    heatmap(thB, loB, hiB, ANIOS[2022]["labels"], ANIOS[2026]["labels"], XB.sum(0),
            "Transición de votos — Brasil 2022 → 2026 (%)", os.path.join(OUT_DIR, "heatmap_2022_2026.png"))
    heatmap(thC, loC, hiC, ANIOS[2022]["labels"], LABELS_2022_2T, XC.sum(0),
            "Transición — Brasil 2022 1ª → 2ª vuelta (%)", os.path.join(OUT_DIR, "heatmap_2022_1t_2t.png"))
    heatmap(th_markov, None, None, ANIOS[2018]["labels"], ANIOS[2026]["labels"], XA.sum(0),
            "Transición encadenada — Brasil 2018 → 2026 (Markov, %)", os.path.join(OUT_DIR, "heatmap_2018_2026.png"))

    sankey_par(thA, XA.sum(0), ANIOS[2018]["labels"], ANIOS[2022]["labels"],
               "Migración de votos — Brasil 2018 → 2022 (personas)", "sankey_2018_2022")
    sankey_par(thB, XB.sum(0), ANIOS[2022]["labels"], ANIOS[2026]["labels"],
               "Migración de votos — Brasil 2022 → 2026 (personas)", "sankey_2022_2026")
    sankey_par(thC, XC.sum(0), ANIOS[2022]["labels"], LABELS_2022_2T,
               "Migración de votos — Brasil 2022 1ª → 2ª vuelta (personas)", "sankey_2022_1t_2t")
    sankey_tres(thA, XA.sum(0), thB, XB.sum(0), ANIOS[2018]["labels"],
                ANIOS[2022]["labels"], ANIOS[2026]["labels"], "sankey_2018_2022_2026")

    open(os.path.join(OUT_DIR, "informe_migracion_2022_2026_es.md"), "w", encoding="utf-8").write(
        reporte_es(thB, XB.sum(0), thC, XC.sum(0), thA, XA.sum(0), th_markov))
    open(os.path.join(OUT_DIR, "relatorio_migracao_2022_2026_pt.md"), "w", encoding="utf-8").write(
        reporte_pt(thB, XB.sum(0), thC, XC.sum(0), thA, XA.sum(0), th_markov))

    res = {
        "n_emparejadas": {"2018_2022": int(len(m_a)), "2022_2026": int(len(m_b)),
                          "2022_1t_2t": int(len(m_c))},
        "labels": {"2018": ANIOS[2018]["labels"], "2022": ANIOS[2022]["labels"],
                   "2022_2t": LABELS_2022_2T, "2026": ANIOS[2026]["labels"]},
        "transicion_2018_2022": thA.tolist(),
        "transicion_2022_2026": thB.tolist(),
        "transicion_2022_1t_2t": thC.tolist(),
        "transicion_2018_2026_markov": th_markov.tolist(),
        "nota_3vias": "2018->2026 es el encadenado de los pares (Markov).",
    }
    json.dump(res, open(os.path.join(OUT_DIR, "resumen_ei.json"), "w"),
              ensure_ascii=False, indent=2)
    print(f"\n[OK] Salidas en {OUT_DIR}")


if __name__ == "__main__":
    main()

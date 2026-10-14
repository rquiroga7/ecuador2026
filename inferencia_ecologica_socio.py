# -*- coding: utf-8 -*-
"""
inferencia_ecologica_socio.py — ¿Cambian los resultados de inferencia ecológica
cuando incorporamos datos económicos y sociales?

Datos socioeconómicos (municipio, Censo 2022), de dschteingart/el-atlas-charts
(brasil-2026/data/socio.js):
  bf        familias con Bolsa Família cada 100 hogares (oct-2022)
  ingreso   ingreso mensual por persona del hogar (mediana, R$)
  raza      % blancos
  religion  % evangélicos
  univ      % universitarios 25+

Se cruzan con los votos por municipio (2022 1ª vuelta vs 2026 1ª vuelta) y con
las secciones electorales, para:
  1) Correlaciones y regresión del swing de Lula/Flávio contra los factores
     (con y sin efectos fijos de estado).
  2) Inferencia ecológica ESTRATIFICADA: matriz de transición por quintil de cada
     factor, y comparación con la matriz nacional (¿la modifica?).

Salidas en <repo>\\plot\\ (4:3):
  socio_municipios.csv, socio_regresion.csv, socio_ei_quintiles.csv
  socio_panel.png, socio_ei_quintiles.png
  informe_socio_es.md, relatorio_socio_pt.md
"""

import os
import sys
import json

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
import inferencia_ecologica as ie
import estilo_plot as ep

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SOCIO_DIR = rd.ruta_dir("socio")
OUT = ie.OUT_DIR
COLS_O = [c + "_o" for c in ie.COLS5]
COLS_D = [c + "_d" for c in ie.COLS5]
VARS = ["ingreso", "raza", "religion", "univ"]
NOMBRES = {"bf": "Bolsa Família (por 100 hog.)", "ingreso": "Ingreso per cápita",
           "raza": "% blancos", "religion": "% evangélicos", "univ": "% universitarios"}


def cargar_socio():
    txt = open(os.path.join(SOCIO_DIR, "socio.js"), encoding="utf-8").read()
    obj = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    orden = obj["orden"]
    filas = [{"ibge": str(k), **{orden[i]: v[i] for i in range(len(orden))}}
             for k, v in obj["mun"].items()]
    return pd.DataFrame(filas), orden


def cargar_tse_ibge():
    with open(os.path.join(rd.REPO, "data", "tse_ibge.json"), encoding="utf-8") as f:
        d = json.load(f)
    return {int(k): str(v) for k, v in d.items()}


def municipios(y, turno="1"):
    d = ie.cargar_anio(y, turno)
    g = d.groupby("mun", as_index=False).agg(
        uf=("uf", "first"), lula=("blk_lula", "sum"), bolso=("blk_bolso", "sum"),
        otros=("blk_otros", "sum"), bn=("blk_bn", "sum"), aptos=("aptos", "sum"))
    g["validos"] = g[["lula", "bolso", "otros"]].sum(axis=1)
    g["comparecimento"] = g["validos"] + g["bn"]
    g["lula_pct"] = 100 * g["lula"] / g["validos"].replace(0, np.nan)
    g["bolso_pct"] = 100 * g["bolso"] / g["validos"].replace(0, np.nan)
    g["turnout"] = 100 * g["comparecimento"] / g["aptos"].replace(0, np.nan)
    return g


def dataset_municipal():
    m22, m26 = municipios(2022), municipios(2026)
    m = m22[["mun", "uf", "lula_pct", "bolso_pct", "turnout", "validos", "aptos"]].merge(
        m26[["mun", "lula_pct", "bolso_pct", "turnout", "validos"]],
        on="mun", suffixes=("_22", "_26"))
    mapa = cargar_tse_ibge()
    m["ibge"] = m["mun"].map(lambda x: mapa.get(int(x)))
    socio, _ = cargar_socio()
    m = m.merge(socio, on="ibge", how="left")
    m["swing_lula"] = m["lula_pct_26"] - m["lula_pct_22"]
    m["swing_flavio"] = m["flavio_pct"] - m["bolso_pct_22"] if "flavio_pct" in m else \
        m["bolso_pct_26"] - m["bolso_pct_22"]
    m["log_votos"] = np.log10(m["validos_22"].clip(lower=1))
    m["ingreso_log"] = np.log10(m["ingreso"].clip(lower=1))
    return m


def _z(s):
    return (s - s.mean()) / s.std(ddof=0)


def ols_fe(df, ycol, xcols, fe="uf"):
    d = df.dropna(subset=[ycol] + xcols + [fe]).copy()
    if len(d) < 50:
        return None
    Xs = d[xcols].apply(_z)
    y = d[ycol].to_numpy(float)
    dummies = pd.get_dummies(d[fe], drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(d)), Xs.to_numpy(float), dummies])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    xtx = np.linalg.pinv(X.T @ X)
    cov = xtx @ (X.T @ (X * (resid ** 2)[:, None])) @ xtx * n / (n - k)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    filas = []
    for i, x in enumerate(xcols, start=1):
        filas.append({"factor": x, "coef": beta[i], "se": se[i],
                      "t": beta[i] / se[i] if se[i] else np.nan})
    return pd.DataFrame(filas), r2, len(d)


def correlaciones(df, ycol):
    filas = []
    for v in VARS + ["log_votos"]:
        d = df[[ycol, v]].dropna()
        r = np.corrcoef(d[ycol], d[v])[0, 1] if len(d) > 10 else np.nan
        # parcial: residuo tras quitar efectos fijos de estado
        dd = df[[ycol, v, "uf"]].dropna()
        ry = dd[ycol] - dd.groupby("uf")[ycol].transform("mean")
        rv = dd[v] - dd.groupby("uf")[v].transform("mean")
        rp = np.corrcoef(ry, rv)[0, 1] if len(dd) > 10 else np.nan
        filas.append({"factor": v, "corr": r, "corr_intra_estado": rp})
    return pd.DataFrame(filas)


def ei_por_quintiles(m_sec, var, q=5):
    """Matriz 4×4 (Lula, Bolsonaro/Flávio, Otros, No voto/Blanco-Nulo) por quintil."""
    m = m_sec.dropna(subset=[var]).copy()
    m["q"] = pd.qcut(m[var], q, labels=False, duplicates="drop")
    m["b1_o"], m["b2_o"], m["b3_o"] = m["blk_lula_o"], m["blk_bolso_o"], m["blk_otros_o"]
    m["b4_o"] = m["blk_bn_o"] + m["blk_novoto_o"]
    m["b1_d"], m["b2_d"], m["b3_d"] = m["blk_lula_d"], m["blk_bolso_d"], m["blk_otros_d"]
    m["b4_d"] = m["blk_bn_d"] + m["blk_novoto_d"]
    cols_o, cols_d = ["b1_o", "b2_o", "b3_o", "b4_o"], ["b1_d", "b2_d", "b3_d", "b4_d"]
    lab_o = ["Lula", "Bolsonaro", "Otros", "No voto/Blanco-Nulo"]
    lab_d = ["Lula", "Flavio", "Otros", "No voto/Blanco-Nulo"]
    filas = []
    for g, sub in m.groupby("q"):
        if len(sub) < 500:
            continue
        X = sub[cols_o].to_numpy(float)
        th = ie.em_transicion(X, sub[cols_d].to_numpy(float))
        N_o = X.sum(0)  # personas por bloque de origen en este quintil
        for j, oj in enumerate(lab_o):
            for kk, dk in enumerate(lab_d):
                filas.append({"factor": var, "quintil": int(g), "origen": oj,
                              "destino": dk, "p": th[j, kk],
                              "votos": th[j, kk] * N_o[j], "n": len(sub)})
    return pd.DataFrame(filas)


def graficar_panel(muni, corr, reg_sin, reg_con):
    fig, axes = plt.subplots(2, 2, figsize=(8 * 1.0, 6 * 1.0))  # placeholder, fixed below
    fig.set_size_inches(11, 8.25)  # 4:3
    ax = axes[0, 0]
    for v, color in (("ingreso", "#2C5FBF"), ("univ", "#E11B22")):
        d = muni.dropna(subset=[v, "swing_lula"]).copy()
        d["q"] = pd.qcut(d[v], 5, labels=False, duplicates="drop")
        agg = d.groupby("q")["swing_lula"].agg(["mean", "std", "size"])
        ax.errorbar(agg.index + 1, agg["mean"], yerr=1.96 * agg["std"] / np.sqrt(agg["size"]),
                    fmt="o-", color=color, capsize=3, label=NOMBRES[v])
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("Quintil (1=bajo, 5=alto)")
    ax.set_ylabel("Cambio de Lula 2022→2026 (puntos)")
    ax.set_title("A) Brasil: swing de Lula por quintil")
    ax.grid(alpha=0.35, ls="--")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    d = muni.dropna(subset=["religion", "swing_lula"]).copy()
    d["q"] = pd.qcut(d["religion"], 5, labels=False, duplicates="drop")
    agg = d.groupby("q")["swing_lula"].agg(["mean", "std", "size"])
    ax.bar(agg.index + 1, agg["mean"], color="#2E7D32", alpha=0.85)
    ax.errorbar(agg.index + 1, agg["mean"], yerr=1.96 * agg["std"] / np.sqrt(agg["size"]),
                fmt="none", ecolor="k", capsize=3)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("Quintil de % evangélicos")
    ax.set_ylabel("Cambio de Lula (puntos)")
    ax.set_title("B) Brasil: swing de Lula por % evangélicos")
    ax.grid(alpha=0.35, axis="y", ls="--")

    ax = axes[1, 0]
    x = np.arange(len(corr))
    ax.barh(x - 0.2, corr["corr"], height=0.4, color="#9AA0A6", label="simple")
    ax.barh(x + 0.2, corr["corr_intra_estado"], height=0.4, color="#2C5FBF",
            label="intra-estado")
    ax.set_yticks(x)
    ax.set_yticklabels([NOMBRES.get(f, "log votos") for f in corr["factor"]], fontsize=8)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel("Correlación con swing de Lula")
    ax.set_title("C) Brasil: correlación de factores con el swing")
    ax.grid(alpha=0.35, axis="x", ls="--")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    if reg_con is not None:
        r = reg_con.sort_values("coef")
        ax.barh(r["factor"], r["coef"], xerr=1.96 * r["se"], color="#B8860B")
        ax.set_yticklabels([NOMBRES.get(f, "log votos") for f in r["factor"]], fontsize=8)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel("Coef. (puntos por 1 SD), con efectos de estado")
    ax.set_title("D) Brasil: regresión del swing de Lula")
    ax.grid(alpha=0.35, axis="x", ls="--")

    fig.tight_layout()
    ep.mpl(fig, "Swing de Lula por quintiles de factores socioeconómicos (Censo 2022) y "
                "regresión con efectos fijos de estado.")
    fig.savefig(os.path.join(OUT, "socio_panel.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


def graficar_grupo(quints, claves, archivo, titulo, meto, absoluto=False):
    q = quints
    fig, axes = plt.subplots(1, 3, figsize=(12, 9))
    ymin, ymax = np.inf, -np.inf
    for ax, var in zip(axes, ["ingreso", "univ", "religion"]):
        sub = q[q["factor"] == var]
        for oj, dk in claves:
            s = sub[(sub["origen"] == oj) & (sub["destino"] == dk)].sort_values("quintil")
            if s.empty:
                continue
            y = s["votos"] / 1e6 if absoluto else s["p"] * 100
            ax.plot(s["quintil"] + 1, y, "o-", label=f"{oj}→{dk}")
            ymin = min(ymin, float(y.min()))
            ymax = max(ymax, float(y.max()))
        ax.set_title(f"Quintil de {NOMBRES[var]}", fontsize=9)
        ax.set_xlabel("Quintil")
        ax.set_ylabel("Millones de votos/personas" if absoluto else "% del bloque de origen")
        ax.grid(alpha=0.35, ls="--")
    margen = 0.06 * (ymax - ymin) if ymax > ymin else 1.0
    for ax in axes:                       # mismo eje y en las tres facetas
        ax.set_ylim(max(0.0, ymin - margen), ymax + margen)
    suf = " — millones de votos/personas" if absoluto else ""
    fig.suptitle(f"Brasil: {titulo} (2022→2026){suf}", fontsize=12)
    axes[0].legend(fontsize=7)
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    ep.mpl(fig, meto)
    fig.savefig(os.path.join(OUT, archivo), dpi=140, bbox_inches="tight")
    plt.close(fig)


# Transiciones hacia/desde Lula
CLAVES_LULA = [("Lula", "Lula"), ("Lula", "Flavio"), ("Lula", "Otros"),
               ("Lula", "No voto/Blanco-Nulo"),
               ("Otros", "Lula"), ("No voto/Blanco-Nulo", "Lula")]
# Transiciones desde Bolsonaro y hacia Flávio
CLAVES_BOLSO = [("Bolsonaro", "Flavio"), ("Bolsonaro", "Otros"),
                ("Bolsonaro", "No voto/Blanco-Nulo"),
                ("Lula", "Flavio"), ("Otros", "Flavio"),
                ("No voto/Blanco-Nulo", "Flavio")]


def reporte(muni, corr, reg_con, r2_con, n_con, quints, idioma):
    es = idioma == "es"
    def num(x): return f"{x:+.1f}"
    lineas = []
    if es:
        lineas.append("# ¿La economía y la sociedad cambian la migración de votos? (Brasil 2022→2026)\n")
        lineas.append(f"Factores socioeconómicos municipales (Censo 2022) cruzados con "
                      f"{n_con} municipios. Swing de Lula = % Lula 2026 − % Lula 2022 (1ª vuelta).\n")
        lineas.append("## Correlación con el swing de Lula\n")
    else:
        lineas.append("# A economia e a sociedade mudam a migração de votos? (Brasil 2022→2026)\n")
        lineas.append(f"Fatores socioeconômicos municipais (Censo 2022) cruzados com "
                      f"{n_con} municípios. Swing de Lula = % Lula 2026 − % Lula 2022 (1º turno).\n")
        lineas.append("## Correlação com o swing de Lula\n")
    lineas.append("| Factor | Correlación | Intra-estado |")
    lineas.append("|---|---|---|")
    for _, r in corr.iterrows():
        lineas.append(f"| {NOMBRES.get(r['factor'], 'log votos')} | {r['corr']:+.2f} | "
                      f"{r['corr_intra_estado']:+.2f} |")
    lineas.append("")
    if es:
        lineas.append(f"## Regresión (coef. en puntos por 1 desvío estándar; R²={r2_con:.2f})\n")
    else:
        lineas.append(f"## Regressão (coef. em pontos por 1 desvio padrão; R²={r2_con:.2f})\n")
    lineas.append("| Factor | Coef. | t |")
    lineas.append("|---|---|---|")
    for _, r in reg_con.sort_values("coef", ascending=False).iterrows():
        lineas.append(f"| {NOMBRES.get(r['factor'], 'log votos')} | {r['coef']:+.2f} | {r['t']:+.1f} |")
    lineas.append("")
    if es:
        lineas.append("## ¿Modifica la inferencia ecológica? Transiciones clave por quintil\n")
    else:
        lineas.append("## A inferência ecológica muda? Transições-chave por quintil\n")
    lineas.append("| Factor | Quintil | Bolsonaro→Lula | Bolsonaro→Flávio | Otros→Flávio |")
    lineas.append("|---|---|---|---|---|")
    for var in ["ingreso", "univ", "religion"]:
        sub = quints[quints["factor"] == var]
        for q in sorted(sub["quintil"].unique()):
            def g(oj, dk):
                s = sub[(sub["quintil"] == q) & (sub["origen"] == oj) & (sub["destino"] == dk)]
                return f"{s['p'].iloc[0]*100:.1f}%" if not s.empty else "—"
            lineas.append(f"| {NOMBRES[var]} | {int(q)+1} | {g('Bolsonaro','Lula')} | "
                          f"{g('Bolsonaro','Flavio')} | {g('Otros','Flavio')} |")
    lineas.append("")
    if es:
        lineas.append("## Lectura\n"
                      "Si los coeficientes y las transiciones cambian marcadamente entre quintiles, "
                      "los factores socioeconómicos **sí** modifican la inferencia: la matriz nacional "
                      "promedia realidades muy distintas. La parte que sobrevive a los efectos de "
                      "estado es la relación más limpia (no confundida por la geografía).\n\n"
                      "*Fuente socio: dschteingart/el-atlas-charts (Censo 2022). Inferencia ecológica "
                      "por secciones (EM).*")
    else:
        lineas.append("## Leitura\n"
                      "Se os coeficientes e as transições mudam fortemente entre quintis, os fatores "
                      "socioeconômicos **sim** modificam a inferência: a matriz nacional mistura "
                      "realidades muito distintas. A parte que sobrevive aos efeitos de estado é a "
                      "relação mais limpa (não confundida pela geografia).\n\n"
                      "*Fonte socio: dschteingart/el-atlas-charts (Censo 2022). Inferência ecológica "
                      "por seções (EM).*")
    return "\n".join(lineas) + f"\n\n---\n\n*{ep.CREDITO}*\n"


def graficar_todo(muni, corr, reg_con, r2_con, n_con, quints):
    """Genera todos los gráficos e informes a partir de los datos intermedios."""
    graficar_panel(muni, corr, None, reg_con)
    METO_LULA = ("Transiciones de voto hacia/desde Lula (2022→2026) por quintil de factores "
                 "socioeconómicos; inferencia ecológica por secciones electorales (EM).")
    METO_BOLSO = ("Transiciones de voto desde Bolsonaro 2022 y hacia Flávio 2026 por quintil de "
                  "factores socioeconómicos; inferencia ecológica por secciones electorales (EM).")
    graficar_grupo(quints, CLAVES_LULA, "socio_ei_lula.png",
                   "transiciones hacia/desde Lula", METO_LULA)
    graficar_grupo(quints, CLAVES_LULA, "socio_ei_abs_lula.png",
                   "transiciones hacia/desde Lula", METO_LULA, absoluto=True)
    graficar_grupo(quints, CLAVES_BOLSO, "socio_ei_bolso_flavio.png",
                   "transiciones desde Bolsonaro y hacia Flávio", METO_BOLSO)
    graficar_grupo(quints, CLAVES_BOLSO, "socio_ei_abs_bolso_flavio.png",
                   "transiciones desde Bolsonaro y hacia Flávio", METO_BOLSO, absoluto=True)
    open(os.path.join(OUT, "informe_socio_es.md"), "w", encoding="utf-8").write(
        reporte(muni, corr, reg_con, r2_con, n_con, quints, "es"))
    open(os.path.join(OUT, "relatorio_socio_pt.md"), "w", encoding="utf-8").write(
        reporte(muni, corr, reg_con, r2_con, n_con, quints, "pt"))


def solo_graficos():
    """Regenera gráficos e informes desde los datos intermedios guardados (sin EM)."""
    muni = pd.read_csv(os.path.join(OUT, "socio_municipios.csv"))
    quints = pd.read_csv(os.path.join(OUT, "socio_ei_quintiles.csv"))
    reg = pd.read_csv(os.path.join(OUT, "socio_regresion.csv"))
    r2_con = float(reg["r2"].iloc[0]) if "r2" in reg.columns else float("nan")
    n_con = int(reg["n"].iloc[0]) if "n" in reg.columns else len(muni)
    reg_con = reg[["factor", "coef", "se", "t"]].copy()
    corr = correlaciones(muni, "swing_lula")
    graficar_todo(muni, corr, reg_con, r2_con, n_con, quints)
    print("[OK] Gráficos regenerados desde datos guardados")


def main():
    if "--solo-graficos" in sys.argv:
        solo_graficos()
        return
    print("[*] Datos socioeconómicos + votos por municipio...")
    muni = dataset_municipal()
    cobertura = muni["ingreso"].notna().mean() * 100
    print(f"    municipios: {len(muni)} | con socio: {cobertura:.1f}%")
    muni.to_csv(os.path.join(OUT, "socio_municipios.csv"), index=False)

    corr = correlaciones(muni, "swing_lula")
    reg_sin = ols_fe(muni, "swing_lula", VARS + ["log_votos"], fe="uf")
    # (sin FE de estado sería una variante; usamos con FE como principal)
    reg_con, r2_con, n_con = ols_fe(muni, "swing_lula", VARS + ["log_votos"], fe="uf")
    print("[i] Correlaciones con swing de Lula:")
    print(corr.round(2).to_string(index=False))
    print(f"[i] Regresión (con efectos de estado), R2={r2_con:.2f}, n={n_con}")
    print(reg_con.round(2).to_string(index=False))
    reg_con.assign(r2=r2_con, n=n_con).to_csv(os.path.join(OUT, "socio_regresion.csv"), index=False)

    # Secciones emparejadas 2022->2026 con socio por municipio
    print("[*] EI estratificada por factores socioeconómicos...")
    m_sec = ie.emparejar(ie.cargar_anio(2022, "1"), ie.cargar_anio(2026, "1"))
    mapa = cargar_tse_ibge()
    m_sec["ibge"] = m_sec["mun"].map(lambda x: mapa.get(int(x)))
    socio, _ = cargar_socio()
    m_sec = m_sec.merge(socio, on="ibge", how="left")

    partes = [ei_por_quintiles(m_sec, v) for v in ["ingreso", "univ", "religion"]]
    quints = pd.concat(partes, ignore_index=True)
    quints.to_csv(os.path.join(OUT, "socio_ei_quintiles.csv"), index=False)

    graficar_todo(muni, corr, reg_con, r2_con, n_con, quints)
    print(f"[OK] Salidas en {OUT}")


if __name__ == "__main__":
    main()

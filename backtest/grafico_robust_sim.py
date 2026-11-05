# -*- coding: utf-8 -*-
"""
backtest/grafico_robust_sim.py — Backtest local 2023 (prefecto): evolución de la cuota
correísta por prefectura según el % escrutado, comparando:
  * crudo (solo lo contado), v1, jerárquico, robust_sim (λ=0.65).
Orden de carga = timestamps 2021 (por zona). Genera dos imágenes 3×3:
  1) las 9 prefecturas más grandes (con candidato correísta en 2023);
  2) las siguientes 9 más grandes con candidato correísta.
Cada panel lleva el ganador de la prefectura; eje y acotado a 60%.

Salida:
  D:\\ecuador2026_data\\backtest\\grafico_robust_sim.png
  D:\\ecuador2026_data\\backtest\\grafico_robust_sim_siguientes9.png
Uso: python -m backtest.grafico_robust_sim
"""
import os
import sys
import time
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import rutas_datos as rd
from proyeccion import Proyector
from modelo import v1_brasil
from backtest.variantes_swing import unidades, orden_zonas, jer_de
from backtest.mejoras_v1 import hibrido_var

FRS = [0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50,
       0.60, 0.70, 0.80, 0.90, 0.95, 1.0]

PROV = {"01": "Azuay", "02": "Bolívar", "03": "Cañar", "04": "Carchi", "05": "Cotopaxi",
        "06": "Chimborazo", "07": "El Oro", "08": "Esmeraldas", "09": "Guayas",
        "10": "Imbabura", "11": "Loja", "12": "Los Ríos", "13": "Manabí",
        "14": "Morona S.", "15": "Napo", "16": "Pastaza", "17": "Pichincha",
        "18": "Tungurahua", "19": "Zamora Ch.", "20": "Galápagos", "21": "Sucumbíos",
        "22": "Orellana", "23": "Santo Domingo", "24": "Santa Elena"}

COL = {"crudo": "#7f7f7f", "v1": "#1f77b4", "hier": "#2ca02c", "robust_sim": "#d62728"}
LAB = {"crudo": "crudo", "v1": "v1", "hier": "jerárquico",
       "robust_sim": "robust_sim (λ=0,50)"}


def pshare(M, keys, ci):
    prov = np.array([k[:2] for k in keys]); cols = list(range(M.shape[1]))
    P = pd.DataFrame(M); P["p"] = prov; G = P.groupby("p")[cols].sum()
    return 100 * G[ci] / G.sum(1)


def ganadores():
    """{prov: (candidato, familia)} ganador de prefecto 2023 + provincias con candidato RC."""
    p = rd.ruta("gaona_format/gaona_2023_seccional_d11_prefecto_junta.csv")
    d = pd.read_csv(p, dtype=str, usecols=["cod_prov", "cod_candidato", "votos"])
    d["votos"] = pd.to_numeric(d["votos"], errors="coerce").fillna(0)
    d["cod_prov"] = d["cod_prov"].str.zfill(2)
    g = d.groupby(["cod_prov", "cod_candidato"])["votos"].sum().reset_index()
    from datos import candidatos
    r = candidatos.roster("prefecto", 2023)[["cod_candidato", "candidato", "familia"]]
    m = g.merge(r, on="cod_candidato", how="left")
    win = m.loc[m.groupby("cod_prov")["votos"].idxmax()]
    gan = {row.cod_prov: (str(row.candidato).title(), row.familia) for row in win.itertuples()}
    has_corre = set(m.loc[m.familia == "RC", "cod_prov"].unique())
    tot_prov = g.groupby("cod_prov")["votos"].sum()
    return gan, has_corre, tot_prov


def plot(provs, series, prov_votes, fprov, gan, out_name, titulo):
    fig, axes = plt.subplots(3, 3, figsize=(15, 12), sharex=True, sharey=True)
    for ax, p in zip(axes.ravel(), provs):
        for nm in ("crudo", "v1", "hier", "robust_sim"):
            ax.plot(series[nm][p]["x"], series[nm][p]["y"], color=COL[nm],
                    lw=1.6, label=LAB[nm])
        ax.axhline(float(fprov.get(p, np.nan)), color="black", ls="--", lw=1, label="final")
        ax.set_title(f"{PROV.get(p, p)} ({p}) · {int(round(prov_votes.get(p, 0)/1000))}k votos")
        ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.grid(alpha=0.25)
        nombre, fam = gan.get(p, ("?", "?"))
        ax.text(0.98, 0.97, f"Gana: {nombre} ({fam})", transform=ax.transAxes,
                ha="right", va="top", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.7", alpha=0.85))
    for ax in axes[-1]:
        ax.set_xlabel("% escrutado (votos, orden 2021)")
    for ax in axes[:, 0]:
        ax.set_ylabel("cuota correísmo (%)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, fontsize=10)
    fig.suptitle(titulo, fontsize=13)
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    out = os.path.join(rd.ruta_dir("backtest"), out_name)
    tmp = out + ".tmp.png"
    fig.savefig(tmp, dpi=130, bbox_inches="tight"); plt.close(fig)
    for _ in range(8):
        try:
            os.replace(tmp, out)
            break
        except OSError:
            time.sleep(0.4)
    else:
        raise OSError("no se pudo reemplazar " + out)
    print("[OK]", out, "|", provs)


def main():
    B = unidades(2019, "prefecto", "zona", "4bloques")
    T = unidades(2023, "prefecto", "zona", "4bloques")
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= 100) & (T.sum(1) >= 100)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    ci = cols.index("correismo")
    basev, finv = B.values, T.values; base_val = basev.sum(1)
    K = len(cols)

    # orden por timestamps 2021 (zona)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    zone_votes = finv.sum(1)
    cum = np.cumsum(zone_votes[orden]) / zone_votes.sum()

    modelo = Proyector(keys, jer_de(keys, ["nac", "prov", "cant", "parr"]), basev, base_val)
    grupos = [np.array([k[:11] for k in keys]), np.array([k[:6] for k in keys]),
              np.array([k[:2] for k in keys]), np.full(len(keys), "EC")]
    fprov = pshare(finv, keys, ci)
    # membresía por la muestra del backtest (misma que la imagen ya vista);
    # orden y "k votos" por el total oficial 2023
    prov_sample = pd.Series(finv.sum(1), index=keys).groupby([k[:2] for k in keys]).sum()
    gan, has_corre, tot_prov = ganadores()
    excluir = {"06", "18"}
    elegibles = [p for p in prov_sample.sort_values(ascending=False).index
                 if p in has_corre and p not in excluir]
    top9 = sorted(elegibles[:9], key=lambda p: -tot_prov.get(p, 0))
    sig9 = sorted(elegibles[9:18], key=lambda p: -tot_prov.get(p, 0))
    todos = top9 + sig9

    series = {m: {p: {"x": [], "y": []} for p in todos}
              for m in ("crudo", "v1", "hier", "robust_sim")}
    for f in FRS:
        n = int(np.searchsorted(cum, f, side="left")) + 1
        n = min(max(3, n), len(keys))
        cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        ff = np.zeros(len(keys)); ff[cnt] = 1.0
        r = modelo.proyectar(obs.copy(), ff, np.arange(K))
        hier = r["final"] if r else obs
        v1 = v1_brasil.proyectar(obs, base_val, grupos)
        rs = hibrido_var(obs, basev, base_val, keys, clip=True, robust="median",
                         peer="sim", lam=0.50, ks=(2, 4, 8, 16))
        met = {"crudo": obs, "v1": v1, "hier": hier, "robust_sim": rs}
        xv = 100 * float(zone_votes[orden[:n]].sum() / zone_votes.sum())
        for nm, M in met.items():
            sh = pshare(M, keys, ci)
            for p in todos:
                v = sh.get(p, np.nan)
                if pd.notna(v):
                    series[nm][p]["x"].append(xv); series[nm][p]["y"].append(float(v))

    plot(top9, series, tot_prov, fprov, gan, "grafico_robust_sim.png",
         "Backtest prefecto 2023 · 9 prefecturas más grandes")
    plot(sig9, series, tot_prov, fprov, gan, "grafico_robust_sim_siguientes9.png",
         "Backtest prefecto 2023 · siguientes 9 prefecturas con candidato correísta")


if __name__ == "__main__":
    main()

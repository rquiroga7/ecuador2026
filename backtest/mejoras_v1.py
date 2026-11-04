# -*- coding: utf-8 -*-
"""
backtest/mejoras_v1.py — Paso 1: alternativas a la cascada dura de v1 (local 2019→2023).

Métodos (unidad zona, 2019→2023, orden 2021):
  * `v1`      — cascada dura (baseline).
  * `A_soft`  — cascada SUAVIZADA: mezcla de niveles con peso n/(n+k) (empirical Bayes).
  * `B_hyb`   — híbrido: base+swing (v4-like, encogido) mezclado con A_soft (λ).
  * `H_turn`  — tamaño/participación: válidos esperados = base_val × factor de turnout (encogido).
  * `C_sim`   — promedio de pares ponderado por similitud de share base (kernel).
  * `G_ens`   — ensamble v1 + jerárquico + v2.

Foco: 10% y 20% (curva 5–50%). 3 esquemas de bloque. Salida:
D:\\ecuador2026_data\\backtest\\mejoras_v1.csv
Uso: python -m backtest.mejoras_v1
"""
import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rutas_datos as rd
from proyeccion import Proyector, _grupos
from modelo import swing, v1_brasil
from backtest.variantes_swing import unidades, orden_zonas, metricas, jer_de, FRACS


def _norm(M):
    s = M.sum(1, keepdims=True); s = np.where(s <= 0, 1, s)
    return M / s


def _shares_g(base, counted, gi, ng, K):
    S = np.zeros((ng, K))
    for b in range(K):
        S[:, b] = np.bincount(gi, weights=np.where(counted, base[:, b], 0), minlength=ng)
    T = S.sum(1)
    sh = np.divide(S, T[:, None], out=np.zeros_like(S), where=T[:, None] > 0)
    return sh, T


def _niveles(keys):
    return [np.array([k[:11] for k in keys]), np.array([k[:6] for k in keys]),
            np.array([k[:2] for k in keys]), np.array(["EC"] * len(keys))]


def soft_cascade(obs, base_val, keys, ks=(2, 4, 8, 16)):
    U, K = obs.shape
    counted = obs.sum(1) > 0
    blend = np.zeros((U, K)); wsum = np.zeros(U)
    for labels, kk in zip(_niveles(keys), ks):
        gi, ng = _grupos(labels)
        sh, T = _shares_g(obs, counted, gi, ng, K)
        w = T[gi] / (T[gi] + kk)
        blend += w[:, None] * sh[gi]
        wsum += w
    wsum[wsum == 0] = 1
    sh_i = _norm(blend / wsum[:, None])
    proj = obs.copy()
    unc = ~counted
    proj[unc] = base_val[unc, None] * sh_i[unc]
    return proj


def hibrido(obs, base, base_val, keys, lam=0.5, ks=(2, 4, 8, 16)):
    U, K = obs.shape
    counted = obs.sum(1) > 0
    S = soft_cascade(obs, base_val, keys, ks)
    sh_base = _norm(base.copy())  # base shares
    # swing observado por nivel (encogido)
    delta = np.zeros((U, K)); wsum = np.zeros(U)
    for labels, kk in zip(_niveles(keys), ks):
        gi, ng = _grupos(labels)
        so, To = _shares_g(obs, counted, gi, ng, K)
        sb, Tb = _shares_g(base, counted, gi, ng, K)
        d = (so - sb) * (To / (To + kk))[:, None]
        w = To[gi] / (To[gi] + kk)
        delta += w[:, None] * d[gi]
        wsum += w
    wsum[wsum == 0] = 1
    delta /= wsum[:, None]
    sh_sw = _norm(sh_base + delta)
    unc = ~counted
    # mezcla de shares
    sh = lam * sh_sw + (1 - lam) * _norm(S / np.maximum(S.sum(1, keepdims=True), 1))
    sh = _norm(sh)
    out = obs.copy()
    out[unc] = base_val[unc, None] * sh[unc]
    return out


def turnout(obs, base, base_val, keys, ks=(2, 4, 8, 16)):
    U, K = obs.shape
    counted = obs.sum(1) > 0
    S = soft_cascade(obs, base_val, keys, ks)
    sh = _norm(S / np.maximum(S.sum(1, keepdims=True), 1))
    # factor de turnout por nivel (obs total / base_val de los contados)
    r = np.zeros(U); wsum = np.zeros(U)
    for labels, kk in zip(_niveles(keys), ks):
        gi, ng = _grupos(labels)
        to = np.bincount(gi, weights=np.where(counted, obs.sum(1), 0), minlength=ng)
        tb = np.bincount(gi, weights=np.where(counted, base_val, 0), minlength=ng)
        rg = np.where(tb > 0, to / np.maximum(tb, 1), 1.0)
        w = tb[gi] / (tb[gi] + kk)
        r += w * rg[gi]; wsum += w
    wsum[wsum == 0] = 1
    r = np.where(wsum > 0, r / wsum, 1.0)
    out = obs.copy()
    unc = ~counted
    out[unc] = (base_val[unc] * r[unc])[:, None] * sh[unc]
    return out


def turnout_factor(obs, base_val, keys, ks=(2, 4, 8, 16)):
    """Factor de turnout r (obs total / válidos base en pares contados), encogido por nivel."""
    U = obs.shape[0]
    counted = obs.sum(1) > 0
    r = np.zeros(U); wsum = np.zeros(U)
    for labels, kk in zip(_niveles(keys), ks):
        gi, ng = _grupos(labels)
        to = np.bincount(gi, weights=np.where(counted, obs.sum(1), 0), minlength=ng)
        tb = np.bincount(gi, weights=np.where(counted, base_val, 0), minlength=ng)
        rg = np.where(tb > 0, to / np.maximum(tb, 1), 1.0)
        w = tb[gi] / (tb[gi] + kk)
        r += w * rg[gi]; wsum += w
    wsum[wsum == 0] = 1
    return np.where(wsum > 0, r / wsum, 1.0)


def aplicar_turnout(proj, obs, r):
    """Escala solo las unidades NO escrutadas por el factor de turnout."""
    out = proj.copy()
    unc = obs.sum(1) == 0
    out[unc] = r[unc, None] * proj[unc]
    return out


def _niv_sel(keys, niveles):
    m = {"parr": np.array([k[:11] for k in keys]),
         "cant": np.array([k[:6] for k in keys]),
         "prov": np.array([k[:2] for k in keys]),
         "nac": np.array(["EC"] * len(keys))}
    return [m[n] for n in niveles]


def _soft_levels(obs, base_val, labels, kks, power=1.0):
    """Cascada suave; `power`>0 pondera pares por votos^power (sizew usa 0.5)."""
    U, K = obs.shape
    counted = obs.sum(1) > 0
    u = np.where(counted, obs.sum(1), 0.0)
    wt = np.power(np.maximum(u, 0), power)
    blend = np.zeros((U, K)); wsum = np.zeros(U)
    for labs, kk in zip(labels, kks):
        gi, ng = _grupos(labs)
        S = np.zeros((ng, K))
        for b in range(K):
            S[:, b] = np.bincount(gi, weights=np.where(counted, obs[:, b], 0) * np.where(counted, wt, 0), minlength=ng)
        W = np.bincount(gi, weights=np.where(counted, wt, 0), minlength=ng)
        Tv = np.bincount(gi, weights=np.where(counted, obs.sum(1), 0), minlength=ng)
        sh = np.divide(S, W[:, None], out=np.zeros_like(S), where=W[:, None] > 0)
        w = Tv[gi] / (Tv[gi] + kk)
        blend += w[:, None] * sh[gi]; wsum += w
    wsum[wsum == 0] = 1
    sh_i = _norm(blend / wsum[:, None])
    proj = obs.copy(); unc = ~counted
    proj[unc] = base_val[unc, None] * sh_i[unc]
    return proj


def _delta_median(obs, base, counted, gi, ng, K):
    d = _norm(obs) - _norm(base)
    T = np.bincount(gi, weights=np.where(counted, obs.sum(1), 0), minlength=ng)
    out = np.zeros((ng, K))
    idx = np.where(counted)[0]
    if len(idx):
        med = pd.DataFrame(d).iloc[idx].groupby(gi[idx]).median()
        out[med.index.values] = med.values
    return out, T


def hibrido_var(obs, base, base_val, keys, clip=True, shrink_nat=False,
                robust="mean", ks=(2, 4, 8, 16), lam=0.5, peer="soft",
                logit=False, niveles=("parr", "cant", "prov", "nac")):
    """est_B parametrizado (ver docs/backtest.md, grilla est_B)."""
    U, K = obs.shape
    counted = obs.sum(1) > 0
    labels = _niv_sel(keys, niveles)
    kks = list(ks)[:len(labels)]
    # --- componente de pares ---
    if peer == "sim":
        P = similitud(obs, base, base_val, keys)
    else:
        P = _soft_levels(obs, base_val, labels, kks, power=0.5 if peer == "sizew" else 1.0)
    sh_peer = _norm(P / np.maximum(P.sum(1, keepdims=True), 1))
    # --- base + swing ---
    sh_base = _norm(base.copy())
    so_nat = _norm(obs[counted].sum(0)[None, :])[0]; sb_nat = _norm(base[counted].sum(0)[None, :])[0]
    sw_nat = so_nat - sb_nat
    delta = np.zeros((U, K)); wsum = np.zeros(U)
    for labs, kk in zip(labels, kks):
        gi, ng = _grupos(labs)
        if robust == "median":
            d_g, T = _delta_median(obs, base, counted, gi, ng, K)
        else:
            so, T = _shares_g(obs, counted, gi, ng, K)
            sb, _ = _shares_g(base, counted, gi, ng, K)
            d_g = so - sb
        if shrink_nat:
            d_g = sw_nat[None, :] + (d_g - sw_nat[None, :]) * (T / (T + kk))[:, None]
        else:
            d_g = d_g * (T / (T + kk))[:, None]
        w = T[gi] / (T[gi] + kk)
        delta += w[:, None] * d_g[gi]; wsum += w
    wsum[wsum == 0] = 1
    delta /= wsum[:, None]
    sh_sw = sh_base + delta
    if clip:
        sh_sw = np.clip(sh_sw, 0, None)
    sh_sw = _norm(sh_sw)
    # --- mezcla ---
    if lam == "data":
        f = float(counted.sum()) / U
        lamv = float(np.clip(0.75 - 1.0 * f, 0.25, 0.75))
    else:
        lamv = float(lam)
    eps = 1e-6
    if logit:
        sh = np.exp(lamv * np.log(np.clip(sh_sw, eps, None))
                    + (1 - lamv) * np.log(np.clip(sh_peer, eps, None)))
    else:
        sh = lamv * sh_sw + (1 - lamv) * sh_peer
    if clip:
        sh = np.clip(sh, 0, None)
    sh = _norm(sh)
    out = obs.copy(); unc = ~counted
    out[unc] = base_val[unc, None] * sh[unc]
    return out


def similitud(obs, base, base_val, keys, m=8):
    U, K = obs.shape
    counted = obs.sum(1) > 0
    base_sh = _norm(base.copy())
    out = obs.copy()
    # grupos finos: parroquia -> canton -> provincia -> nacional
    niveles = _niveles(keys)
    for i in np.where(~counted)[0]:
        sh = None
        for labels in niveles:
            peers = np.where(counted & (labels == labels[i]))[0]
            if len(peers) < 3:
                continue
            d = ((base_sh[peers] - base_sh[i]) ** 2).sum(1)
            h = np.median(d) + 1e-6
            w = np.exp(-d / h)
            if w.sum() <= 0:
                continue
            sh = (w[:, None] * _norm(obs[peers])).sum(0) / w.sum()
            break
        if sh is None:
            continue
        out[i] = base_val[i] * sh
    return out


def corrida(esquema, dig, nivel="zona", min_votos=100):
    B = unidades(2019, dig, nivel, esquema)
    T = unidades(2023, dig, nivel, esquema)
    cols = sorted(set(B.columns) | set(T.columns))
    com = sorted(set(B.index) & set(T.index))
    B = B.reindex(index=com, columns=cols, fill_value=0)
    T = T.reindex(index=com, columns=cols, fill_value=0)
    keep = (B.sum(1) >= min_votos) & (T.sum(1) >= min_votos)
    B, T = B[keep], T[keep]
    keys = list(B.index)
    if not keys:
        return []
    K = len(cols)
    basev = B.values; finv = T.values; base_val = basev.sum(1)
    g, prov = orden_zonas()
    tz = np.array([g.get(k, np.nan) for k in keys], float)
    pv = np.array([prov.get(k[:2], np.nan) for k in keys], float)
    tz = np.where(np.isnan(tz), pv, tz); tz = np.where(np.isnan(tz), np.nanmedian(tz), tz)
    orden = np.argsort(tz, kind="stable")
    jer = jer_de(keys, ["nac", "prov", "cant", "parr"])
    modelo = Proyector(keys, jer, basev, base_val)

    filas = []
    for fr in FRACS:
        n = max(3, int(round(fr * len(keys))))
        cnt = orden[:n]
        obs = np.zeros_like(finv); obs[cnt] = finv[cnt]
        f = np.zeros(len(keys)); f[cnt] = 1.0
        met = {}
        met["v1"] = v1_brasil.proyectar(obs, base_val, [np.array([k[:11] for k in keys]),
                                    np.array([k[:6] for k in keys]), np.array([k[:2] for k in keys]),
                                    np.full(len(keys), "EC")])
        met["A_soft"] = soft_cascade(obs, base_val, keys)
        met["B_hyb"] = hibrido(obs, basev, base_val, keys, lam=0.5)
        met["B_hyb25"] = hibrido(obs, basev, base_val, keys, lam=0.25)
        met["H_turn"] = turnout(obs, basev, base_val, keys)
        met["C_sim"] = similitud(obs, basev, base_val, keys)
        # G: ensamble v1 + jerarquico + v2
        r = modelo.proyectar(obs.copy(), f, np.arange(K))
        hier = r["final"] if r else met["v1"]
        v2, _ = swing.proyectar(basev, obs, np.array(["EC"] * len(keys)), modo="nacional")
        met["G_ens"] = 0.6 * met["v1"] + 0.2 * hier + 0.2 * v2
        for nombre, proj in met.items():
            err, acc, top2 = metricas(proj, finv, keys, dig)
            filas.append({"esquema": esquema, "dignidad": dig, "nivel": nivel,
                          "metodo": nombre, "frac": round(fr, 2), "err": round(err, 2),
                          "acc": round(acc, 3), "top2": round(top2, 3)})
    return filas


def main():
    out = rd.ruta_dir("backtest")
    filas = []
    for esquema in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            filas += corrida(esquema, dig, "zona", 100)
    df = pd.DataFrame(filas)
    p = os.path.join(out, "mejoras_v1.csv")
    df.to_csv(p, index=False)
    print("[OK]", p, len(df), "filas")
    for esquema in ("familias", "2bloques", "3bloques"):
        for dig in ("prefecto", "alcalde"):
            sub = df[(df.esquema == esquema) & (df.dignidad == dig) & (df.frac.isin([0.10, 0.20]))]
            if sub.empty:
                continue
            piv = sub.pivot_table(index="metodo", columns="frac", values="err", aggfunc="first")
            piv.columns = [f"err@{int(c*100)}%" for c in piv.columns]
            piv["acc@10%"] = sub[sub.frac == 0.10].set_index("metodo")["acc"]
            piv["acc@20%"] = sub[sub.frac == 0.20].set_index("metodo")["acc"]
            print(f"\n== {esquema} · {dig} ==")
            print(piv.sort_values(piv.columns[0]).to_string())


if __name__ == "__main__":
    main()

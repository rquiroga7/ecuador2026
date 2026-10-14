# -*- coding: utf-8 -*-
"""
forense/mezclas.py — Modelo de mezclas finitas (estilo Mebane / Klimek) por unidad.

Con N (electores), V (sufragantes) y W (votos del partido líder) por unidad, se
ajusta una mezcla de 3 componentes gaussianos sobre
    x = [logit(turnout = V/N), logit(share_líder = W/V)]
por EM. Los componentes capturan: sin fraude (mayoría), e incrementales/extremos
(turnout y/o share anómalamente altos). El **score** = probabilidad posterior de
pertenecer a un componente fraudulento (turnout y share altos).

Se valida con una simulación: se inyecta fraude extremo (turnout ~99%, share ~90%) en
una fracción de unidades y se mide separación (AUC).

Nota: es una aproximación práctica al modelo positivo de Mebane (2016) implementado en
el paquete R `eforensics`; no reproduce exactamente su verosimilitud (esa requiere MCMC).

Uso:  python -m forense.mezclas 2025
"""

import os
import sys
import numpy as np
import pandas as pd

import rutas_datos as rd
import datos.registro as registro

EPS = 1e-4


def _logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def cargar_presidencial(anio, leader):
    """N,V,W por parroquia. W = votos del partido líder (OP) ."""
    v = pd.read_csv(rd.ruta(f"mesas/parr_votos_nacional_{anio}.csv.gz"), dtype=str)
    v = v[v["dignidad"].str.contains("PRESID", case=False, na=False)].copy()
    v["votos"] = v["votos"].astype(int)
    v["op"] = pd.to_numeric(v["op_codigo"], errors="coerce")
    v = v.dropna(subset=["op"])
    v["op"] = v["op"].astype(int).astype(str)
    v["loc_id"] = v["cod_provincia"].str.cat([v["cod_canton"], v["cod_parroquia"]],
                                             sep="-")
    W = v[v["op"] == leader].groupby("loc_id")["votos"].sum()
    V = v.groupby("loc_id")["votos"].sum()
    N = registro.electores_parroquia(anio)
    loc = V.index.intersection(N.index)
    df = pd.DataFrame({"V": V.reindex(loc), "N": N.reindex(loc)})
    df["W"] = W.reindex(loc).fillna(0)
    df = df[(df["N"] > 0) & (df["V"] > 0)]
    return df


def gmm_em(X, K=3, iters=300, seed=0):
    """EM para GMM de K componentes (covarianza completa). Devuelve pi, mu, Sigma, resp."""
    n, d = X.shape
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, K, replace=False)
    mu = X[idx].copy()
    Sigma = np.array([np.cov(X.T) + 1e-4 * np.eye(d) for _ in range(K)])
    pi = np.full(K, 1.0 / K)
    resp = np.zeros((n, K))
    for _ in range(iters):
        # E
        logp = np.zeros((n, K))
        for k in range(K):
            diff = X - mu[k]
            inv = np.linalg.inv(Sigma[k])
            maha = np.einsum("ij,jk,ik->i", diff, inv, diff)
            logp[:, k] = (np.log(pi[k] + 1e-300) - 0.5 * maha
                          - 0.5 * np.log(np.linalg.det(Sigma[k]) + 1e-300))
        logp -= logp.max(1, keepdims=True)
        resp = np.exp(logp)
        resp /= resp.sum(1, keepdims=True)
        # M
        Nk = resp.sum(0) + 1e-9
        pi = Nk / n
        for k in range(K):
            mu[k] = (resp[:, k] @ X) / Nk[k]
            diff = X - mu[k]
            Sigma[k] = (diff * resp[:, k:k+1]).T @ diff / Nk[k] + 1e-4 * np.eye(d)
    return pi, mu, Sigma, resp


def score_fraude(resp, mu, pi, max_peso=0.30):
    """Score = responsabilidad del componente de **esquina alta** (mayor turnout+share)
    que además sea minoritario (peso < max_peso). Si no hay, no hay señal de fraude."""
    esquina = mu[:, 0] + mu[:, 1]
    cand = np.where(pi < max_peso)[0]
    if len(cand) == 0:
        return np.zeros(len(resp))
    k = cand[np.argmax(esquina[cand])]
    return resp[:, k]


def correr(df, col_N="N", col_V="V", col_W="W", K=3):
    X = np.column_stack([_logit(df[col_V] / df[col_N]), _logit(df[col_W] / df[col_V])])
    pi, mu, Sigma, resp = gmm_em(X, K=K)
    df = df.copy()
    df["score"] = score_fraude(resp, mu, pi)
    return df, (pi, mu, Sigma, resp)


def _auc(s, y):
    r = pd.Series(s).rank().values
    n1 = y.sum(); n0 = (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else np.nan


def main():
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    leader = {"2025": "500", "2021": "1030"}[str(anio)]
    df = cargar_presidencial(anio, leader)
    print(f"[mezclas {anio}] unidades={len(df)} "
          f"turnout medio={100*df['V'].sum()/df['N'].sum():.1f}%")
    # A) sin anomalía
    _, (pi, mu, _, _) = correr(df)
    print("  componentes (turnout, share) con pesos:")
    for k in range(len(pi)):
        t = np.exp(mu[k, 0]) / (1 + np.exp(mu[k, 0]))
        s = np.exp(mu[k, 1]) / (1 + np.exp(mu[k, 1]))
        print(f"    k{k}: peso={pi[k]:.3f}  turnout={t:.3f}  share_lider={s:.3f}")

    # B) simulación: inyectar fraude extremo en 5%
    rng = np.random.default_rng(3)
    d2 = df.copy()
    frac = 0.05
    idx = rng.choice(len(d2), int(frac * len(d2)), replace=False)
    mask = np.zeros(len(d2), bool); mask[idx] = True
    d2.iloc[idx, d2.columns.get_loc("V")] = (0.99 * d2.iloc[idx]["N"]).round()
    d2.iloc[idx, d2.columns.get_loc("W")] = (0.90 * d2.iloc[idx]["V"]).round()
    sc, _ = correr(d2)
    auc = _auc(sc["score"].values, mask)
    print(f"  simulación fraude extremo (5%): AUC={auc:.3f}")

    out = rd.ruta_dir("forense")
    sc.sort_values("score", ascending=False).to_csv(
        os.path.join(out, f"mezclas_{anio}.csv.gz"), index=False, compression="gzip")
    print(f"[OK] -> {out}")


if __name__ == "__main__":
    main()

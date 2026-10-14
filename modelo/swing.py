# -*- coding: utf-8 -*-
"""
modelo/swing.py — Métodos de swing "simples" recuperados de Brasil (v2 y v4).

Adaptados a Ecuador (unidades = parroquias; territorio = provincia o cantón):

  * `v2` (uniforme NACIONAL): para cada unidad no escrutada,
        proj_share = normalize(share_2019 + swing_nacional)
    con swing_nacional = media de (share_obs − share_2019) sobre las unidades
    escrutadas, ponderada por votos observados.

  * `v4` (swing por TERRITORIO): ídem pero con el swing del territorio
        (provincia/cantón), encogido hacia el nacional según su % escrutado:
        sw = λ·sw_territorio + (1−λ)·sw_nacional,  λ = min(1, esc_terr / T).

En ambos, el denominador son **votos válidos**, y las unidades ya escrutadas se
respetan tal cual (se usa su share observado).

Uso:
    from modelo import swing
    proj = swing.proyectar(base19, obs23, terr_of, modo="territorio")
"""

import numpy as np


def _normalizar(M):
    M = np.clip(np.asarray(M, float), 0.0, None)
    s = M.sum(1, keepdims=True)
    s = np.where(s <= 0, 1.0, s)
    return M / s


def _shares(M):
    v = M.sum(1, keepdims=True)
    v = np.where(v <= 0, 1.0, v)
    return M / v


def proyectar(base, obs, terr_of, modo="nacional", T=0.30, min_n=5):
    """base [U,K]: votos de referencia (2019). obs [U,K]: votos observados 2023
    (0 donde aún no hay datos). terr_of [U]: etiqueta de territorio.

    Devuelve (proj [U,K] votos proyectados, info dict)."""
    base = np.asarray(base, float)
    obs = np.asarray(obs, float)
    U, K = base.shape
    terr_of = np.asarray(terr_of)

    val_base = base.sum(1)
    val_obs = obs.sum(1)
    counted = val_obs > 0
    sh_base = _shares(base)
    sh_obs = np.zeros_like(obs)
    sh_obs[counted] = _shares(obs[counted])

    w = val_obs.copy()                       # peso = votos observados
    delta = sh_obs - sh_base

    def _sw(mask):
        ww = w[mask]
        if ww.sum() <= 0:
            return np.zeros(K)
        return (ww[:, None] * delta[mask]).sum(0) / ww.sum()

    sw_nat = _sw(counted)

    # swing por territorio (con encogimiento)
    sw_terr = {}
    for g in np.unique(terr_of):
        m = counted & (terr_of == g)
        if m.sum() < min_n:
            continue
        mg = _sw(m)
        expected = val_base[terr_of == g].sum()
        esc = val_obs[m].sum() / max(expected, 1.0)
        lam = min(1.0, esc / T)
        sw_terr[g] = lam * mg + (1.0 - lam) * sw_nat

    proj = np.zeros_like(base)
    proj[counted] = obs[counted]
    unc = ~counted
    for i in np.where(unc)[0]:
        if modo == "territorio" and terr_of[i] in sw_terr:
            sw = sw_terr[terr_of[i]]
        else:
            sw = sw_nat
        sh = _normalizar((sh_base[i] + sw)[None, :])[0]
        proj[i] = val_base[i] * sh           # votos esperados ≈ válidos 2019
    return proj, {"sw_nat": sw_nat, "n_counted": int(counted.sum()), "modo": modo}

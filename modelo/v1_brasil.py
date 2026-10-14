# -*- coding: utf-8 -*-
"""
modelo/v1_brasil.py — Método v1 de Brasil (Etchenique): relleno jerárquico espacial.

NO usa una elección de referencia (por eso no depende de mapear alianzas entre años).
Para cada unidad:
  * si ya está escrutada → se usa su share observado;
  * si no → se usa el share promedio observado de sus pares en el **cantón**; si el
    cantón no tiene nada contado, el de la **provincia**; si no, el **nacional**.

Votos esperados de la unidad = válidos de referencia (proxy de tamaño/turnout) × share.

Uso:
    from modelo import v1_brasil
    proj = v1_brasil.proyectar(obs, val_base, [canton, provincia, np.full(U,"EC")])
"""

import numpy as np


def _suma_por_grupo(obs, counted, g):
    agg = {}
    for lab in np.unique(g):
        m = counted & (g == lab)
        if m.any():
            v = obs[m].sum(0)
            s = v.sum()
            if s > 0:
                agg[lab] = v / s
    return agg


def proyectar(obs, val_base, grupos):
    """obs [U,K] votos observados (0 donde no hay datos); val_base [U] válidos de
    referencia; grupos = lista de etiquetas de lo más fino a lo más grueso
    (p. ej. [cantón, provincia, nacional])."""
    obs = np.asarray(obs, float)
    val_base = np.asarray(val_base, float)
    U, K = obs.shape
    val_obs = obs.sum(1)
    counted = val_obs > 0

    proj = np.zeros_like(obs)
    proj[counted] = obs[counted]

    falls = [_suma_por_grupo(obs, counted, np.asarray(g)) for g in grupos]
    nat = obs[counted].sum(0)
    nat = nat / nat.sum() if nat.sum() > 0 else np.zeros(K)

    for i in np.where(~counted)[0]:
        sh = None
        for g, agg in zip(grupos, falls):
            if g[i] in agg:
                sh = agg[g[i]]
                break
        if sh is None:
            sh = nat
        proj[i] = val_base[i] * sh
    return proj

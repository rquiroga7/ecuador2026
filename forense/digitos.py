# -*- coding: utf-8 -*-
"""
forense/digitos.py — Tests de dígitos (Mebane) sobre conteos y porcentajes.

Sobre un conjunto de conteos (p. ej. votos por junta de un partido):
  * `media_segundo`  — media del 2.º dígito significativo (Benford-like ≈ 4.187)
  * `chi2_2bl`       — chi-cuadrado del 2.º dígito vs distribución 2BL (gl=9)
  * `media_ultimo`   — media del último dígito (uniforme ≈ 4.5)
  * `c05`            — fracción de últimos dígitos en {0,5} (≈ 0.2)
  * `p05`            — ídem sobre el último dígito de porcentajes redondeados (≈ 0.2)

Bootstrap no paramétrico para intervalos. Ver docs/FORENSE.md.
"""

import numpy as np

# frecuencias 2BL (Benford) del 2.º dígito
R_2BL = np.array([.120, .114, .109, .104, .100, .097, .093, .090, .088, .085])
J_BAR = float((np.arange(10) * R_2BL).sum())      # 4.187
LAST_BAR = 4.5
P05_BAR = 0.2


def _counts(v):
    v = np.asarray(v, float)
    return v[np.isfinite(v) & (v >= 10)]


def _segundos(v):
    v = np.floor(np.abs(v)).astype("int64")
    return (v // 10) % 10


def _ultimos(v):
    return np.floor(np.abs(np.asarray(v, float))).astype("int64") % 10


def media_segundo(v):
    v = _counts(v)
    if len(v) == 0:
        return np.nan
    return float(_segundos(v).mean())


def chi2_2bl(v):
    v = _counts(v)
    if len(v) == 0:
        return np.nan
    obs = np.bincount(_segundos(v), minlength=10)
    esp = R_2BL * len(v)
    return float((((obs - esp) ** 2) / esp).sum())


def media_ultimo(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v) & (v >= 1)]
    return float(_ultimos(v).mean()) if len(v) else np.nan


def c05(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v) & (v >= 1)]
    if len(v) == 0:
        return np.nan
    u = _ultimos(v)
    return float(np.isin(u, [0, 5]).mean())


def p05(pct):
    """último dígito de porcentajes redondeados a 1 decimal (x10 % 10 == 0/5)."""
    pct = np.asarray(pct, float)
    pct = pct[np.isfinite(pct)]
    if len(pct) == 0:
        return np.nan
    d = np.round(pct * 10).astype("int64") % 10
    return float(np.isin(d, [0, 5]).mean())


def _ic_boot(fn, v, n=1000, alpha=0.05, rng=None):
    rng = rng or np.random.default_rng(0)
    v = np.asarray(v, float)
    if len(v) < 5:
        return np.nan, np.nan
    est = np.array([fn(rng.choice(v, size=len(v), replace=True)) for _ in range(n)])
    est = est[np.isfinite(est)]
    return float(np.percentile(est, 100 * alpha / 2)), float(np.percentile(est, 100 * (1 - alpha / 2)))


def resumen(v, pct=None):
    """Diccionario con las estadísticas de dígitos y sus IC bootstrap."""
    out = {
        "n": int(len(_counts(v))),
        "media_segundo": media_segundo(v),
        "chi2_2bl": chi2_2bl(v),
        "media_ultimo": media_ultimo(v),
        "c05": c05(v),
    }
    if pct is not None:
        out["p05"] = p05(pct)
    lo, hi = _ic_boot(media_segundo, v, 500)
    out["media_segundo_ic"] = (lo, hi)
    return out

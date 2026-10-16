# -*- coding: utf-8 -*-
"""
estilo_plot.py — Pie de figura común para todos los gráficos.

Añade una nota metodológica breve en español + autor (+ repositorio, si se define
`REPO_URL`).
"""

# Poné aquí la URL del repositorio de Ecuador cuando lo crees, p. ej.
#   REPO_URL = "https://github.com/<usuario>/ecuador2026"
REPO_URL = ""
AUTORES = "Rodrigo Quiroga y Roberto Etchenique"
AUTOR = AUTORES
CREDITO = f"Autores: {AUTORES}"


def pie(metodologia):
    base = f"{metodologia}\n{CREDITO}"
    if REPO_URL:
        base += f" · ver {REPO_URL}"
    return base


def mpl(fig, metodologia):
    """Pie para figuras matplotlib (usar con bbox_inches='tight')."""
    fig.text(0.5, -0.03, pie(metodologia), ha="center", va="top",
             fontsize=7, color="#555555")


def plotly(fig, metodologia):
    """Pie para figuras plotly (Sankey)."""
    fig.add_annotation(text=pie(metodologia), xref="paper", yref="paper",
                       x=0.5, y=-0.13, showarrow=False, align="center",
                       font=dict(size=10, color="#555555"))

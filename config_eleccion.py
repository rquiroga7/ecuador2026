# -*- coding: utf-8 -*-
"""
config_eleccion.py — Parámetros de la elección (modular: 2026 real ↔ 2023 de prueba).

Todo el pipeline (captura → instantánea → proyección → dashboard) lee de acá, así
cambiar de elección es cambiar estos valores (o pasarlos por CLI). No hay nada
hardcodeado a 2026 en el resto del código.

Uso:
    import config_eleccion as cfg
    cfg.resumen()
"""

# --- Elección objetivo ---
ELECCION = "Seccionales Ecuador 2026"
ANIO_ELECCION = 2026
ANIO_REFERENCIA = 2023            # base del swing / relleno (misma dignidad)

# --- Dignidades y método ---
DIGNIDADES = ["prefecto", "alcalde"]
METODO = "v1"                     # v1 (relleno jerárquico) | jerarquico (Schteingart)

# --- Fuente de datos ---
FUENTE = "replay"                 # replay | azure | portal
FRACCION_REPLAY = 0.35            # % de mesas escrutadas en el replay
ORDEN_REPLAY = "aleatorio"        # aleatorio | directo | inverso

# --- Publicación ---
SALIDA_WEB = "web/datos_web.json"
PUBLICAR = False                  # True -> empuja a la rama de datos (PUBLISH_* / git)


def como_dict():
    return {
        "eleccion": ELECCION, "anio_eleccion": ANIO_ELECCION,
        "anio_referencia": ANIO_REFERENCIA, "dignidades": DIGNIDADES,
        "metodo": METODO, "fuente": FUENTE,
        "fraccion_replay": FRACCION_REPLAY, "orden_replay": ORDEN_REPLAY,
    }


def resumen():
    d = como_dict()
    return " | ".join(f"{k}={v}" for k, v in d.items())


if __name__ == "__main__":
    print(resumen())

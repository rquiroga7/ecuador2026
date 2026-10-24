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
# Unidad fina del modelo: "recinto" (zona; más fino y estable que la junta) |
# "parroquia". Recinto solo si el dump por mesa del año de referencia existe
# (2023 sí; 2019/2021/2025 no → se baja a parroquia automáticamente).
NIVEL = "recinto"

# --- Fuente de datos ---
FUENTE = "replay"                 # replay | azure | portal
FRACCION_REPLAY = 0.50            # % de mesas escrutadas en el replay
# Orden de carga simulado: timestamp2021 (orden real de publicación por junta, 2021) |
# prioridad2021 (minuto medio por parroquia, 2021) | aleatorio | directo | inverso.
ORDEN_REPLAY = "timestamp2021"

# --- Publicación ---
SALIDA_WEB = "web/datos_web.json"
PUBLICAR = False                  # True -> empuja a la rama de datos (PUBLISH_* / git)


def como_dict():
    return {
        "eleccion": ELECCION, "anio_eleccion": ANIO_ELECCION,
        "anio_referencia": ANIO_REFERENCIA,         "dignidades": DIGNIDADES,
        "metodo": METODO, "nivel": NIVEL, "fuente": FUENTE,
        "fraccion_replay": FRACCION_REPLAY, "orden_replay": ORDEN_REPLAY,
    }


def resumen():
    d = como_dict()
    return " | ".join(f"{k}={v}" for k, v in d.items())


if __name__ == "__main__":
    print(resumen())

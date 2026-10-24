import pandas as pd

# === ARCHIVOS DE ENTRADA Y SALIDA ===
ARCHIVO_DATOS = "cne_ec_2021_presidencia.csv"
ARCHIVO_CANDIDATOS = "cne_ec_2021_candidatos_presidencia.csv"
ARCHIVO_SALIDA = "mesas_resumido_tres_bloques2.csv"

print("Cargando archivos...")
df = pd.read_csv(ARCHIVO_DATOS)
df_cand = pd.read_csv(ARCHIVO_CANDIDATOS)

# === 1. CLASIFICACIÓN POLÍTICA POR CÓDIGO DE ORGANIZACIÓN POLÍTICA ===
correistas_ids = [1005,35]  # Andrés Arauz (UNES)
anticorreistas_ids = [
    21006,
    3,
    4,
    8,
    10,
    16,
    17051,
    19,
    20,
    23,
    25,
    33,
]  # Lasso, derecha y centroderecha aliada


def clasificar_bloque(cod):
  if cod in correistas_ids:
    return "votos_correistas"
  elif cod in anticorreistas_ids:
    return "votos_anticorreistas"
  else:
    return "votos_diferentes"


df["bloque"] = df["cod_org_pol"].apply(clasificar_bloque)

print("Agrupando votos por mesa y categoría política...")

# === 2. SUMAR VOTOS POR MESA Y BLOQUE (excluyendo 'updated' aquí para evitar duplicados) ===
votos_por_bloque = (
    df.pivot_table(
        index=[
            "acta_numero",
            "cod_prov",
            "cod_cant",
            "parroquia",
            "recinto",
            "junta",
        ],
        columns="bloque",
        values="votos",
        aggfunc="sum",
        fill_value=0,
    )
    .reset_index()
)

# === 3. EXTRAER VALORES FIJOS Y EL TIMESTAMP ÚNICO POR CADA MESA ===
fijos_por_mesa = (
    df.groupby("acta_numero")[["nulos", "blancos", "updated"]]
    .first()
    .reset_index()
)
fijos_por_mesa = fijos_por_mesa.rename(
    columns={"nulos": "voto_nulo", "blancos": "voto_blanco"}
)

# === 4. UNIR TABLAS DE FORMA LIMPIA ===
tabla_mesas = pd.merge(votos_por_bloque, fijos_por_mesa, on="acta_numero")

# Asegurar que existan las columnas de bloques por si alguna categoría salió en 0
for col in [
    "votos_correistas",
    "votos_anticorreistas",
    "votos_diferentes",
]:
  if col not in tabla_mesas.columns:
    tabla_mesas[col] = 0

# === 5. SELECCIÓN Y ORDEN FINAL DE COLUMNAS ===
# Orden solicitado: 1) timestamp, 2) canton, 3) provincia, 4) voto blanco, 5) voto nulo, 6+) bloques
columnas_finales = [
    "updated",
    "cod_cant",
    "cod_prov",
    "voto_blanco",
    "voto_nulo",
    "votos_correistas",
    "votos_anticorreistas",
    "votos_diferentes",
]

tabla_mesas = tabla_mesas[columnas_finales]

# === 6. GUARDAR RESULTADO ===
print(f"Guardando archivo resumido en {ARCHIVO_SALIDA}...")
tabla_mesas.to_csv(ARCHIVO_SALIDA, index=False)

print(
    f"¡Proceso completado con éxito! Total de mesas procesadas:"
    f" {len(tabla_mesas):,}"
)

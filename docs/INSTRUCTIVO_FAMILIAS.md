# Instructivo — Cómo completar la hoja `Mapa_familias` (XLSX)

**Archivo:** `familias_ecuador_2019_2023_2026.xlsx` — hoja **`Mapa_familias`**.

## Para qué sirve

Agrupar cada partido/movimiento (cada número de lista) en una **familia política estable**.
Las candidaturas y las **alianzas cambian** entre elecciones, pero las familias persisten:
al agruparlas podemos medir el **cambio de voto (swing)** entre 2019, 2023 y 2026 y así
proyectar mejor. **El modelo agrupa por familia, no por candidato.**

## Qué tenés que llenar

En la hoja `Mapa_familias`, columna **`familia`** (tiene un **desplegable** con las
opciones válidas):

- Viene pre-cargada con nuestras sugerencias (`familia_sugerida`). **Revisá y corregí.**
- Podés usar la columna **`notas`** para aclarar casos dudosos.
- La columna **`correismo_2026`** da pistas del correísmo en 2026 (no la edites).

Columnas de la hoja:

| Columna | Qué es |
|---|---|
| `lista` | Número de lista de la organización (clave). |
| `nombre_2019` / `nombre_2023` / `nombre_2026` | Nombre de la organización en cada año. |
| `correismo_2026` | Pista: vehículos del correísmo en 2026. |
| `familia_sugerida` | Lo que propusimos automáticamente. |
| **`familia`** | **← lo que tenés que completar.** |
| `notas` | Comentarios opcionales. |

## Reglas

1. **Usá solo** las etiquetas del desplegable (hoja `Vocabulario`). Si hace falta una
   familia nueva, avisá y la agregamos al vocabulario.
2. La familia sigue la **identidad/linaje** del partido aunque cambie de nombre o número
   de lista. Ejemplos:
   - **FCS (2019) → Revolución Ciudadana (2023)** = familia **`RC`**.
   - **Alianza PAIS → MOVER** = familia **`MOVER`**.
   - **Democracia Sí → Movimiento Futuro** = familia **`MF`** (lista 20).
3. Movimientos **puramente locales/provinciales** sin familia nacional → **`LOCAL`**
   (o `LOCAL-<provincia>` si querés distinguirlos).
4. **2026 — caso especial:** `RC` (lista 5) y `Amigo` (16) están **suspendidas**, y el
   correísmo corre bajo otras tiendas (PSE 17, UP 2, Todos 70, y acuerdos reservados).
   Definí a qué familia corresponde cada tienda **en 2026**. Las opciones típicas son:
   - Mapear esas tiendas a **`RC`** (tratar todo el correísmo como una familia), **o**
   - dejar cada partido en su propia familia (**`PSE`**, **`UP`**, etc.) y usar `notas`
     para marcar que en 2026 lleva candidatos del correísmo.
   - **Marcá el criterio que elijas** para que sea consistente en todas las filas.
5. **Si dudás:** dejá la celda **vacía** y anotalo en `notas`. Es mejor vacío que mal
   asignado (una familia equivocada distorsiona el swing).

## Vocabulario de familias

`RC` · `PSC` · `MUPP` · `CREO` · `SUMA` · `ID` · `UP` · `PSP` · `CD` · `Avanza` ·
`PSE` · `MF` · `MOVER` · `CONSTRUYE` · `PID` · `AMIGO` · `ADN` · `RETO` · `LOCAL` · `OTRO`

## Ejemplos

| lista | nombre (2023) | familia |
|---|---|---|
| 5 | Revolución Ciudadana | `RC` |
| 6 | Partido Social Cristiano | `PSC` |
| 18 | Pachakutik (MUPP) | `MUPP` |
| 21 | CREO | `CREO` |
| 35 | MOVER | `MOVER` |
| 62 | Alianza por la Unidad Manabita (local) | `LOCAL` |
| 17 (2026) | PSE (lleva candidatos del correísmo) | `PSE` **o** `RC` (según el criterio elegido) |

## Cómo se usa

Las hojas **`Familias`** y **`Ganadores`** muestran la evolución (votos y
prefecturas/alcaldías ganadas por familia en 2019 y 2023) para ayudarte a decidir.
La columna `familia` se usa luego para homologar partidos entre años en el modelo de
proyección y en la detección de anomalías.

## Al terminar

Devolvé el XLSX con la columna **`familia`** completa (y `notas` donde haga falta).

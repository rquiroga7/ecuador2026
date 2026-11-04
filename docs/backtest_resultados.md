# Resultados — Backtest de métodos de proyección (local 2019 → 2023)

> Ejecución del plan `docs/backtest.md`. Compara swing jerárquico (varias combinaciones de
> niveles), v2/v4 y v1 a **10% y 20%** de escrutado, con orden de carga 2021 extrapolado.
> Datos: `D:\ecuador2026_data\backtest\variantes_swing.csv`,
> `resumen_variantes.csv`.

## 1. Datos (Fase 0)

- 2019 por junta: **d2 35.774 juntas / 7,43M votos (91,8%)**; **d4 37.039 / 8,48M (94,1%)**
  (vs oficiales ~8,09M / ~9,01M).
- **Pendiente**: prov. 23 (Sto. Dgo. Tsáchilas) se está crawleando (se incorporará en
  re-ejecución automática). Prov. 20 (Galápagos) no tiene prefecto (0 cantones) → sin datos.
- Consolidación deduplicada por `prov-cant-parr-zona-junta-sexo`.

## 2. Homologación (Fase 1)

- 2019 nombre→lista: **100% de los votos** mapeados (catálogo de organizaciones + alianzas).
- Distribución 2019 (prefecto):
  - **2 bloques**: correísmo 13,4% / resto 86,6%.
  - **3 bloques + residual**: derecha 48,6% · otros 38,0% · correísmo 13,4%.
  - **familias**: PSC 18,6 · LOCAL 14,7 · RC 13,4 · CREO 12,3 · ID 6,4 · MUPP 4,9 · …
- **Corrección de homologación**: la lista 35 (Alianza PAIS-2019) se excluyó del bloque
  correísmo y cae en "otros" (no en derecha). En 2023 la 35 es MOVER (derecha) y su votante
  no se transfiere a RC; incluirla inflaba la base (Loja: base 29,5% vs. real 10,8%).

## 3. Comparación (err de composición, puntos)

**Familias** (realista):
| dignidad | método | err@10% | err@20% |
|---|---|---|---|
| prefecto | **v1@zona** | **5,90** | **3,58** |
| prefecto | hier N-P-C-Pa | 12,53 | 9,31 |
| prefecto | v2 nacional | 13,48 | 10,62 |
| alcalde | **v1@zona** | **12,51** | **6,47** |
| alcalde | hier N-P-C-Pa | 17,89 | 14,46 |
| alcalde | v2 nacional | 15,75 | 13,25 |

**2 bloques**:
| dignidad | método | err@10% | err@20% |
|---|---|---|---|
| prefecto | v1@zona | 2,62 | 0,63 |
| prefecto | v4:prov | **0,03** | 2,27 |
| prefecto | hier N-P-Z | 1,94 | **0,52** |
| alcalde | v1@zona | 1,21 | 1,40 |
| alcalde | v1:provincia | **0,07** | **0,88** |
| alcalde | v2 nacional | 5,18 | 3,56 |

**3 bloques + residual**:
| dignidad | método | err@10% | err@20% |
|---|---|---|---|
| prefecto | v1@zona | 4,02 | **2,57** |
| prefecto | v4:prov | **1,30** (acc 54,5%) | 4,19 |
| prefecto | hier N-P-C-Pa | 7,76 | 3,39 |
| alcalde | v1@zona | 10,31 | **2,74** |
| alcalde | v1:cant-prov | **10,01** | 3,46 |
| alcalde | hier N-P-C | 12,81 | 3,27 |

## 4. Conclusiones

1. **En el esquema realista (familias), v1@zona gana** en prefecto y alcalde a 10% y 20%
   (menor error y acierto comparable/mejor). Ningún jerárquico/v2/v4 lo supera.
2. **En esquemas gruesos (2/3 bloques)** algunas variantes bajan el error en un corte
   (`v4:prov` a 10%; `hier N-P-Z` a 20%), pero **no de forma consistente** y a veces con
   **peor acierto** (p. ej. `v4:prov` 3bloques: err 1,30 pero acc 54,5%).
3. **La junta como unidad es peor que la zona para lo local** (err mucho mayor); la zona
   (recinto) es el nivel fino adecuado para prefecto/alcalde.
4. **No hay variante que supere a v1@zona de forma consistente** en los 3 esquemas y ambas
   fracciones. → Para 2026 local: **v1 a nivel zona**. Para nacional/general, el test
   previo (`backtest/presidencial.py`) mostró que **jerárquico a nivel junta** es el mejor.

## 5. Sensibilidad y pendientes

- Asignación de alianzas 2019 (LOCAL/OTRO residual 15–21%) es el principal ruido; por eso se
  corrieron 3 esquemas.
- AP-2019→MOVER en familias (caveat).
- Prov. 23 pendiente de crawl; se re-consolidará y re-ejecutará.

## 6. Mejoras a v1 (Paso 1 y Paso 2)

Alternativas probadas (unidad zona, 2019→2023, orden 2021; err nacional / acc):

- **A_soft** — cascada suavizada (mezcla de niveles n/(n+k)).
- **B_hyb** — híbrido base+swing mezclado con A_soft.
- **H_turn** — tamaño/participación (válidos base × factor de turnout encogido).
- **C_sim** — pares ponderados por similitud de share base.
- **G_ens** — ensamble 0,6·v1 + 0,2·jerárquico + 0,2·v2.
- **Combos (Paso 2)**: C1 (0,5 v1+0,3 G+0,2 Csim), C2 (0,4/0,4/0,2), C3_frac (dependiente
  del % escrutado) y C4 (0,5 v1+0,3 B_hyb+0,2 G).

**Familias (realista)** — mejoras sobre v1:

| dignidad | método | err@10 | err@20 | acc@10 | acc@20 |
|---|---|---|---|---|---|
| prefecto | v1 | 5,90 | 3,58 | 81,8% | 81,8% |
| prefecto | **C3_frac** | **5,42** | 3,58 | 86,4% | **90,9%** |
| prefecto | C1 | 5,56 | 3,53 | 90,9% | 90,9% |
| alcalde | v1 | 12,51 | 6,47 | 44,3% | 53,8% |
| alcalde | **C3_frac** | **10,05** | **5,04** | 45,7% | **59,0%** |
| alcalde | C2 | 10,49 | 5,21 | 46,2% | 57,6% |

**2/3 bloques** — los combos también bajan err y suben acc: C4 da err@20 de 0,02 (2bloques
alcalde) y 0,29 (2bloques prefecto); G_ens mejora 3bloques alcalde (6,45/0,86 vs 10,31/2,74
de v1).

**Conclusión del Paso 2**: combinar **v1 + G_ens + C_sim** con pesos dependientes del %
escrutado (**C3_frac**) es el mejor generalista: en familias mejora **err y acc** vs v1 en
prefecto y alcalde; en esquemas gruesos `G_ens`/`C4` son competitivos. Riesgo: pesos fijados
in-sample; validar en otro par (p. ej. presidencial 2021→2023) antes de congelar.

## 7. Correísmo vs principal opositor (3 variantes)

El esquema de 2 bloques **no sirve** para identificar al principal opositor (todo lo no
correísta queda en "resto"). Se comparan 3 variantes midiendo el error de los **dos
principales** (correísmo y su opositor): `err2 = ½(|Δcorreísmo| + |Δopositor|)` y `acc2` =
acierto correísmo-vs-opositor por territorio.

- **familias**: correísmo = RC; opositor = mayor familia de derecha (PSC).
- **3 bloques**: correísmo / derecha / otros; opositor = derecha.
- **4 bloques**: correísmo / derecha / izquierda / otros; opositor = derecha.

Resultados (≥100 votos, orden 2021; err2 en puntos / acc2):

| variante · dignidad | mejor@10% | mejor@20% |
|---|---|---|
| familias · prefecto | v4prov 1,49 (acc 86%) | **C3_frac 0,46 (acc 100%)** |
| familias · alcalde | hier 1,45 (acc 73%) | **C4 0,51 / C3_frac 1,29 (acc 84–86%)** |
| 3 bloques · prefecto | v4prov 0,42 (acc 82%) | **hier 0,75 (acc 100%)** |
| 3 bloques · alcalde | C3_frac 3,85 (acc 77%) | **C4 0,80 (acc 90%)** |
| 4 bloques · prefecto | v4prov 0,41 (acc 82%) | **hier 1,20 (acc 100%)** |
| 4 bloques · alcalde | C3_frac 3,59 (acc 76%) | **C4 0,82 (acc 89%)** |

**Recomendación para el correísmo**
- Usar **3 o 4 bloques** (no 2) para que el opositor sea un bloque propio.
- **Prefecto**: `hier` (jerárquico N-P-C-Pa) o `C3_frac`; **alcalde**: `C3_frac`/`C4`.
- En **familias**, `C3_frac` domina (prefecto acc 100% a 20%).
- `v2`/`v4:prov` a veces bajan err2 a 10% pero con peor `acc2`.

Riesgo: pesos in-sample; validar en presidencial 2021→2023.

## 9. Tabla de todos los modelos base (10/15/20%) — correísmo vs opositor

Se excluyen los combos lineales C3/C4 (y el ensamble G_ens) por objeciones metodológicas.
Modelos: `v1`, `est_A` (cascada suavizada), `est_B` (híbrido base+swing), `est_H`
(turnout), `est_C` (similitud), `v2`, `v4_{prov,cant,parr,zona}` y jerárquicos
`hier_N-P-Pa`, `hier_N-P-C-Pa`, `hier_N-P-C-Pa-Z`, `hier_N-P-C-Z`, `hier_N-P-C`, `hier_N-P-Z`.

Métricas: `err2 = ½(|Δcorreísmo|+|Δopositor|)` y `acc2` = acierto correísmo-vs-opositor.
Tabla completa: `D:\ecuador2026_data\backtest\correismo_tabla.csv`; resumen:
`correismo_tabla_resumen.csv`.

Mejor por celda (err2 y acc2):

| variante · dignidad | 10% | 15% | 20% |
|---|---|---|---|
| familias · prefecto | err2 `est_B` 0,74 · acc2 `est_C` 100% | err2 `est_H` 0,70 · acc2 `est_C` 100% | err2 `est_C` 0,70 · acc2 `est_C` 100% |
| familias · alcalde | err2 `hier N-P-C-Z` 1,45 · acc2 `v1` 82,6% | err2 `hier N-P-Pa` 0,48 · acc2 `v1` 83,2% | err2 `est_C` 1,16 · acc2 `v1` 84,8% |
| 3bloques · prefecto | err2 `est_B` 0,83 · acc2 `hier N-P-Pa` 91,3% | err2 `est_C` 0,45 · acc2 `est_B` 91,3% | err2 `hier N-P-Pa` 0,63 · acc2 `hier` 100% |
| 3bloques · alcalde | err2 `est_B` 3,16 · acc2 `est_A` 85,3% | err2 `v1` 0,95 · acc2 `est_A` 85,8% | err2 `est_B` 1,02 · acc2 `est_B` 87,2% |
| 4bloques · prefecto | err2 `est_B` 0,83 · acc2 `hier N-P-Pa` 95,7% | err2 `est_C` 0,75 · acc2 `hier` 100% | err2 `est_C` 0,98 · acc2 `hier` 100% |
| 4bloques · alcalde | err2 `est_B` 3,16 · acc2 `est_A` 85,3% | err2 `est_C` 0,94 · acc2 `est_A` 85,8% | err2 `est_B` 1,02 · acc2 `est_B` 87,2% |

Lecturas:
- **Prefecto**: el jerárquico (`hier N-P-Pa` / `N-P-C-Pa`) da el **mejor acierto** (95,7–100%);
  `est_B`/`est_C` dan el **mejor error** a 15–20%.
- **Alcalde**: `v1`/`est_A`/`est_H` dan el mejor acierto; `est_B` el mejor error a 20%.
- `est_C` (similitud) es fuerte a 15–20% en familias/4bloques.
- `v2`/`v4` suelen quedar por detrás en acierto; solo bajan err2 a 10% en algunas celdas.

## 10. Error por provincia + modelos est_B+H / est_C+H / est_B+C+H

Cambio de métrica (a pedido): el error de los dos principales (**correísmo vs opositor**) se
calcula **por provincia** y se promedia (sin ponderar por votos), en vez del agregado nacional.
`acc2` sigue por territorio. Se agregan `est_BH` (est_B × turnout), `est_CH` (est_C × turnout)
y `est_BCH` (mezcla de est_B y est_C × turnout).

**4 bloques** (opositor = derecha). Error = promedio provincial de `½(|Δcorreísmo|+|Δderecha|)`:

| método | pref@10 | pref@15 | pref@20 | alc@10 | alc@15 | alc@20 |
|---|---|---|---|---|---|---|
| v1 | 4,73 | 4,58 | **2,86** | 5,21 | 4,71 | 2,96 |
| est_A | 6,70 | 6,04 | 5,37 | 5,20 | 4,88 | 3,84 |
| est_B | 6,26 | 5,53 | 4,74 | 5,43 | 4,88 | 4,12 |
| est_C | 4,28 | 3,61 | 3,13 | 4,90 | 4,75 | 3,39 |
| est_H | 6,70 | 5,98 | 5,32 | 5,21 | 4,88 | 3,86 |
| est_BH | 6,27 | 5,51 | 4,70 | 5,44 | 4,89 | 4,13 |
| est_CH | 4,28 | 3,54 | 3,14 | 4,92 | 4,76 | 3,40 |
| **est_BCH** | 4,69 | 3,76 | 3,27 | **4,37** | **3,82** | **2,87** |
| v2 | 14,01 | 13,53 | 12,90 | 11,81 | 11,36 | 10,82 |
| v4_prov | 11,08 | 9,51 | 9,15 | 10,26 | 9,18 | 8,19 |
| hier_N-P-C-Pa | 6,89 | 5,70 | 4,07 | 8,12 | 6,87 | 5,12 |
| hier_N-P-Pa | 7,39 | 6,18 | 4,58 | 8,50 | 7,35 | 5,72 |

acc2 (%) — 4 bloques:

| método | pref@10 | pref@15 | pref@20 | alc@10 | alc@15 | alc@20 |
|---|---|---|---|---|---|---|
| v1 | 78,3 | 78,3 | 87,0 | 69,7 | 72,5 | 85,3 |
| est_B | 87,0 | 91,3 | 95,7 | 82,9 | 85,3 | **87,2** |
| est_BCH | 91,3 | 87,0 | 87,0 | 83,9 | 82,5 | 86,3 |
| est_CH | 82,6 | 78,3 | 82,6 | 81,5 | 75,4 | 80,1 |
| hier_N-P-C-Pa | **95,7** | **100,0** | **100,0** | 83,4 | 84,4 | 80,1 |

Lectura:
- **Error provincial**: `v1` es el mejor en prefecto a 15–20%; `est_BCH` es el mejor en
  alcalde (2,87 a 20%) y bueno en prefecto. `est_C`/`est_CH` mejoran a 10–15%.
- **Acierto**: `hier` domina en prefecto (95,7–100%); `est_B`/`est_BCH` en alcalde.
- `est_BH`/`est_CH` ≈ `est_B`/`est_C`: el factor de turnout es ≈1 (poco cambio de participación
  2019→2023), así que H no aporta.
- Los jerárquicos **sí difieren** entre sí, pero poco: con unidades zona, el nivel `zona` es la
  propia unidad (sin efecto en no escrutadas) y los efectos cantón/parroquia están muy
  encogidos; por eso err/acc quedan casi iguales. Para que los niveles pesen: usar unidades
  junta, subir `ks` o agregar covariables (base share).

Tabla completa: `correismo_tabla.csv`; tabla ancha 4 bloques: `tabla_4bloques.csv`.

## 11. Reproducir

```
python -m backtest.consolidar_2019
python -m datos.homologar_2019
python -m backtest.variantes_swing
python -m backtest.resumen_variantes
python -m backtest.mejoras_v1
python -m backtest.mejoras_v1_paso2
python -m backtest.correismo_variantes
python -m backtest.tabla_correismo
python -m backtest.estB_grid
```

## 12. Grilla de variaciones de est_B (4 bloques, error provincial)

> **Nota**: esta grilla se calculó **antes** de excluir la lista 35-2019 del bloque correísmo.
> Tras la corrección (ver §2 y §13), los valores absolutos cambian; la comparación relativa
> `sim` / `robust_sim` se mantiene, pero la calibración vigente es la de §13.

Sobre `est_B` (mezcla base+swing / pares), grilla OFAT + interacciones (~34 variantes).
Métrica: error promedio por provincia de correísmo+derecha; `acc2` por territorio; 10/15/20%.
Detalle: `D:\ecuador2026_data\backtest\estB_grid.csv`.

Ganador claro (prefecto y alcalde): **`sim`** = est_B con **pares por similitud** (clip on);
equivale a `est_BCH`. El resto de dimensiones (nat, ks, logit, sizew, robust, clip solo) aportan
poco o empeoran.

| variante | pref err@10/15/20 | pref acc@10/15/20 | alc err@10/15/20 | alc acc@10/15/20 |
|---|---|---|---|---|
| base | 7,91/6,75/6,61 | 87/87/96 | 6,81/6,31/5,45 | 82/84/85 |
| clip | 7,93/6,78/6,65 | 87/87/96 | 6,76/6,33/5,54 | 82/84/85 |
| **sim** | **4,86/4,16/3,40** | **91/91/96** | **4,73/3,81/3,09** | 83/81/84 |
| sim_lam25 | 4,15/3,32/2,90 | 83/87/83 | 4,57/4,05/2,82 | 83/82/84 |
| robust_sim | 4,89/4,29/3,47 | 91/91/96 | 4,77/3,78/3,19 | 83/83/86 |
| nat_sim | 4,86/4,16/3,40 | 91/91/96 | 4,73/3,81/3,09 | 83/81/84 |

Lectura:
- **`sim` reduce el error ~3 puntos** vs base y **sube el acierto** en prefecto (87→91%),
  con alcalde similar; `robust_sim` es levemente mejor en acierto de alcalde.
- `sim_lam25` baja más el error pero **empeora el acierto** en prefecto.
- `clip` solo no cambia (no hubo shares negativas en 4 bloques); `nat`, `ks`, `logit`, `sizew`
  no aportan.
- Sobre la duda de la métrica: el "top-2 por dignidad" a nivel nacional es derecha+correísmo
  (idéntico a la pareja fija); usar el top-2 por **provincia** no cambia la conclusión.

**Recomendación**: usar **`sim` (est_B + pares por similitud)** como modelo local principal;
`robust_sim` si se prioriza acierto en alcalde. Validar en presidencial 2021→2023 antes de congelar.

## 13. Calibración de robust_sim y validación presidencial

> **Corrección de homologación (2026-11)**: la lista 35 (Alianza PAIS-2019) se excluyó del
> bloque correísmo (cae en "otros"). En 2023 la 35 es MOVER (derecha) y su votante no se
> transfiere a RC; incluirla inflaba la base (Loja: base 29,5% vs. real 10,8%). Todos los
> números de esta sección usan ya la base corregida.

Calibré λ y ks de `robust_sim` (median + sim + clip) en local 2019→2023, 4 bloques.
`ks` casi no importa (diferencias <0,01); `λ` sí mueve acierto/error. Detalle local por
dignidad (err promedio provincial correísmo+derecha / acc, a 10/15/20%):

| λ | prefecto err/acc | alcalde err/acc |
|---|---|---|
| 0,50 | 4,3/95,7 · 3,8/91,3 · 3,1/100 | 4,7/83,4 · 3,8/87,7 · 3,2/88,2 |
| 0,65 | 4,6/95,7 · 4,2/95,7 · 3,6/100 | 5,0/83,4 · 4,2/87,7 · 3,6/87,7 |
| 0,75 | 4,9/95,7 · 4,5/95,7 · 3,9/100 | 5,3/84,4 · 4,5/87,7 · 4,0/87,7 |

Agregado (media prefecto+alcalde): λ=0,65 → acc 0,918 / err 4,21; λ=0,75 → acc 0,918 /
err 4,51; λ=0,50 → acc 0,910 / err 3,85.

**Validación fuera de muestra — presidencial 2021→2023 (misma arena), zona, 2 bloques**
(err provincial de cuota correísta / acc correísmo-vs-resto) — no depende de la corrección
2019 (usa 2021→2023):

| método | 10% | 15% | 20% |
|---|---|---|---|
| v1 | 5,87 / 83,3% | 5,31 / 87,5% | 5,59 / 79,2% |
| sim (λ=0,5) | 1,98 / 91,7% | 2,21 / 87,5% | 2,58 / 83,3% |
| robust_sim (λ=0,5) | 2,30 / 91,7% | 2,43 / 87,5% | 2,78 / 83,3% |
| **robust_sim (λ=0,75)** | **2,08 / 91,7%** | **1,91 / 87,5%** | **2,36 / 87,5%** |

**Conclusiones**
- `robust_sim` **generaliza**: en presidencial baja el error a ~2 pts (vs ~5,5 de v1) con
  igual o mejor acierto. No hay sobreajuste al par local.
- Tras corregir la base 2019, **λ=0,65 domina a 0,75** en local (mismo acierto, menor error);
  en alcalde λ=0,5 sigue siendo el mejor (menor err y acc igual o mayor).
- Recomendación: `robust_sim` con **λ=0,65 en prefecto** y **λ=0,5 en alcalde**;
  presidencial/nacional λ=0,75. `ks=(2,4,8,16)`.
- **Loja** (2019→2023): con la base corregida, la cuota de `robust_sim` baja de ~16,4% a
  ~13,9% (λ=0,75) / ~13,3% (λ=0,5) frente a final 10,8%; el crudo (11,2%) sigue más cerca
  porque las zonas contadas primero ya reflejan el nivel 2023. El residuo es geográfico/timing,
  no de homologación.

Scripts: `backtest/robust_sim_tune.py`, `backtest/validar_presidencial.py`,
`backtest/grafico_robust_sim.py`.

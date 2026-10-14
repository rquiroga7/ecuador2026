# Plan — Proyección y auditoría de las Seccionales Ecuador 2026

Elección: **domingo 29 de noviembre de 2026**. Objetivo: proyectar el resultado final
de las 23 prefecturas, 222 alcaldías y concejalías a partir del escrutinio parcial, y
**señalar las mesas (juntas) anómalas** para focalizar la fiscalización.

Este plan se organiza en **cinco frentes**:

| Frente | Qué hace | Entregable |
|---|---|---|
| **A. Datos históricos y validación** | Descargar/reconstruir 2019, 2023, 2025; probar que el método de Brasil funciona en Ecuador | Backtest calibrado + bases por mesa |
| **B. Adquisición en vivo** | Bajar el escrutinio 2026 en tiempo real (Azure Files) | Snapshots por mesa + serie de progreso |
| **C. Proyección y sitio** | Modelo en vivo + dashboard | JSON + web con ganadores proyectados |
| **D. Detección de anomalías** | Forense (Mebane) sobre mesas | Ranking de mesas sospechosas + mapas |
| **E. Inferencia ecológica** | Migración de votos entre ciclos por mesa (EM/Goodman/bootstrap) | Matrices de transición + sankeys |

La documentación de descubrimiento está en `docs/FINDINGS.md`. Los frentes son
independientes hasta la Fase de integración (F).

> **Decisión (2026-10-13).** El backtest se hace **2019 → 2023** (referencia 2019,
> objetivo 2023), que es la misma tarea que 2023 → 2026. La inferencia ecológica se
> incluye desde ya, pero su parte más rica es **post-elección** (cuando existan los
> resultados finales de 2026 y se puedan estimar las matrices 2023 → 2026).

---

## Fase 0 — Limpieza del repositorio (Brasil → Ecuador)

Objetivo: dejar solo el andamiaje reutilizable y el nuevo andamiaje de Ecuador.

**Borrar de `main` (64 archivos versionados, ver `docs/FINDINGS.md` §5):**

- Datos y artefactos de Brasil: `data/*` (elecciones-2022.js, mun-jerarquia.json,
  tse_ibge.json, secciones_*.json, proyeccion-calibracion.json), todo `plot/*`.
- Scrapers y variantes: `scrapingbrasil2022.py`, `scrapingbrasil2026*.py` (5),
  `zonpasG_rodri.py`, `descargar_secciones.py`.
- Proyecciones específicas: `extrapolador10B.py`, `extrapolador10B_rodri.py`,
  `proyeccion_swing.py`, `proyeccion_v3.py`, `proyeccion_v4.py`,
  `proyeccion_schteingart.py`, `reconstruir_lanzamiento.py`, `runner_local.py`.
- `COMO_PROYECTAMOS.md` (se reemplaza), `plot/` completo.
- Datos crudos fuera del repo en `D:\brasil2026_data` y junctions NTFS
  (`dados_tse_2022`, `backtest_snapshots`, `backtest_resultados`).

**Conservar (se adapta):**

- `rutas_datos.py` → nueva raíz `D:\ecuador2026_data`, subcarpetas nuevas.
- `proyeccion.py` (clase `Proyector`, agnóstica al país).
- `backtest.py` (estructura de snapshots/bins), `inferencia_ecologica*.py` (EM/sankey/socio).
- `index.html`, `config.js`, `.github/workflows/pages.yml`, `worker/`, `publicar_rodri.py`.
- `estilo_plot.py` (actualizar créditos).

**Estructura objetivo del repo:**

```
ecuador2026/
  docs/                 FINDINGS.md · PLAN.md · FORENSE.md
  datos/                (Frente A) descarga y parseo de bases históricas
    catalogo.py          parsea CATALOGO.xls → parquet de dimensiones
    parsear_resultados.py txt CNE por mesa → parquet tidy
    jerarquia.py         provincia→cantón→parroquia→zona→junta
    descargar_bases.py   bases 2019/2023/2025 desde cne.gob.ec
  vivo/                 (Frente B) adquisición en tiempo real
    azure.py             Azure Files: listar/espejar incremental
    instantaneas.py      snapshots por mesa + serie de progreso
  modelo/               (Frente C) proyección
    proyeccion.py        Proyector genérico (logit-swing jerárquico)
    bloques.py           candidato → partido/movimiento por elección
    proyectar.py         proyección en vivo por dignidad
    dhondt.py            asignación de escaños (concejales)
  forense/              (Frente D) anomalías
    digitos.py           2BL, LastC, C05s, P05s, Skew, Kurt, DipT
    participacion.py     distribución + Sobyanin + regresión no paramétrica
    mezclas.py           modelo de mezclas finitas (eforensics)
    ranking.py           score compuesto por mesa
  inferencia/           (Frente E) migración de votos por mesa
    ecologica.py         EM/Goodman/bootstrap (portado de inferencia_ecologica.py)
    socio.py             cruce socioeconómico (portado de inferencia_ecologica_socio.py)
  backtest/             validación 2019→2023 con órdenes de carga simulados
  web/                  index.html · config.js
  plot/                 salidas
```

> La limpieza se ejecuta al confirmar el alcance (preguntas abiertas en
> `docs/FINDINGS.md` §9).

---

## Frente A — Datos históricos y validación del método

**A0. Reconstruir elecciones pasadas.** Descargar y parsear a nivel de mesa:

- **Seccionales 2023** (ya en `DATOS2023CNE.zip`) — ancla del modelo.
- **Seccionales 2019** — para el backtest 2019→2023.
- **Generales 2025** y **2021 / anticipadas 2023** — señal de swing nacional por partido.

Herramientas:

- `datos/catalogo.py` — lee `CATALOGO.zip` (PROVINCIA, CANTON, PARROQUIA, ZONA,
  JUNTA, CIRCUNSCRIPCION, DIGNIDAD, PARTIDO, CANDIDATOS) → parquet dimensiones.
- `datos/parsear_resultados.py` — parser del formato pipe-decodificado
  (`FINDINGS.md` §4): agrega sexos F+M, arma `votos[mesa, candidato]`, `totales[mesa]`
  (emitidos, blancos, nulos) y **join** con catálogos; salida parquet/csv por dignidad.
- `datos/jerarquia.py` — jerarquía geográfica + normalización de códigos.
- `datos/descargar_bases.py` — descarga las bases del CNE (con manejo de Incapsula si
  hiciera falta).
- `datos/padron.py` — electores habilitados (N) por junta, para participación.

**A1. Construir bloques de partidos** (`modelo/bloques.py`).

- Mapear cada candidato a su **organización política** (una candidatura puede ser
  alianza; `PARTIDO.xls` + `LIS_PARTIDO`/`NUM_PARTIDO`).
- Definir por ciclo un conjunto de bloques (p. ej. RC/5, ADN, PSC/6, MUPP/18, CREO/21,
  SUMA/23, ID/12, movimientos provinciales/locales, "otros").
- Homologar movimientos entre 2019, 2023 y 2026 (fusiones, cambios de nombre).

**A2. Validar el método de Brasil en Ecuador** (`backtest/`).

- Usar 2019 como referencia y proyectar **2023** (misma dignidad), que es la misma
  tarea que 2023→2026 pero con un cambio posiblemente mayor.
- **Sin timestamps por mesa** (ver `FINDINGS.md` §8): construir snapshots con
  **órdenes de carga simulados**:
  - *aleatorio*, *real por provincia/cantón* (si se reconstruye), *sesgado*
    (urbanas/oficialistas primero) y *adverso*.
- Reutilizar `backtest.py`: medir error de la proyección por trámite de % escrutado
  (2%, 5%, 10%, …, 50%) y **calibrar los márgenes** (`proyeccion-calibracion.json`).
- Comparar contra conteo crudo y contra "extrapolar solo lo escrutado".

**Criterio de éxito A:** con ≤5% escrutado, el error mediano del ganador proyectado
por alcaldía/prefectura debe ser sustancialmente menor que el del conteo crudo, y los
márgenes calibrados deben cubrir el error real.

---

## Frente B — Adquisición en vivo (Azure Files)

**B0. Azure.** SDK `azure-storage-file-share` (a instalar). Conexión con SAS /
connection string vigente. Shares conocidas: `cne-medios`, `cne-ops` (cuenta
`stresultadoscne2025`); confirmar la de 2026.

- `vivo/azure.py`: listar la share, **espejo incremental** (solo ficheros nuevos/
  cambiados, por ETag/size/hash), descarga reanudable, y registro de
  `(ruta, hora_local_descarga, etag, hash)`.
- Detectar si los ficheros traen **versión/progreso/timestamp** propio para ordenar la
  carga; si no, guardar nuestro reloj de descarga.

**B1. Normalización en vivo** (`vivo/instantaneas.py`).

- Convertir cada volcado a una **instantánea por mesa** en formato tidy (mismo esquema
  que el histórico del Frente A), para que el modelo consuma histórico y vivo igual.
- Serie temporal nacional/provincial: `% actas procesadas`, votos por bloque.
- `control_versiones` para no reprocesar lo ya visto.

**B2. Respaldo (opcional).** Si Azure falla o no cubre 2026, raspador de respaldo del
portal con navegador headless (Incapsula) o del canal de Telegram/App. Decisión abierta.

---

## Frente C — Proyección y datos del sitio

**C0. Modelo** (`modelo/proyeccion.py`): se porta la clase `Proyector` de Brasil
(logit-swing jerárquico) generalizada a:

- Bloques = partidos/movimientos.
- Jerarquía = `nacional → provincia → cantón → parroquia → zona`.
- Múltiples dignidades con distinto ámbito (prefecto provincial; alcalde y concejales
  cantonales).
- Concejales: `modelo/dhondt.py` reparte escaños sobre los votos proyectados.

**C1. Proyección en vivo** (`modelo/proyectar.py`): lee la última instantánea, corre
el modelo por dignidad y escribe `datos_proyeccion_*.json` (nacional + por
provincia/cantón) con:
- % escrutado, ganador proyectado + margen/banda calibrada,
- comparación con el conteo crudo,
- evolución temporal.

**C2. Sitio** (`web/index.html` + `config.js`): dashboard con selector de dignidad
(prefecto/alcalde/concejales), mapa por provincia y cantón, y pestañas de
"crudo" vs "proyectado". Reutiliza `index.html` (Chart.js) y el pipeline de
publicación (`publicar_rodri.py`, rama `data`, GitHub Pages, worker).

> **Diseño detallado del dashboard en `docs/DASHBOARD.md`** (3 pestañas: prefecturas con
> mapas y método v1; detalle de una prefectura con evolución; alcaldías por prefectura).

---

## Frente D — Detección de outliers para fiscalización

Objetivo: un **score por mesa** que priorice dónde auditar (prefectura/alcaldía/
concejalías) el día del escrutinio. Ver `docs/FORENSE.md` (métodos de Mebane).

- `forense/digitos.py` — 2BL (≈4.187), LastC (≈4.5), C05s/P05s (≈0.2), Skew, Kurt,
  DipT. A nivel de **mesa** (nunca de máquina, por REDWL).
- `forense/participacion.py` — distribución de participación, detección de "spikes"
  (0/5, 100%), y relación participación ↔ share (Sobyanin, regresión no paramétrica).
- `forense/mezclas.py` — modelo de mezclas finitas (`eforensics`): N/V/W por mesa →
  `π2, π3`, `α`, `τ`, `ν`, y probabilidad/magnitud de fraude por mesa.
- `forense/ranking.py` — combina las señales en un *score* por mesa, con mapas y
  listado priorizado (provincia, cantón, parroquia, zona, junta) y FDR para múltiples
  comparaciones.
- Integración: cruzar las mesas anómalas con la proyección (¿las mesas que "mueven" el
  resultado están señaladas?).

Advertencia metodológica (Mebane): digit tests y multimodalidad tienen **falsos
positivos** (voto estratégico, coaliciones). El score señala **candidatos a revisión**,
no prueba fraude; se debe combinar con denuncias y observación.

---

## Frente E — Inferencia ecológica (migración de votos)

Recicla `inferencia_ecologica.py` y `inferencia_ecologica_socio.py` (hoy de Brasil:
bloques Lula/Bolsonaro/otros/no-voto, secciones EM) para estimar, por **mesa**, las
**matrices de transición de voto** entre ciclos con **EM / Goodman / bootstrap**,
incluyendo a quienes no votaron. A diferencia de Brasil (presidencial, mismo candidato),
en Ecuador los bloques son **partidos/movimientos**.

Pares a estimar:
- **2019 → 2023** seccionales (mismo par de dignidades) — disponible.
- **2023 → 2026** seccionales — **el producto estrella, post-elección** (nov 2026).
- **2023 general → 2025 general** — señal de swing nacional intercalado.
- Encadenado **2019 → 2023 → 2026** por producto de matrices (Markov).

Niveles: nacional, por provincia y por cantón. Salidas: matrices de transición,
heatmaps y **sankeys** (PNG + HTML) y un informe ES/PT.

Nota: la inferencia ecológica por mesa exige **mesas comunes** entre ciclos; hay que
resolver el emparejamiento `(provincia, cantón, parroquia, zona, junta)` entre
elecciones (hay juntas que se crean/eliminan; usar la jerarquía del Frente A).

---

## Fase F — Integración y operación el día de la elección

1. Congelar el modelo con márgenes calibrados (A2).
2. Ciclo automático: B (Azure) → normalizar → C (proyectar) → publicar → D (forense).
3. Dashboard público + lista privada de mesas a fiscalizar para el equipo.
4. Registro de todo (versiones, horas, hash) para reproducibilidad.

---

## Herramientas y dependencias a desarrollar

| Módulo | Estado | Notas |
|---|---|---|
| `rutas_datos.py` | adaptar | raíz `D:\ecuador2026_data` |
| `datos/catalogo.py` | nuevo | xls → parquet; `xlrd`/`openpyxl` ya instalados |
| `datos/parsear_resultados.py` | nuevo | parser pipe; agregación F+M |
| `datos/jerarquia.py` | nuevo | jerarquía y normalización |
| `datos/descargar_bases.py` | nuevo | CNE static DBs |
| `datos/padron.py` | nuevo | electores habilitados por junta |
| `modelo/proyeccion.py` | portar | `Proyector` de `proyeccion.py` |
| `modelo/bloques.py` | nuevo | candidato→partido, homologación |
| `modelo/proyectar.py` | nuevo | multipropósito |
| `modelo/dhondt.py` | nuevo | concejales |
| `vivo/azure.py` | nuevo | `azure-storage-file-share` (**instalar**) |
| `vivo/instantaneas.py` | nuevo | snapshots por mesa |
| `forense/digitos.py` | nuevo | tests de Mebane |
| `forense/participacion.py` | nuevo | turnout/Sobyanin |
| `forense/mezclas.py` | nuevo | `eforensics` (portar/llamar a R) |
| `forense/ranking.py` | nuevo | score + mapas |
| `inferencia/ecologica.py` | portar | EM/Goodman/bootstrap + sankey |
| `inferencia/socio.py` | portar | cruce con censo/contexto Ecuador |
| `backtest/*` | adaptar | de `backtest.py` |
| `web/*`, `publicar_rodri.py` | adaptar | contrato de datos Ecuador |
| `estilo_plot.py` | adaptar | créditos |

Dependencias: `pandas`, `numpy`, `matplotlib`, `requests`, `xlrd`, `openpyxl`
(presentes); **instalar** `azure-storage-file-share`; opcional R + `EFToolkit` /
`eforensics` (o portar el EM a Python).

---

## Riesgos

- **Sin timestamps por mesa** → el backtest depende de órdenes simulados; validar con
  2025 si se logran snapshots reales.
- **Incapsula** bloquea el acceso directo al portal.
- **Credenciales Azure** expiran; la share puede ser de 2025 y no de 2026.
- **Volatilidad de alianzas** entre ciclos complica la homologación de bloques.
- **Concejales** (plurinominal, D'Hondt) es el nivel más difícil; los métodos de
  fraude están pensados para contiendas con un "ganador" claro.
- **Sin padrón por junta** no hay participación ni modelo de mezclas; confirmar fuente.

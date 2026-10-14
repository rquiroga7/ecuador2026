# Hallazgos — Ecuador Seccionales 2026

Documento de descubrimiento. Reúne qué datos existen, cómo están estructurados, qué
se puede reutilizar del repositorio de Brasil y qué métodos de auditoría aplicaremos.
Fecha de la investigación: 2026-10-13.

---

## 1. Objetivo

Convertir este repositorio (hoy de la elección presidencial de **Brasil 2026**) en un
sistema de **proyección a partir de escrutinio parcial** y **auditoría forense** de las
**Elecciones Seccionales y de CPCCS de Ecuador**, que se celebran el
**domingo 29 de noviembre de 2026** (adelantadas desde el 14 de febrero de 2027).

Dignidades a proyectar (período 2027–2031):

| Dignidad | Cantidad | Ámbito | Dignidad CNE |
|---|---:|---|---:|
| Prefecta/o y Viceprefecta/o | 23 fórmulas | provincial | 11 |
| Alcaldesa/Alcalde | 222 | cantonal | 13 |
| Concejales/as urbanos | 909 | urbano cantonal | 14 |
| Concejales/as rurales | 457 | rural cantonal | 12 |
| Vocales de juntas parroquiales | 4.131 | parroquial rural | 15 |
| Consejeros/as CPCCS | 7 | nacional | 16/17/18 |

La idea es **respetar lo ya escrutado y estimar lo que falta**, a nivel de **mesa
(junta receptora del voto)**, corrigiendo el sesgo de orden geográfico de carga, tal
como se hizo con las secciones electorales del TSE en Brasil.

---

## 2. La diferencia clave respecto de Brasil

| | Brasil 2026 | Ecuador 2026 (seccionales) |
|---|---|---|
| Contienda | 1 candidato nacional (presidente) | 23 prefecturas + 222 alcaldías + concejales |
| Unidad base | sección electoral (~470k) | **junta receptora del voto** (mesa) |
| Referencia natural | 2022 (misma dignidad, mismo candidato) | **2023 seccionales** (misma dignidad, **otro candidato**) |
| Eje del *swing* | candidato (Lula, Flávio) | **partido/movimiento** (las candidaturas cambian entre ciclos) |
| Escrutinio | rapidísimo (~2 h), timestamps por BU | más lento, **sin timestamps por mesa** |
| Seats | no aplica | alcaldes/prefectos mayoría simple; **concejales por D'Hondt** |

Consecuencias:

1. El modelo de swing debe medirse a **nivel de partido/movimiento**, no de persona.
   Las alianzas y los candidatos cambian; lo que persiste es la organización política.
2. Habrá que decidir, por cada ciclo, a qué "bloque" mapea cada candidato (el número
   de lista puede ser una alianza de varios movimientos concatenados, ver §5).
3. Los **concejales** se proyectan a nivel de partido y luego se asignan escaños con
   el método D'Hondt (igual que ya ocurre en el conteo real).
4. Sin timestamps reales de mesa, el backtest a bajo % de escrutado hay que
   construirlo con **órdenes de carga simulados** (aleatorio, sesgado por geografía,
   adverso) y calibrar los márgenes de error; ver §8.

---

## 3. Fuentes de datos

### 3.1 Bases de datos oficiales (estáticas, resultados finales)

El CNE publica bases por proceso en <https://www.cne.gob.ec/estadisticas/bases-de-datos/>.
Secciones relevantes:

- **Elecciones Seccionales, CPCCS y Referéndum 2023** (ancla `z7648`) — ya la tenemos
  como `DATOS2023CNE.zip` (18 MB, descargada).
- **Elecciones Seccionales 2019** (ancla `z6553`) — **pendiente de descargar**; es la
  referencia para validar el método (2019 → 2023). Necesaria para el backtest.
- **Elecciones Generales 2025** (ancla `z8325`) — resultados por vuelta a nivel de mesa
  (`Primera Vuelta` 18.12 MB, wpdmdl=57396; `Segunda Vuelta`, wpdmdl≈). Dignidades:
  Presidente/Vice, Asambleístas (nacionales, provinciales y del exterior) y
  Parlamentarios Andinos.
- **Elecciones Generales 2021** (ancla `z6924`) — ídem (`Primera Vuelta` 13 MB,
  wpdmdl=20904).
- **Presidenciales/Legislativas Anticipadas 2023** (ancla `z7790`) — ídem.

> **Aclaración clave (dignidades).** Las **generales** (2021, 2023 anticipadas, 2025)
> eligen cargos **nacionales/legislativos** — Presidente/Vice, Asambleístas
> (nacionales, provinciales y del exterior) y Parlamentarios Andinos —, **no cargos
> locales**. Los cargos **locales** (prefectos, alcaldes, concejales, vocales de juntas
> parroquiales) se eligen solo en las **seccionales** (2019, 2023, 2026). Por eso **no
> hay un par local 2023→2025**: la única secuencia local es 2019→2023 (y 2026), y
> **2019 no tiene base a nivel de junta** (solo el PDF agregado + catalogs + padrón +
> resultados parroquiales de vocales).
>
> Las bases de las **generales** (2021, 2025) que entrega el CNE son a nivel
> **parroquia × sexo** (no de junta) y sirven para **calibrar la maquinaria** (sesgo de
> orden de carga + swing jerárquico) a nivel parroquia y para estudiar las
> **Asambleístas provinciales**, un análogo cercano a los prefectos. La validez
> **política** del modelo local se prueba con el **par 2019→2023 a nivel parroquia**
> (prefecto y alcalde), que ya está armado.

### 3.1-bis Bases `.sav` del CNE (parroquia × sexo) — hallazgo 2026-10-13

Las bases que el CNE entrega por el Download Manager están en **SPSS `.sav`** y su
granularidad es **parroquia × sexo** (la junta se agrega dentro de la parroquia; **no
hay número de junta**). Unidad: `unidad_id = provincia-cantón-circunscripción-parroquia-sexo`.
Se leen con `pandas.read_spss` (requiere **pyreadstat**).

Archivos descargados en `D:\ecuador2026_data\raw\`:

| Archivo | Filas | Dignidades | Notas |
|---|---:|---|---|
| `2019_Resultados-a-nivel-parroquial-1.sav` | 194.035 | prefecto(2), concejal rural(3), alcalde(4), concejal urbano(5), vocales(6) | resultados **locales 2019** |
| `2021_Primera-vuelta-1.sav` | 164.968 | 1, 7, 8, 9 | general 2021 (nacional) |
| `2025_Primera-Vuelta.sav` | 138.862 | 11–16 | general 2025 (nacional) |
| `CANDIDATOS.sav` | 41.512 | — | catálogo de candidatos 2019 (+`CANDIDATO_ESTADO`=ELECTOS) |
| `organizaciones polticas 2019.sav` | 426 | — | `OP_CODIGO`→`OP_LISTA` (número de lista), siglas |
| `dignidades 2019.sav`, `provincias/cantones/parroquias 2019.sav` | — | — | dimensiones |
| `registro electoral a nivel parroquial 2019.sav` | 7.717 | — | padrón por parroquia/sexo/edad |

**Consecuencia (importante):** tenemos un **par local 2019→2023 a nivel parroquia**
(1.200+ parroquias), que alcanza para validar el método de proyección en cargos locales
a esa granularidad. Lo que **no** existe es 2019 a nivel de **junta**; la junta solo
está para 2023 (y para 2026 en vivo).

**Clave de partido:** en 2019 el partido se identifica por `OP_LISTA` (número de lista
del movimiento); en 2023 por la **lista cabeza** de nuestra capa de bloques. La
homologación de partidos entre ciclos (sobre todo movimientos locales) es un paso
explícito del modelo.

**Concejales:** en los `.sav` los votos vienen **por candidato** (dentro de una lista,
los candidatos tienen votos distintos), así que la suma no es el voto de la lista. El
reparto D'Hondt exige el voto de lista → **se posterga** el análisis de concejales hasta
resolver ese mapeo. Prefecto y alcalde (unipersonales) están limpios y son la prioridad.

Los portales de resultados en vivo:

- `https://app01.cne.gob.ec/resultados2023/` — navegable por Provincia → Cantón →
  Circunscripción → Parroquia → Zona → **Junta**. Tiene "VER ACTA DE RESULTADOS".
  Está detrás de **Incapsula** (WAF): un `requests` simple recibe un desafío JS.
- `https://resultados2025.cne.gob.ec/` — mismo sistema (SIER) para las Generales 2025.
- Canales alternos: Bot de Telegram `CNEOficialBot` y la CNE App.

**Bloqueo de acceso programático (2026-10-13).** El sitio `www.cne.gob.ec` está detrás
de **F5 BIG-IP (TSPD)** y la API `wp-json` responde "Request Rejected"; los archivos
estáticos (`wp-content/uploads/...`) también cortan la conexión. El Download Manager
carga los enlaces por **AJAX** (`?wpdmactask=listsub&...&parent=<id>&__wpdmacn=<nonce>`),
y necesita el *nonce* de una sesión de navegador. Por eso **no se puede descargar 2019
(ancla `z6553`) de forma automática** con `requests`/`Invoke-WebRequest`.

Opciones para conseguir las bases (2019, 2025, etc.) y los datos en vivo de 2026:
1. **Azure Files** (canal previsto) con una SAS vigente.
2. **Descarga manual** desde un navegador (el usuario baja el zip y lo deja en
   `D:\ecuador2026_data\raw\`).
3. **Navegador headless** (Playwright/Selenium) que resuelva el desafío F5 — pesado,
   pero también serviría de respaldo para el escrutinio en vivo.

**Problema central:** ni el portal ni los dumps oficiales traen **marca de tiempo por
mesa**. No se puede reconstruir el orden real de publicación mesa a mesa como se hizo
con `DT_RECEBIMENTO_BU_HOR_TSE` del TSE. Ver §8.

### 3.3 APIs del CNE y capturas en vivo (junta + timestamp) — hallazgo 2026-10-13

Los portales de resultados del CNE están respaldados por **APIs REST** que devuelven
**actas por junta** con un **timestamp de corte** (`corte`). Esto es exactamente el
análogo del `DT_RECEBIMENTO_BU_HOR_TSE` del TSE: permite reconstruir el **orden real
de publicación** y el sesgo geográfico de carga.

Endpoints conocidos:
- 2021: `https://resultados2021.cne.gob.ec/Home/ConsultarResultados` (POST JSON).
- 2023 (generales y anticipadas): `https://elecciones.cne.gob.ec/certero-cne/api/v1/total-provincias?codDignidad=11&codProvincia=0`
  (requiere `Authorization: Bearer <JWT>` de ~1 min). Ver el blog de jreyesr
  (`blog.jreyesr.com/posts/election-data/`).
- 2023 seccionales: `https://app01.cne.gob.ec/resultados2023/`; 2025:
  `https://resultados2025.cne.gob.ec/` y `resultados2025-2v.cne.gob.ec`.

**Fuentes de terceros con datos a nivel de junta/mesa:**

| Fuente | Año | Nivel | Timestamp | Notas |
|---|---|---|---|---|
| **gavg712/elecciones-ecuador-2021** (GitLab, Gabriel Gaona) | 2021 | **junta** | **sí (`updated`, 763 snapshots)** | 39.844 juntas, 637.542 filas; `voto_acumulado` nacional. **Descargado**: `raw\gaona_2021_presidencia_junta.csv` |
| **RickyTB/elecciones-2021** (GitHub) | 2021 | **junta** | no | presidente (16 cands, ancho); esquema FK provincia→…→junta (`tables.sql`). **Descargado** |
| **svallejovera/Elecciones_2021_EC** (GitHub) | 2021 | **junta** | no | `presi_data_clean.Rdata` + asambleístas provinciales por junta; scraper RSelenium |
| **jreyesr** (blog) | 2023 general | junta (actas) | sí (`corte`) | captura vía Burp del API `certero-cne` |
| **Juanmanuelph21/ecuador2025-scraping-analisis** (GitHub) | 2025 | junta/parroquia | (scraper) | scripts Python contra `resultados2025.cne.gob.ec` |
| **Giuseppe Gangi** (`ggangi.com`, `macedoniadelnorte.com`) | — | actas | — | plataformas VZ/EC/BO; sin dataset EC abierto claro |
| **ELECU** (USFQ; PyPI `elecu`; repo GitHub) | 2002–2023 | **parroquia** | no | convierte los `.sav` del CNE a CSV estandarizados (152 archivos) |

**Respuesta a la pregunta "¿hay datos por junta/mesa para 2019/2021/2025?"**
- **2021: sí** (junta, y con timestamp en Gaona → sirve para calibrar la carga).
- **2025: parcial** — el CNE entrega `.sav` **parroquia**; el scraper de la comunidad
  apunta al portal en vivo (junta/parroquia) pero no hallamos dataset ya capturado.
- **2019: no** a nivel de junta (solo `.sav` parroquia + PDF + padrón).
- **2023 seccionales (feb):** el portal `app01` existe; **no hallamos captura pública**
  aún (es el par local que más falta; vale la pena buscarlo o scrapearlo).

**Consecuencia operativa:** para **2026** podemos scrapear el API del CNE en vivo a
nivel de **junta y con timestamps** (como hicieron Gaona/jreyesr), sin depender solo de
Azure. Y usamos **2021** (Gaona) como caso de calibración real del sesgo de orden de
carga.

### 3.2 Azure File Storage (la vía preferida para datos en vivo)

En `Claves_Azure_File_Storage_test.txt` hay dos SAS apuntando a:

```
https://stresultadoscne2025.file.core.windows.net/cne-medios   (sp=rl, sr=s)
https://stresultadoscne2025.file.core.windows.net/cne-ops      (sp=rl, sr=s)
```

Es **Azure Files** (REST/SMB), cuenta creada para las Generales 2025, pensada para
distribuir resultados a medios. Los SAS de prueba **ya expiraron (2025-02-07)**.

Plan: usar Azure Files como canal primario (en lugar de scrapear el portal), con el
SDK `azure-storage-file-share` (o `azure-storage-file`). Hay que:

- Conectar con una **SAS vigente** (o una *connection string* / service principal) que
  el CNE/medio provea para 2026.
- **Espejar incrementalmente** la share (bajar solo lo nuevo/cambiado), con hashes y
  log de versiones, y guardar snapshots con hora local de descarga (nuestro reloj).
- Confirmar si los ficheros de la share traen **algún timestamp propio** o un campo
  de versión/progreso que permita ordenar la carga (aunque sea por bloque geográfico).

> El paquete `azure` **no está instalado** en el entorno actual; hay que agregarlo
> (`pip install azure-storage-file-share`). Python 3.14.5, pandas 3.0.5, numpy 2.5.2,
> matplotlib 3.11.1, requests 2.34.2, xlrd 2.0.2, openpyxl 3.1.5 ya están presentes.

### 3.3 Que la relación con `DATOS2023CNE.zip` (lo que ya tenemos)

```
DATOS2023CNE.zip
├── INDICE.xls                                     (mapa junta → archivo de acta)
├── CATALOGO.zip
│   ├── PROVINCIA.xls  CANTON.xls  PARROQUIA.xls  ZONA.xls
│   ├── JUNTA.xls  CIRCUNSCRIPCION.xls  DIGNIDAD.xls
│   ├── PARTIDO.xls  CANDIDATOS.xls
├── PREFECTA_PREFECTO_2023.02.28_13.00.02.txt      (22.6 MB, dignidad 11)
├── ALCALDESA_ALCALDE_2023.02.28_13.00.22.txt      (20.9 MB, dignidad 13)
├── CONCEJALES_URBANOS_2023.02.28_13.00.14.txt     (14.3 MB, dignidad 14)
├── CONCEJALES_RURALES_2023.02.28_13.00.20.txt      (4.3 MB, dignidad 12)
├── CPCCS_HOMBRES_...txt  CPCCS_MUJERES_...txt     (dignidades 17 y 16)
└── (sin VOCALES DE JUNTA PARROQUIAL, dignidad 15)
```

---

## 4. Esquema de los ficheros de resultados (decodificado)

Cada `.txt` es **pipe-delimited sin cabecera**, una fila por (mesa, sexo, candidato).
Verificado cruzando los catálogos y dos mesas de Cuenca (Azuay):

| Col | Campo | Ejemplo | Notas |
|---:|---|---|---|
| c0 | `COD_DIGNIDAD` | `11` | 11 prefecto, 12 conc. rural, 13 alcalde, 14 conc. urbano, 15 vocales, 16/17/18 CPCCS |
| c1 | `COD_PROVINCIA` | `1` | Azuay |
| c2 | `COD_CANTON` | `260` | Cuenca |
| c3 | `COD_CIRCUNSCRIPCION` | `0` | 0 rural, 1/2 urbana |
| c4 | `COD_PARROQUIA` | `285` | Baños |
| c5 | `COD_ZONA` | `1` | |
| c6 | `JUNTA` | `1` | número de junta dentro de la zona |
| c7 | `SEXO` | `F` / `M` | **la mesa se parte en dos registros F y M** |
| c8 | `COD_JUNTA` | `46001` | id único de la junta (F y M tienen ids distintos) |
| c9 | `LISTA` / org. política | `002`, `001033004021` | número de lista; en alianzas parece concatenar listas |
| c10 | `COD_CANDIDATO` | `11010101` | 11 = dignidad, 01 = provincia, resto = secuencia |
| c11 | total votos de la mesa | `274` | sufragantes (V) |
| c12 | blancos **o** nulos | `27` | orden exacto a confirmar |
| c13 | el otro (nulos/blancos) | `44` | |
| c14 | **votos del candidato** | `34` | |

Verificación aritmética (dos mesas): `c11 − c12 − c13 = Σ c14`.
Ej. mesa F 46001: `274 − 27 − 44 = 203 = 23+34+37+6+9+3+23+11+41+16`.

**La unidad "mesa" es la junta single-sex (`cod_junta`).** Verificado en el prefecto
2023: `cod_junta` es único y consistente → **40.058 mesas**, agrupadas en **20.941
ubicaciones físicas** (19.117 con mesa F y mesa M, 1.824 con una sola). Mediana de
votos por mesa ≈ **291** (máx. 387). Por eso **no** se suman F+M: cada `cod_junta` es
una mesa real (las juntas están segregadas por sexo).

**Clave de empalme entre elecciones.** `cod_junta` **no** es estable entre ciclos
(2019/2023/2026). La clave estable es **ubicación + sexo** =
`(provincia, cantón, circunscripción, parroquia, zona, junta, sexo)`; el parser la
expone como `mesa_id` (y `loc_id` sin sexo, para agregar F+M si conviene).

**Verificación aritmética.** Por mesa se cumple `c11 − c12 − c13 = Σ c14`, salvo
ruido de ±3 votos en ~11% de las mesas (inconsistencias de la fuente, no de parseo:
`max_abs_diff = 3`). Para los denominadores conviene usar **votos válidos = suma de
votos de candidatos**. (En CPCCS, que es voto múltiple, la suma de votos de candidatos
supera con creces a los sufragantes: ese chequeo no aplica.)

**Elegibles por mesa.** Los dumps **no** traen el número de electores habilitados
(N) por junta; solo votos emitidos (c11). Para el modelo forense (participación =
V/N) hay que cruzar con el **padrón** por junta (catalogado en `JUNTA.xls` y en las
bases de padrón del CNE).

### 4.1 Catálogos (dimensiones)

- `PROVINCIA`: `COD_PROVINCIA`, `NOM_PROVINCIA` (0 = ECUADOR).
- `CANTON`: `COD_CANTON`, `COD_PROVINCIA`, `NOM_CANTON`.
- `PARROQUIA`: `COD_PARROQUIA`, `COD_CANTON`, `NOM_PARROQUIA`.
- `ZONA`: `COD_ZONA`, `NOM_ZONA`, `COD_PARROQUIA`, `COD_CIRCUNSCRIPCION`.
- `JUNTA`: `COD_JUNTA`, `COD_PROVINCIA`, `COD_CANTON`, `COD_PARROQUIA`, `COD_ZONA`,
  `JUNTA`, `SEXO`.
- `CIRCUNSCRIPCION`: `COD_CIRCUNSCRIPCION`, `NOM_...`, `COD_PROVINCIA`, `COD_CANTON`
  (0 = rural, 1/2 = urbana; define cuántos concejales se eligen).
- `DIGNIDAD`: mapea código → nombre de dignidad.
- `PARTIDO`: `COD_PARTIDO`, `NOM_PARTIDO`, `LIS_PARTIDO`, `NUM_PARTIDO`.
- `CANDIDATOS`: `COD_CANDIDATO`, `NOM_CANDIDATO`, `COD_PARTIDO`, `COD_DIGNIDAD`.

### 4.2 Jerarquía geográfica

```
Provincia (24)  →  Cantón (222)  →  Parroquia  →  Zona  →  Junta (mesa)  [× sexo]
```

Es análoga a la del IBGE en Brasil (región → estado → intermedia → inmediata) pero
Ecuador es más somero. Para el *shrinkage* jerárquico del modelo usaremos
`provincia → cantón → parroquia → zona`, más un nivel nacional.

---

## 5. Inventario del repositorio actual (Brasil) y reutilización

64 archivos versionados. Resumen de qué sirve:

### Reutilizable casi tal cual
- `rutas_datos.py` — patrón de raíz de datos configurable (cambiar `D:\brasil2026_data`
  → `D:\ecuador2026_data` y las subcarpetas).
- `proyeccion.py` — clase `Proyector`: **logit-swing jerárquico** con pesos, ridge y
  encogimiento por nivel. El corazón del método es agnóstico al país.
- `estilo_plot.py` — pie de figura con créditos (actualizar autor/repo).
- `backtest.py` / `backtest_timestamped.py` — **estructura** de backtest (snapshots,
  bins por % escrutado, error |Δ|). Se reescribe la fuente de snapshots.
- `inferencia_ecologica.py` / `inferencia_ecologica_socio.py` — inferencia ecológica
  por EM/Goodman/bootstrap y cruces socioeconómicos. Muy reutilizable cambiando
  bloques y fuentes.
- `index.html` + `config.js` + `.github/workflows/pages.yml` + `worker/` — pipeline de
  dashboard y publicación; se reescribe el contrato de datos.
- `publicar_rodri.py` — publica el JSON a la rama `data` por *git plumbing*; reutilizable.

### Se reemplaza por completo (específico de Brasil)
- `scrapingbrasil2022.py`, `scrapingbrasil2026*.py` (5 variantes),
  `zonpasG_rodri.py`, `extrapolador10B*.py`, `proyeccion_v3.py`, `proyeccion_v4.py`,
  `proyeccion_swing.py`, `proyeccion_schteingart.py`, `reconstruir_lanzamiento.py`,
  `descargar_secciones.py`, `runner_local.py`.
- `data/elecciones-2022.js`, `data/mun-jerarquia.json`, `data/tse_ibge.json`,
  `data/secciones_*.json`, `data/proyeccion-calibracion.json`.
- `COMO_PROYECTAMOS.md` (reescribir para Ecuador).

### Datos generados (borrar/regenerar)
- `plot/*` (heatmaps, sankeys, informes, socio) — todo Brasil.
- Salidas crudas en `D:\brasil2026_data` (fuera del repo).

> El **scrub** de Brasil está descrito en `docs/PLAN.md` (Fase 0). No se ejecuta hasta
> confirmar el alcance.

---

## 6. Métodos forenses de Walter Mebane (detección de mesas sospechosas)

El objetivo es señalar **mesas/juntas anómalas** por participación y por patrones de
voto, e integrarlo con la proyección. El paquete de referencia es el **Election
Forensics Toolkit** de Mebane & Kalinin (`kkalininMI/EFToolkit`, R) y el modelo
bayesiano `eforensics` (Klimek et al. 2012 → Mebane 2016 → Ferrari, McAlister &
Mebane 2018). Núcleo conceptual y estadísticas:

### 6.1 Tests de dígitos (`BasicElectionForensics`)
Sobre los **conteos por unidad** (aquí, votos por junta para cada partido; y votos
emitidos/blancos/nulos):

- **2BL** — media del segundo dígito significativo; valor esperado bajo Benford ≈
  **4.187**. Desvíos sistemáticos = posible redondeo o fabricación humana.
- **LastC** — media del último dígito; esperado ≈ **4.5** (uniforme).
- **C05s** — indicador de último dígito 0/5 en **conteos**; esperado **0.2**.
- **P05s** — ídem en **porcentajes** redondeados; esperado **0.2**. Un exceso de 0/5
  tiene difícil explicación benigna.
- **Skew / Kurt / DipT** — asimetría, curtosis y test de unimodalidad de Hartigan.
- **Sobyanin** y **Correlation** — relación participación ↔ share del partido.

Caveat importante (Mebane 2013, `pm13.pdf`): el 2BL se **rechaza con frecuencia en
elecciones limpias**; la media condicional del segundo dígito responde a voto
estratégico, movilización y desbalance distrital. **No es diagnóstico de fraude por
sí solo.** En particular, Mebane desaconseja tests de dígitos a nivel de *máquina*
por el mecanismo REDWL ("roughly equal division with leftovers"); a nivel de mesa/
junta (varios miles de votos) sí es razonable, pero con cautela.

### 6.2 Participación y relación participación–voto
- Estimación de la distribución de la participación y detección de multimodalidad
  ("spikes" en 0/5 o en 100%).
- Regresión no paramétrica de la media del segundo dígito (o del share) contra la
  participación; intervalos donde `j̄ > 4.187` sugieren **traspaso de votos**
  (vote switching) y donde `j̄ < 4.187` en partidos con muchos votos sugiere
  **coerción/acarreo**.
- Referencia: Mebane & Kalinin, *Comparative Election Fraud Detection* (APSA 2009),
  `apsa09.pdf`. Aplicado a Rusia (2003-2008).

### 6.3 Modelo de mezclas finitas (`eforensics`) — "positive empirical model"
Entrada por unidad de agregación (mesa): `N` = electores habilitados, `V` = votos
emitidos, `W` = votos del **ganador/leader**, `A = N − V` = abstención. Tres
componentes de mezcla:

1. **sin fraude** (`π1`),
2. **fraude incremental** (`π2`): se transfiere una proporción moderada de votos
   desde la oposición (**robados**) y/o desde no votantes (**manufacturados**),
3. **fraude extremo** (`π3`): casi todos los votos se transfieren.

Parámetros: `α` (manufacturar vs. robar), `τ`/`σ_τ` (participación verdadera media y
sd), `ν`/`σ_ν` (share verdadero del leader), `θ`; y por observación las
probabilidades `f0i, fii, fei` y la **magnitud** de votos robados/manufacturados.
Salida: probabilidad de fraude por mesa + votos fraudulentos estimados + clasificación
`Zi ∈ {1,2,3}`. Implementación bayesiana (JAGS/MCMC) en el paquete R `eforensics`;
versión EM de máxima verosimilitud en Mebane (2016).

Advertencia del propio autor: **voto estratégico y coaliciones también generan
multimodalidad**; el modelo mide "anomalías", no prueba intención maliciosa. Hay que
combinarlo con información contextual (denuncias, observadores, dispositivos).

### 6.4 Modelos robustos con detección de outliers
- `Wand, Shotts, Sekhon, Mebane, Herron & Brady (2001)`, `Mebane & Sekhon (2004)`:
  multinomial sobre-parametrizado (EI/MNP) con detección de unidades atípicas.
- Útil para comparar el patrón de transferencia de votos entre mesas normales y
  atípicas.

### 6.5 Referencias (todas de acceso público)
- Mebane 2006, *Election Forensics: Vote Counts and Benford's Law* — `websites.umich.edu/~wmebane/pm06.pdf`
- Mebane 2007, *Statistics for Digits* — `~wmebane/pm07.pdf`
- Mebane 2008, *Election Forensics: Outlier and Digit Tests* — `~wmebane/aep2008.pdf`
- Mebane & Kalinin 2009, *Comparative Election Fraud Detection* — `~wmebane/apsa09.pdf`
- Mebane 2010, *…Difference?* (simulaciones estrategia/coerción) — `~wmebane/pm10.pdf`
- Mebane 2013, *…Meanings of Precinct Vote Counts' Second Digits* — `~wmebane/pm13.pdf`
- Mebane 2016, *…Frauds Tests and Observation-level Frauds Probabilities* — `~wmebane/mw16.pdf`
- Mebane 2019, *Frauds* (modelo `eforensics`) — `~wmebane/measfrauds.pdf`
- Klimek, Yegorov, Hanel & Thurner 2012, *Statistical Detection of Systematic Election Irregularities*, PNAS 109(41).
- **Election Forensics Toolkit (R)**: <https://github.com/kkalininMI/EFToolkit>
- **eforensics (R)**: <https://github.com/UMeforensics/eforensics_public>
- Guía: *A Guide to Election Forensics* (USAID/UMich, 2023).

### 6.6 Adaptación a Ecuador (mesas)
- Unidad: junta (mesa) sumando sexos; conteos por partido.
- Se puede correr por dignidad (prefecto y alcalde tienen un "leader" claro por
  cantón/provincia → encaja con el modelo de mezclas); para concejales (plurinominal)
  el concepto de "leader" es más difuso (advertencia de Mebane sobre sistemas
  proporcionales).
- N (electores habilitados) por mesa: cruzar con padrón.
- Histórico comparable: 2019 y 2023 seccionales, 2021/2023/2025 generales.

---

## 7. Cómo se proyectará (borrador)

1. **Referencia**: resultados 2023 por mesa y por **partido/movimiento** (bloques).
2. **Observado 2026**: votos por mesa ya escrutada → share por bloque.
3. **Swing** por bloque: `logit(% hoy) − logit(% 2023)`, con regresión ponderada +
   efectos jerárquicos `provincia → cantón → parroquia → zona` encogidos hacia el
   nivel superior (se reutiliza la clase `Proyector` de `proyeccion.py`).
4. **Votos esperados** por mesa: padrón 2026 × participación estimada (o lo contado /
   fracción escrutada).
5. **Votos faltantes** por mesa: se reparten según `logit⁻¹(share 2023 + swing)`,
   normalizado; luego **reparto dentro del bloque** por composición local.
6. **Concejales**: proyectar votos por partido a nivel cantonal y aplicar **D'Hondt**.
7. **Salida**: ganador proyectado por prefectura/alcaldía + margen ± y, opcionalmente,
   reparto de concejales, a distintos % de escrutado.

---

## 8. El problema del bajo % de escrutado sin timestamps

Brasil pudo reconstruir el orden **real** de carga con `DT_RECEBIMENTO_BU_HOR_TSE`.
Ecuador no tiene eso por mesa. Opciones, en orden de preferencia:

1. **Azure histórico**: si la share de Azure (2025, o una nueva de 2026) guarda
   snapshots versionados con hora, reconstruimos el orden real por bloque. Hay que
   averiguar qué hay dentro de `cne-medios` / `cne-ops`.
2. **Portal 2023/2025 con progreso**: aunque el portal no da hora por mesa, sí da
   `% de actas procesadas`. Si logramos capturar o reconstruir snapshots históricos
   (p. ej. vía Wayback Machine o registros de prensa), podemos ordenar por provincia/
   cantón y estimar el sesgo geográfico.
3. **Simulación** (fallback): como en `probar_proyeccion.py` de Brasil, generar
   órdenes de carga por escenarios — **aleatorio**, **sesgado por geografía**
   (provincias más urbanas/afines al oficialismo primero) y **adverso** — proyectar
   2023 desde 2019 y medir el error por tramo de % escrutado. Calibrar así los
   márgenes de confianza del modelo 2026.

En cualquiera de los casos, la salida debe reportar el error esperado por tramo de
escrutado (p.ej. 2%, 5%, 10%, …, 50%).

---

## 9. Decisiones tomadas y preguntas abiertas

**Decisiones (2026-10-13):**

1. **Referencia del backtest = seccionales 2019 → 2023.** Es la misma tarea que
   2023 → 2026. Descargar la base de mesa de 2019 desde el CNE.
2. **Azure**: las claves están en `Claves_Azure_File_Storage_test.txt`, pero los SAS
   **expiraron el 2025-02-07**. La cuenta (`stresultadoscne2025`) y las shares
   (`cne-medios`, `cne-ops`) se conocen; hay que **obtener un SAS vigente** (o una
   connection string) para 2026. El código se escribe igual, leyendo el SAS de una
   variable de entorno, nunca del repo.
3. **Limpieza**: se ejecutó la Fase 0 (borrados datos y scripts de Brasil solapados).
4. **Inferencia ecológica**: se incluye para Ecuador (nuevo Frente E en `PLAN.md`);
   su parte más valiosa es post-elección (matrices 2023 → 2026).

**Preguntas abiertas:**

5. **Azure 2026**: ¿qué contiene exactamente `cne-medios`/`cne-ops` (resultados por
   junta, actas, series) y con qué frecuencia se actualizan?
6. **Alcance por dignidad**: ¿empezamos por prefectos + alcaldes y luego concejales,
   o las cuatro de una?
7. **¿Mantenemos un raspador de respaldo** del portal (navegador headless por
   Incapsula) o confiamos solo en Azure?
8. **Identidad del repo**: ¿renombrar a `ecuador2026` y cambiar remoto/créditos?
9. **Padrón por junta**: confirmar de dónde se baja el número de electores habilitados
   por mesa (participación y modelo forense).

---

## 10. Primer backtest local 2019→2023 (nivel parroquia) — 2026-10-13

Se armó el par local a nivel **parroquia** (1.222 comunes) y se proyectó 2023 desde
2019 con la clase `Proyector` (logit-swing jerárquico `provincia→cantón→parroquia`),
tratando cada **partido** (número de lista) como bloque. Partidos homologados por
número de lista: cubren **98%** de los votos 2023 (prefecto) y **97,6%** (alcalde).

Órdenes de carga simulados: **aleatorio**, **prioridad 2021** (orden real observado en
la captura de Gaona 2021) y **adverso** (los que más cambian entran últimos).

Resultados (aciertos = ganador proyectado por territorio coincide con el final):

| Dignidad | Orden | 2% | 10% | 20% | 50% |
|---|---|---|---|---|---|
| **Prefecto** (23 prov.) | aleatorio | 10/23 | 18/23 | 18/23 | 21/23 |
| | prioridad 2021 | 9/23 | 15/23 | 18/23 | 21/23 |
| | adverso | 1/23 | 5/23 | 5/23 | 17/23 |
| **Alcalde** (219 cant.) | aleatorio | 48/219 | 60/219 | 79/219 | 127/219 |
| | prioridad 2021 | 46/219 | 66/219 | 69/219 | 117/219 |
| | adverso | 25/219 | 38/219 | 49/219 | 116/219 |

Lectura:
- **Prefecto**: el swing por partido funciona razonablemente (21/23 a 50%).
- **Alcalde**: mucho peor (~58% a 50%, incluso con medio país contado). Confirma que
  en lo local pesan **voto personal/incumbencia/alianzas locales** (28% movimientos
  locales en 2023): el swing por partido **no basta** para alcaldías.
- El orden **prioridad 2021** es claramente **no aleatorio** (peor que aleatorio)
  → existe un sesgo geográfico de carga real, que el modelo corrige solo en parte.
- El escenario **adverso** acota el peor caso razonable.

Salidas: `D:\ecuador2026_data\backtest\backtest_local_{prefecto,alcalde}_2019_2023.csv`,
`carga_2021_nacional.csv`, `sesgo_2021_provincia.csv`, `orden_parroquia_2021.csv`.

Próximos pasos del modelo local: reducir/agrupar bloques, incorporar
**candidato/incumbente/reelección** (conocidos para 2026), y tratar alianzas.

### 10.1 Versión 2 — bloques = familias políticas (`backtest/local_v2.py`)

Agrupar los ~40 partidos en **familias** (RC, PSC, MUPP, CREO, SUMA, ID, … LOCAL)
mejora y estabiliza el modelo. Métricas: `acc` = ganador exacto por territorio,
`top2` = el ganador real está en el top-2 proyectado, `err` = error de composición
(puntos), `crudo` = conteo crudo extrapolado.

**Prefecto** (23 provincias): baseline 2019 sin swing: acc 43.5%.

| orden | 2% | 10% | 20% | 50% |
|---|---|---|---|---|
| aleatorio  acc | 47.8% | 69.6% | 87.0% | 95.7% |
| aleatorio  top2 | 73.9% | 91.3% | 91.3% | 100% |
| prioridad2021 acc | 47.8% | 78.3% | 82.6% | 91.3% |
| prioridad2021 err (crudo) | 34.2 (30.1) | **20.9 (30.1)** | 17.7 (26.1) | 9.8 (21.4) |
| adverso acc | 13.0% | 26.1% | 39.1% | 73.9% |

**Alcalde** (219 cantones): baseline 2019 sin swing: acc 19.6%.

| orden | 2% | 10% | 20% | 50% |
|---|---|---|---|---|
| aleatorio  acc | 25.6% | 32.0% | 41.1% | 59.8% |
| aleatorio  top2 | 45.7% | 53.4% | 63.5% | 79.5% |
| prioridad2021 acc | 31.1% | 32.4% | 33.3% | 57.1% |
| prioridad2021 err (crudo) | 33.0 (26.4) | **23.7 (26.3)** | 19.9 (26.0) | 10.9 (19.5) |
| adverso acc | 22.4% | 16.0% | 34.7% | 54.3% |

Conclusiones:
- **El modelo de swing por familias corrige el sesgo de carga mejor que el conteo
  crudo** en el orden real (prioridad 2021): a 10-50% el error baja ~y el crudo se
  queda alto. Ese es el valor central (como en Brasil).
- **Prefecto**: proyección sólida (acc 87-96% desde 20%; top-2 ≥91%).
- **Alcalde**: manejable con expectativas realistas (acc ~60% a 50%, **top-2 ~80%**).
  Es el nivel "difícil": alta rotación de coaliciones.

**Estabilidad del ganador (2019→2023):** mismo partido (lista) 12.3% (alcalde) /
43.5% (prefecto); misma **familia** 19.6% / 43.5%; ganador 2023 ∈ top-3 2019: 31.5% /
56.5%. → En lo local manda el **voto personal/incumbencia y la rotación de alianzas**;
conviene reportar probabilidad/top-2, no un ganador duro.

### 10.3 Comparación de métodos (v2/v4 de Brasil vs jerárquico) — 2026-10-14

Se recuperaron de `brasil2026` los métodos **v2** (swing uniforme nacional) y **v4**
(swing por territorio encogido al nacional) y se portaron en `modelo/swing.py`. Se
comparan en `backtest/bloques_familia.py`. Aciertos de ganador **@10% escrutado**:

| orden | jerárquico | v2 nacional | v4 territorio | **v1 relleno** |
|---|---|---|---|---|
| Prefecto aleatorio | 73.9% | 52.2% | 52.2% | **87.0%** |
| Prefecto prioridad2021 | 65.2% | 39.1% | 43.5% | **78.3%** |
| Prefecto adverso | **52.2%** | 47.8% | 43.5% | 39.1% |
| Alcalde aleatorio | 39.8% | 30.8% | 30.8% | **48.9%** |
| Alcalde prioridad2021 | 33.0% | 26.7% | 27.1% | **40.7%** |
| Alcalde adverso | 30.8% | 28.5% | 28.5% | **34.8%** |

**Conclusión clave (2026-10-14):** el método **v1** (relleno espacial jerárquico
cantón→provincia→nación, portado de Brasil en `modelo/v1_brasil.py`) **gana casi
siempre**, y **no depende de mapear alianzas entre años** (usa solo los partidos
observados de la misma elección). Es el más robusto para cargos locales y debería ser
el **método principal** para 2026 (con el jerárquico como alternativa, y ambos
convergen al conteo a mayor % escrutado). Salvo en el caso *adverso* de prefecto, donde
el jerárquico tiene algo más de aciertos, v1 es superior en aciertos y en top-2.

> **Corrección crítica (2026-10-14).** La base 2019 subestimaba votos: las alianzas
> guardaban la lista como `"21-100"` y quedaban sin mapear (46% de votos perdidos).
> Se corrigió tomando la **cabeza** de la lista (`datos/parroquia.py`). Ahora 2019 suma
> completo (8,09 M prefecto / 9,01 M alcalde). Los números de esta sección ya son con la
> base corregida; el jerárquico sigue ganando (incluso en el caso adverso ahora).

### 10.3-bis XLSX de familias para revisión del experto

`datos/exportar_familias.py` genera
`D:\ecuador2026_data\familias_ecuador_2019_2023_2026.xlsx` con hojas:
`Partidos` (lista × año: nombres/siglas 2019-2023-2026, familia, votos y shares de
prefecto y alcalde, con deltas), `Familias` (votos por familia y año), `Ganadores`
(prefecturas/alcaldías ganadas por familia y año), `Mapa_familias` (editable) y
`Notas_2026`. Muestra la evolución real: **RC 13,5%→27,1% (prefecto) y 3→50 alcaldías**;
PSC 19,3%→11,0%; MUPP 4,8%→10,9%; locales 18%→10,9%. Nota 2026: **RC suspendida**
(lista 5) → el correísmo va bajo **AMIGO (16)** y ~27 movimientos aliados; ADN lista 7;
"Futuro" (antes Democracia Sí) lista 20.

Conclusión: el **jerárquico (Schteingart) gana en el orden realista y en el aleatorio**
(sobre todo prefecto); v2/v4 solo son más robustos en el **peor caso adverso**. Se
mantiene el jerárquico como método principal y v4 como respaldo conservador.

Renombres (para no cruzarse con los v1–v4 de Brasil): `backtest/bloques_lista.py`
(bloques = cada lista) y `backtest/bloques_familia.py` (bloques = familias + comparación).

### 10.4 Adquisición en vivo (Frente B)

- `vivo/scraper_cne.py` — captura del API del CNE con **timestamp propio** (`capturado_en`)
  y **respuesta cruda** guardada; adaptadores `post2021` (form POST a
  `/Home/ConsultarResultados`) y `certero` (GET JSON con JWT). Los hosts del CNE son
  **efímeros** (se apagan tras la elección), por eso es configurable vía `--base`.
- `vivo/azure.py` — espejo incremental de Azure Files (requiere SAS vigente 2026).

---

## 11. Backtest NACIONAL 2021→2025 (presidencial) — 2026-10-14

Se agregaron las presidenciales de **2021** y **2025** (`.sav` del CNE, nivel
parroquia; 1.296 parroquias comunes) y se repitió la comparación de métodos
(`backtest/nacional.py`). Bloques por código de organización (OP):

| Bloque | 2021 | 2025 |
|---|---|---|
| RC | Arauz (32,7%) | Luisa González (44,0%) |
| ADN | — (no existía) | Noboa (44,2%) |
| MUPP | Yaku Pérez | Leonidas Iza (5,2%) |
| CREO | Lasso (19,7%) | Tabacchi (0,3%) |
| ID | Hervás (15,7%) | — |
| PSC/otros | … | … |

Final 2025: **ADN 44,2% · RC 44,0%** (margen 0,2 pts). Error de composición
(puntos) **@10% escrutado**:

| orden | jerárquico | v2 nacional | v4 territorio | v1 relleno |
|---|---|---|---|---|
| aleatorio | **0,21** | 7,21 | 6,60 | 2,72 |
| prioridad2021 | **1,53** | 8,89 | 8,84 | 2,68 |
| adverso | **19,86** | 27,71 | 27,68 | 28,07 |

**Conclusión (confirma la hipótesis):** cuando los partidos están **claramente
delimitados** (elección nacional, pocos bloques, swing coherente), el **jerárquico
domina** — incluso proyectando un partido **nuevo** (ADN) a partir de una base de
2021 = 0. v2/v4 quedan muy atrás. En cambio, en lo **local** (seccionales, alianzas
que rotan) ganaba **v1**.

→ **Elección de método según el tipo de elección:** *nacional* → jerárquico;
*local (alcaldías/concejalías)* → v1. Para **prefectos** conviene comparar en vivo y
elegir (son provinciales, intermedios).

---

## 12. Forense: detección de mesas para fiscalizar — 2026-10-14

`forense/digitos.py` (2BL/chi², último dígito, C05s/P05s) y `forense/juntas.py`
(score por mesa: z del share del partido líder dentro del cantón/parroquia + z de
dígitos redondeados). Simulación con anomalías inyectadas en 5% de las 40.058 juntas
de **prefecto 2023** (`forense/simular.py`):

| escenario | AUC | TPR@1% FPR | TPR@5% FPR |
|---|---|---|---|
| boost obvio (+80% al líder) | 0,917 | 12% | 49% |
| boost medio (+40%) | 0,782 | 5% | 25% |
| boost sutil (+20%) | 0,631 | 2% | 10% |
| coerce (líder a 90%) | 0,921 | 13% | 50% |
| redondeo a múltiplos de 5 | 0,949 | 16% | 79% |
| redondeo a múltiplos de 10 | 0,884 | 16% | 72% |

Lectura: **fraudes obvios y señales de dígitos (redondeo) se detectan bien** (hasta 79%
a 5% FPR); los desvíos **sutiles de share son difíciles** (AUC 0,63). El score sirve
para **priorizar** fiscalización, no como veredicto. Pendiente: incorporar el modelo
de mezclas finitas (Mebane) — requiere electores habilitados (N) por junta.

## 13. Inferencia ecológica presidencial 2021→2025 — 2026-10-14

`inferencia/ecologica.py` (EM por parroquia; 1.296 parroquias). Matriz de transición
theta[j,k] = P(votar k en 2025 | votar j en 2021), en %:

| origen \ destino | RC | ADN | MUPP | CREO | PSC | RESTO | NOV |
|---|---|---|---|---|---|---|---|
| RC (Arauz) | **98,5** | 0,0 | 0,0 | 0,0 | 1,0 | 0,4 | 0,0 |
| MUPP (Yaku) | 17,9 | 39,8 | 27,3 | 0,2 | 0,0 | 5,4 | 9,4 |
| CREO (Lasso) | 0,0 | **95,0** | 0,0 | 0,4 | 0,6 | 4,0 | 0,0 |
| ID (Hervás) | 17,0 | 77,7 | 0,0 | 0,0 | 0,0 | 5,3 | 0,0 |
| RESTO | 46,7 | 31,8 | 0,0 | 1,2 | 2,6 | 17,8 | 0,0 |
| NOV (no votó) | 2,9 | 5,3 | 0,1 | 0,0 | 0,0 | 1,6 | **90,1** |

Lectura: el **voto correísta es muy leal** (RC→RC 98,5%); el **anti-correísmo se consolidó
en ADN** (CREO→ADN 95%, ID→ADN 78%, RESTO→ADN 32%); el MUPP se partió (40% ADN, 27%
se queda, 18% RC, 9% se abstuvo); **los no votantes se mantienen** (NOV→NOV 90%).
**Ahora sí incluye "No voto"** (con los registros electorales 2021/2025).

## 14. Datos de padrón y forense de participación — 2026-10-14

Se descargaron los **registros electorales** del CNE (nivel parroquia × sexo × edad):

| Año | Archivo | Electores | URL |
|---|---|---:|---|
| 2021 | `registro_electoral_2021.sav` | 13.099.150 | `…/download/registro-electoral/?wpdmdl=20902` |
| 2023 | `registro_electoral_parroquial_2023.sav` | 13.450.047 | `…/registro-electoral-a-nivel-parroquial-2023/?wpdmdl=39832` |
| 2025 | `registro_electoral_parroquial_2025.sav` | 13.736.315 | `…/registro-electoral-a-nivel-parroquial-5/?wpdmdl=57394` |

(`datos/registro.py`). Con eso: participación 2021 = **81,0%**, 2025 = **82,1%** (coincide
con lo oficial). **Limitación:** el padrón es parroquia, **no por junta** (el CNE no
publica electores por mesa) → el forense de turnout y el modelo de mezclas se corren a
nivel **parroquia** (o por provincia/cantón).

**Forense de participación** (`forense/juntas.py`): se agregaron señales de ballot stuffing
—`z_emit` (emitidos altos dentro del cantón) y `z_bn` (caída de blanco/nulo)— con señales
de un solo lado. En la simulación, el stuffing se detecta bien:

| escenario (5% de 40.015 juntas) | AUC | TPR@1% | TPR@5% |
|---|---|---|---|
| stuffing obvio (+80%) | 0,988 | 17% | 78% |
| stuffing medio (+30%) | 0,919 | 9% | 46% |
| stuffing sutil (+12%) | 0,743 | 1% | 12% |
| round5 (dígitos) | 0,954 | 16% | 79% |

**Modelo de mezclas finitas** (`forense/mezclas.py`, aprox. de Mebane/Klimek): GMM de 3
componentes sobre `[logit(turnout), logit(share del líder)]` por parroquia; el score es la
responsabilidad del componente de esquina alta (turnout+share) minoritario. Validación
inyectando fraude extremo (turnout 99%, share 90%) en 5% de las parroquias:
**AUC = 1,000 (2025)** y **0,998 (2021)**. Es una aproximación práctica (el modelo exacto
de Mebane está en el paquete R `eforensics`).

---

## 15. Frentes A–E: nuevas piezas (2026-10-14)

Se completaron piezas transversales de los cinco frentes.

### 15.1 Frente A — familias y candidaturas
- `datos/familias.py` es la **fuente única** lista → FAMILIA (antes duplicada en
  `modelo/bloques.py` y `backtest/bloques_familia.py`). Normaliza los tres formatos del
  CNE (`"5"`, `"005"`, `"018004035"` concatenada, `"21-100"` alianza) y **lee de vuelta**
  la hoja `Mapa_familias` del XLSX curado por el experto (overrides con caché por mtime).
  Añade las listas 2026 (ADN 7, Futuro/DSI 20, etc.).
- `datos/candidatos.py` — roster de candidaturas por año/dignidad con su familia
  (derivado de las bases tidy 2023) y `cargar_2026()`, que normaliza la lista definitiva
  del CNE (publicación **9-nov-2026**) con columnas flexibles → esquema estable.

### 15.2 Frente B — instantáneas por mesa
- `vivo/instantaneas.py` — normaliza cualquier fuente (histórico, volcado CNE `.txt`,
  respuesta cruda del API o **replay**) al **mismo esquema tidy por mesa** del histórico
  (`mesa_id, loc_id, cod_junta, cod_candidato, lista, familia, votos` + totales).
  Incluye `serie_replay()` (órdenes aleatorio/directo/inverso) para probar el pipeline
  completo sin datos en vivo y `progreso()` para la serie `% actas`.

### 15.3 Frente C — motor de proyección y dashboard
- `modelo/proyectar.py` — motor en vivo: proyecta por **familias** a nivel parroquia
  (método **v1** relleno jerárquico parroquia→cantón→provincia→nación; alternativa
  `jerarquico` de Schteingart), agrega a provincia (prefecto) y cantón (alcalde) y emite
  el **contrato `datos_web.json`** del dashboard. La referencia es 2023 por familia.
- `web/index.html` + `web/config.js` — dashboard estático (Chart.js + Leaflet opcional
  con `provincias.geojson`): pestañas **Prefecturas** (tarjetas + barras + mapa),
  **Detalle** (evolución proyectado vs crudo) y **Alcaldías** por provincia.
  Probado con un **replay** de 2023 (35% escrutado → 23 provincias, 221 cantones;
  la proyección nacional converge a la share final al 100%).

### 15.4 Frente D — ranking forense
- `forense/ranking.py` — combina las señales por mesa de `forense/juntas.py` en
  **p-valores** de una cola, los une con el método de **Simes** y controla FDR con
  **Benjamini–Hochberg**; produce un ranking con prioridad Alta/Media/Baja y el desglose
  de prioridad alta por provincia. Descarta mesas con <20 votantes (evita z de share
  inflado por denominadores diminutos). En prefecto 2023: 200 mesas Alta, 379 con q<0.05.

### 15.5 Frente E — inferencia ecológica local
- `inferencia/local.py` — matriz de transición de voto **entre familias** (EM +
  bootstrap) a nivel parroquia para **prefecto** y **alcalde** 2019→2023, **incluyendo
  No voto** (electores del registro − sufragantes por parroquia). Ejemplos: RC→RC 79%
  (prefecto), RC→RC 80% (alcalde); PSC→PSC 52%/41%; el No voto es mayormente leal
  (NOV→NOV 71%/79%). Salidas: CSV de `theta`, IC bootstrap, heatmap y resumen JSON.

## 16. Dashboard modular, mapas y ciclo en vivo (2026-10-14)

### 16.1 Configuración de la elección (modular)
`config_eleccion.py` concentra la elección objetivo (2026), la **referencia** (2023),
las dignidades, el **método** y la **fuente** (`replay`/`azure`/`portal`). Nada está
hardcodeado a 2026 en el resto del código: cambiar de elección (o probar con 2023) es
cambiar estos valores o pasarlos por CLI.

### 16.2 Dashboard (`web/`)
`web/index.html` (+ `web/config.js`) lee `datos_web.json` y dibuja **todo** desde el
JSON (elección, año, referencia, método, % escrutado). Tres pestañas: **Prefecturas**
(tarjetas + barras + **mapa de provincias**), **Detalle** (evolución nacional
proyectado vs crudo + tabla) y **Alcaldías** (selector de provincia + **mapa de
cantones** + tarjetas). Mapas con **Leaflet** y GeoJSON **local** (sin dependencia de
tiles propios).
Para verlo en prueba con **2023**:

```
python -m vivo.ciclo --fuente replay --anio 2023 --referencia 2019 --fraccion 0.30
python -m http.server 8000 --directory web     # abrir http://localhost:8000
```

### 16.3 GeoJSON con códigos del CNE (`datos/geo.py`)
Fuente: servicio ArcGIS del **INEC** (Provincias/Cantones del Ecuador, DPA), salida
GeoJSON WGS84; se **simplifica** con shapely (de 20/43 MB a **175/812 KB**). Salida:
`web/provincias.geojson` (`cod` 2 díg = DPA = CNE) y `web/cantones.geojson`
(`cod` = CNE por **cruce de nombre+provincia**, 220/224; los 4 sin código son cantones
nuevos que no están en el catálogo 2023). Créditos de la fuente: INEC / ArcGIS;
alternativa abierta: `pabl-o-ce/Ecuador-geoJSON` (MIT).

### 16.4 Azure Files rápido y robusto (`vivo/azure.py`)
Reescrito para tiempo real: **REST directo con SAS** (sin SDK), `requests.Session` con
**pool + descargas en paralelo** (hilos, `--workers`), **incremental** por ETag/tamaño
(con `If-None-Match`→304 y MD5 de respaldo), **reintentos** con backoff exponencial +
jitter y `Retry-After`, timeouts de conexión/lectura, descarga a `.part` **reanudable**
con `Range` y `os.replace` atómico, y registro `(ruta, capturado_en, etag, bytes, md5,
ms)`. `--patron`/`--profundidad` acotan el espejo. El listado XML (recursivo, tolerante
a namespaces) se verificó con respuestas sintéticas.

### 16.5 Ciclo en vivo (`vivo/ciclo.py`)
Une **captura → instantánea → proyección → publicación** en un comando, con
`--fuente replay|azure|portal`, `--loop/--intervalo`, y publicación a la rama `data`
por git o HTTP (reusa `publicar_rodri`). Probado end-to-end con `replay`
(`--anio 2023 --referencia 2019 --fraccion 0.30`): 23 provincias y 221 cantones,
proyección nacional que converge al final.

---
name: ecuador-seccionales-2026
description: Proyectar y auditar las Elecciones Seccionales y de CPCCS de Ecuador del 29 de noviembre de 2026 a partir del escrutinio parcial de mesas (juntas receptoras del voto), y detectar mesas anómalas para fiscalización. Usar cuando se trabaje en este repositorio (C:\Users\Usuario\Documents\GitHub\ecuador2026) sobre descarga/parseo de resultados del CNE, modelos de proyección (swing por partido, logit-swing jerárquico), backtest a bajo % escrutado, adquisición en vivo vía Azure Files, dashboard, o métodos forenses de Walter Mebane (tests de dígitos, participación, modelo de mezclas finitas). También al portar código del proyecto previo de Brasil 2026.
---

# Skill: Seccionales Ecuador 2026 (proyección y auditoría)

Este repositorio era de la elección presidencial de **Brasil 2026** y se está
convirtiendo en un sistema de **proyección + auditoría forense** de las
**Elecciones Seccionales de Ecuador (29-nov-2026)**: 23 prefectos, 222 alcaldes,
909 concejales urbanos, 457 concejales rurales, 4.131 vocales de juntas parroquiales
y 7 CPCCS.

## Documentación de referencia (leer primero)

- `docs/FINDINGS.md` — fuentes de datos, esquema CNE decodificado, Azure, y resumen
  de los métodos de Mebane con referencias.
- `docs/PLAN.md` — los **cuatro frentes** de trabajo y las herramientas a desarrollar.
- `docs/FORENSE.md` — el método de detección de outliers por mesa (fiscalización).

## Los cinco frentes de trabajo

1. **Histórico + validación**: descargar/parsear 2019, 2023 y 2025 a nivel de mesa;
   probar que el modelo de swing de Brasil funciona para Ecuador (backtest **2019→2023**).
2. **Adquisición en vivo**: Azure Files (cuenta `stresultadoscne2025`, shares
   `cne-medios`/`cne-ops`; el SAS de `Claves_Azure_File_Storage_test.txt` **expiró el
   2025-02-07** → obtener uno vigente para 2026) en lugar de scraping.
3. **Proyección + dashboard**: modelo logit-swing jerárquico por partido; JSON +
   sitio (Chart.js) reutilizando el pipeline de `index.html`/`publicar_rodri.py`.
4. **Detección de anomalías**: tests de Mebane por mesa (dígitos, participación,
   mezclas finitas) → score priorizado para fiscalización.
5. **Inferencia ecológica**: migración de votos entre ciclos por mesa (EM/Goodman/
   bootstrap, sankeys); lo más valioso es **post-elección** (matrices 2023→2026).

## Hechos clave que no hay que re-descubrir

- **Esquema de los `.txt` del CNE** (pipe, sin cabecera), una fila por
  (mesa, sexo, candidato): `c0` dignidad · `c1` provincia · `c2` cantón ·
  `c3` circunscripción · `c4` parroquia · `c5` zona · `c6` junta · `c7` sexo (F/M) ·
  `c8` COD_JUNTA · `c9` lista/org · `c10` COD_CANDIDATO · `c11` votos emitidos ·
  `c12`+`c13` blancos/nulos · `c14` votos del candidato.
  Verificado: `c11 − c12 − c13 = Σ c14`. **Agregar F+M por junta.**
- **Dignidades**: 11 prefecto · 12 concejales rurales · 13 alcalde ·
  14 concejales urbanos · 15 vocales junta parroquial · 16/17/18 CPCCS.
- `DATOS2023CNE.zip` (raíz del repo) ya trae los resultados **finales por mesa de 2023**
  y `CATALOGO.zip` (PROVINCIA, CANTON, PARROQUIA, ZONA, JUNTA, CIRCUNSCRIPCION,
  DIGNIDAD, PARTIDO, CANDIDATOS) e `INDICE.xls` (junta→acta).
- Las bases del CNE que se bajan por el Download Manager son **SPSS `.sav`** y su
  granularidad es **parroquia × sexo** (sin número de junta). Se leen con
  `pandas.read_spss` (necesita `pyreadstat`). En `D:\ecuador2026_data\raw\`.
- **Par local 2019→2023 a nivel parroquia** (prefecto/alcalde) ya está armado
  (`datos/parroquia.py`) → permite validar la proyección de cargos locales. 2019 **no**
  tiene nivel de junta.
- Las **generales** (2021, 2025) eligen cargos **nacionales**, no locales; sirven para
  calibrar la maquinaria (nivel parroquia) y para asambleístas provinciales.
- Los `.sav` de **concejales** traen voto por candidato (no de lista) → D'Hondt
  postergado; prefecto/alcalde son la prioridad.
- **No hay timestamps por mesa** en el portal ni en los dumps → el backtest a bajo
  % escrutado usa **órdenes de carga simulados** (aleatorio/sesgado/adverso).
- Los resultados son **pipe-delimited latin-1**; los catálogos son `.xls` (usar xlrd;
  ojo con los avisos "OLE2 inconsistency", son benignos).
- La diferencia con Brasil: el **swing se mide por partido/movimiento**, no por
  candidato (las candidaturas cambian entre ciclos).

## Entorno

- Windows, PowerShell 5.1. Python 3.14.5 con pandas, numpy, matplotlib, requests,
  xlrd, openpyxl. **Falta** `azure-storage-file-share` (`pip install azure-storage-file-share`).
- Datos en `D:\` (raíz configurable vía `rutas_datos.py`).
- El portal `app01.cne.gob.ec` está detrás de **Incapsula** (un `requests` simple
  recibe un desafío JS).

## Convenciones al portar código de Brasil

- Reutilizable: `proyeccion.py` (clase `Proyector`), `backtest.py` (estructura),
  `inferencia_ecologica*.py` (EM/Sankey/socio), `index.html` + `worker/` +
  `publicar_rodri.py` (publicación), `rutas_datos.py` (patrón de rutas).
- A reemplazar: todos los `scrapingbrasil*.py`, `extrapolador10B*.py`,
  `proyeccion_v3/v4/swing/schteingart.py`, `descargar_secciones.py`, y los datos
  `data/*.js|json` de Brasil.
- El portugués de columnas/datos de Brasil (`Lula`, `Flavio_Bolsonaro`, `estado_uf`,
  `zona`, `secao`) se reemplaza por el esquema ecuatoriano (provincia, cantón,
  parroquia, zona, junta; candidato/partido).

## Reglas al trabajar aquí

- No ejecutar el borrado de datos de Brasil sin confirmar (ver `docs/PLAN.md` Fase 0).
- Citar siempre la fuente y el nivel de agregación; aclarar que los tests forenses
  **priorizan**, no prueban fraude.
- Nunca aplicar tests de dígitos a nivel de máquina (mecanismo REDWL de Mebane); la
  unidad es la **junta/mesa**.
- No commitear credenciales de Azure (el archivo `Claves_Azure_File_Storage_test.txt`
  contiene SAS: no versionar; rotar).

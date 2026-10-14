# Ecuador 2026 — Proyección y auditoría de las Elecciones Seccionales

Proyección del resultado final de las **Elecciones Seccionales y de CPCCS de Ecuador**
del **domingo 29 de noviembre de 2026** a partir del **escrutinio parcial** a nivel de
**mesa (junta receptora del voto)**, y **detección de mesas anómalas** para focalizar
la fiscalización.

**Autor:** Rodrigo Quiroga
**Colaboración:** trabajo realizado en colaboración con el **Dr. Roberto Etchenique**.

> Este repositorio parte del sistema desarrollado para la elección presidencial de
> **Brasil 2026** (metodología de proyección de swing y backtest con la carga real).
> Ver `docs/FINDINGS.md` para el mapeo de qué se reutiliza.

---

## Qué contiene / contendrá

1. **Datos históricos por mesa** del CNE (seccionales 2019 y 2023; generales 2021,
   2023 y 2025): descarga, parseo del formato pipe del CNE y armado de las bases
   _tidy_ por mesa con su jerarquía `provincia → cantón → parroquia → zona → junta`.
2. **Validación del método** para Ecuador (`backtest/`): proyectar 2023 desde 2019
   con órdenes de carga simulados (aleatorio/sesgado/adverso) y calibrar los márgenes
   de error por tramo de % escrutado.
3. **Adquisición en vivo** (`vivo/`): espejo incremental de la share de **Azure Files**
   donde el CNE publica resultados, en lugar de scraping.
4. **Proyección** (`modelo/`): swing por **partido/movimiento** con el modelo
   *logit-swing jerárquico* (encogimiento por nivel geográfico), para prefectos,
   alcaldes y concejales (estos últimos con asignación **D'Hondt**).
5. **Detección de anomalías** (`forense/`): tests de **Walter Mebane** (dígitos 2BL/
   C05s/P05s, participación y relación participación-voto, modelo de **mezclas
   finitas**) → score por mesa priorizado para fiscalización.
6. **Dashboard** (`web/`): sitio estático (GitHub Pages) con proyección vs. conteo
   crudo por provincia/cantón.

Los cuatro frentes de trabajo y las herramientas a desarrollar están en
**`docs/PLAN.md`**. Los hallazgos de datos están en **`docs/FINDINGS.md`** y el método
forense en **`docs/FORENSE.md`**.

---

## Estado

En construcción. La conversión desde el repositorio de Brasil está en la **Fase 0**
(limpieza) — ver `docs/PLAN.md`.

## Créditos

Trabajo realizado por **Rodrigo Quiroga** en colaboración con el
**Dr. Roberto Etchenique**.

La metodología de proyección (swing uniforme y *logit-swing* jerárquico) proviene del
trabajo de **Daniel Schteingart (El Atlas / Cenital)** para Brasil.

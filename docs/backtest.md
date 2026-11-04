# Plan — Backtest exhaustivo de métodos de proyección (local 2019 → 2023)

> Estado: **planificado** (no implementado). Objetivo: elegir el método y la unidad de
> proyección para las seccionales 2026 comparando, sobre 2019→2023, el swing jerárquico
> (varias combinaciones de niveles), v2/v4 y v1.

## 1. Objetivo

Predecir **prefecto (dignidad 2)** y **alcalde (dignidad 4) 2023** desde 2019 y encontrar
variantes del **swing jerárquico** (combinando niveles) y de **v2/v4** que **superen a v1
(unidad zona)** en error de composición y acierto de ganador por territorio, a **10% y 20%**
de escrutado, sin degradar 30–50%.

## 2. Datos y estado

- **2019 por junta** (crawl del portal): d2 **35.842/36.049 (99,43%)**; d4 **~100%** (el >100%
  es por claves duplicadas en los `.done` de los workers → deduplicar). Sin procesos activos.
- **2023 seccional por junta**: `gaona_2023_seccional_d11_prefecto_junta.csv`,
  `_d13_alcalde_junta.csv` (formato Gaona).
- **Orden de carga**: `backtest/orden_junta_2021.csv` (minuto medio por junta en 2021),
  extrapolado a 2023 (por zona).
- **Distributivos** 2019/2023/2025/2027 en `raw/` (para mapear junta → recinto físico si se
  agrega a zona).

## 3. Decisiones tomadas

- **3 esquemas de bloque**: (a) familias, (b) 2 bloques, (c) 3 bloques + residual.
- **Una sola corrida** con el orden realista 2021→2023 (sin barrido de semillas).
- **LOCAL/OTRO = residual aparte** en el esquema de 3 bloques (categorías: correísmo,
  izquierda, derecha, residual).
- Generalizar `Proyeccion.Proyector` a **N niveles** (criterio de implementación).
- Secuencia: primero cerrar descargas; luego implementar el backtest.

## 4. Fase 0 — Cierre de descargas

1. Unir y **deduplicar** `gaona2019_junta_d2*` y `_d4*` por clave
   `prov-cant-parr-zona-junta-sexo`; regenerar Gaona consolidado.
2. Verificar los **207 faltantes de d2**: si son juntas sin filas parseables (vacías/error),
   documentar y excluir.
3. Reportar cobertura: votos 2019 prefecto/alcalde vs oficial (~8,09M / ~9,01M) y nº de juntas.
4. (Opcional) mapear junta → recinto físico con distributivos para agregar a zona.

## 5. Homologación de bloques

**Año-específica** (lista 35 = AP-2019 vs MOVER-2023; lista 20 = DSI-2019 vs MF-2023).

- **Familias**: `datos.familias.familia`.
  - 2019: nombre de partido/alianza → lista vía `organizaciones politicas 2019.sav`
    (+ reglas: "LISTAS X", cabeza de alianza) → familia.
  - 2023: `normalizar_lista(cod_org_pol)` → familia.
- **2 bloques**: correísmo (2019: FCS 5, AP 35; 2023: RC 5) vs resto.
- **3 bloques + residual**:
  - correísmo: FCS/AP (2019), RC (2023).
  - izquierda: MUPP(18), ID(12), UP(2), PSE(17), DSI(20-2019)…
  - derecha: PSC(6), CREO(21), SUMA(23), PAE(7), UE(19), MC(51), PSP(3), Avanza(8),
    PID(4), Madera(75)…
  - **residual**: LOCAL/OTRO/no homologado.
- Reportar **cobertura** por esquema (% votos mapeados vs residual) y top no mapeados.

## 6. Cambios de código

1. **`proyeccion.Proyector` → N niveles**:
   - `jer[k]` de longitud arbitraria; `ks_niv` (lista de k por nivel, default 2/4/6/6);
     retrocompatible con 4 niveles.
2. **`backtest/variantes_swing.py`** (nuevo):
   - carga matrices 2019/2023 por unidad (junta/zona) y esquema de bloque;
   - construye `jer` y `terr_of` por variante;
   - orden 2021, `min_votos`, peso por votos;
   - corre métodos, calcula métricas y escribe CSV/pivotes.

## 7. Grilla de variantes

- **Jerárquico, unidad zona**: N–P–Pa · N–P–C–Pa (actual) · N–P–C–Pa–Z · N–P–C–Z ·
  N–P–C · N–P–Z.
- **Jerárquico, unidad junta**: P–C–Pa–Z y subconjuntos (sin cantón, sin parroquia, sin zona).
- **v2** nacional; **v4** territorial en provincia / cantón / parroquia / zona.
- **v1** cascadas: `zona→parroquia→cantón→provincia`, `zona→cantón→provincia`,
  `zona→provincia`.
- **k**: barrido corto (1/2/4/8) solo para las 2–3 mejores combinaciones de niveles.

## 8. Protocolo de evaluación

- Foco **10% y 20%** (curva 2–50% para contexto); **prefecto** y **alcalde**; los 3 esquemas
  de bloque.
- `min_votos ∈ {0,100,200}`; juntas chicas atenuadas.
- Métricas: err composición nacional; acc ganador (provincia/cantón); top-2; error de margen.
- Baseline a batir: **v1@zona** a 10% y 20%.

## 9. Salidas

- `D:\ecuador2026_data\backtest\variantes_swing.csv` (long).
- Pivotes 10%/20% por dignidad y esquema.
- Resumen “mejores variantes vs v1” + **nota de sensibilidad** entre esquemas (asignación
  imperfecta de alianzas).

## 10. Riesgos

- Homologación 2019 de alianzas/movimientos locales → mitigado con 3 esquemas + cobertura.
- Numeración de juntas 2019↔2023 no idéntica → usar intersección; zona como unidad robusta.
- `k` sin calibrar → barrido acotado.

## 11. Criterio de éxito

Una variante que, a **10% y 20%**, tenga **menor err** y **≥ acc** que **v1@zona** en
prefecto **y** alcalde, de forma consistente en los 3 esquemas de bloque (o explicable por la
homologación).

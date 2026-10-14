# Proyecto — Proyección y auditoría de las Seccionales Ecuador 2026

**Objetivo.** Proyectar el resultado de las elecciones seccionales del **29 de noviembre
de 2026** (23 prefecturas, 222 alcaldías, concejalías y juntas parroquiales si es posible) a partir del **escrutinio parcial** a nivel de mesa, y detectar **mesas anómalas** para orientar la fiscalización. El sistema es reproducible y auditable e incluye un dashboard html que permitirá seguir el escrutinio y proyecciones en tiempo real. Incluye también un análisis post-elección de inferencia ecológica, para analizar la transferencia de votos entre fuerzas para las elecciones presidenciales 2021->2025 y también las elecciones seccionales 2019->2023->2026. 

---

## Etapas

**1. Datos históricos y reconstrucción de elecciones pasadas.**
Construir una base _tidy_ por mesa/junta de las elecciones relevantes (seccionales 2019 y 2023; generales 2021 y 2025) con su jerarquía geográfica y el padrón por parroquia. *Entregables:* base de resultados por unidad, catálogos estandarizados, padrón por año, documentación del formato de datos del CNE.

**2. Adquisición de datos en vivo.**
Capturar el escrutinio 2026 conforme se publica (API del CNE y/o Azure Files), guardando snapshots con marca de tiempo propia y respuesta cruda. *Entregables:* capturador configurable con reintentos, registro de versiones/series, y procedimiento de respaldo.

**3. Modelos de proyección.**
Estimar el resultado final por dignidad combinando lo escrutado con lo que falta, mediante métodos de proyección por vecindad geográfica y swing jerárquico por partido/familia. *Entregables:* motor de proyección multi-dignidad, definición de bloques/familias de partidos, y salida de proyección (nacional, provincial y cantonal) con bandas de error.

**4. Validación (backtest).**
Medir y comparar el desempeño de los métodos proyectando una elección con datos de una anterior, bajo distintos órdenes de carga y de % escrutado. *Entregables:* tablero comparativo de métodos por tipo de elección, y calibración de los márgenes de error por % escrutado.

**5. Auditoría forense (mesas a fiscalizar).**
Aplicar tests de anomalías por mesa (dígitos, participación, relación participación–voto y modelos de mezclas) y combinarlos en un score de priorización. *Entregables:* ranking priorizado de mesas con el detalle de cada señal, validación por simulación (detección y falsos positivos), y mapas por zona.

**6. Inferencia ecológica (migración de votos).**
Estimar matrices de transición de voto entre elecciones por unidad, incluyendo no votantes. *Entregables:* matrices de transición con intervalos, visualizaciones (heatmap y Sankey) e informe por par de elecciones.

**7. Dashboard y publicación.**
Publicar resultados y proyecciones en un tablero público actualizado durante el escrutinio. *Entregables:* sitio estático con mapas y pestañas (prefecturas; detalle por prefectura con evolución del escrutinio; alcaldías por prefectura), contrato de datos y publicación automática.

---

## Resultados finales

- Base de datos electoral reproducible (histórico + vivo) por mesa/parroquia.
- Sistema de proyección en vivo por dignidad, con márgenes calibrados.
- Informe de validación del método.
- Herramienta de priorización de mesas para fiscalización.
- Inferencia ecológica de la migración del voto entre elecciones.
- Dashboard público durante la jornada electoral.
- Documentación metodológica y de datos.

*Trabajo de Rodrigo Quiroga y Roberto Etchenique.*

---

## Calendario (hacia el 29-nov-2026)

Hoy: 14-oct-2026 · Elección: **dom 29-nov-2026** · Candidatos definitivos: **9-nov** ·
Campaña: 12–26-nov · Voto de privados de libertad: 26-nov.

| Semana | Fechas | Etapa(s) | Hito / objetivo listo |
|---|---|---|---|
| S1 | 13–19 oct | 1 | Base histórica _tidy_ por mesa/parroquia y padrón; formatos documentados |
| S2 | 20–26 oct | 3, 4 | Modelos de proyección definidos; backtest y elección de método por dignidad |
| S3 | 27 oct–2 nov | 2 | Adquisición en vivo (API CNE y Azure) operativa; pruebas de conectividad y espejo |
| S4 | 3–9 nov | 5, 6 | Forense (score de mesas) e inferencia ecológica listos; candidatos definitivos (9-nov) |
| S5 | 10–16 nov | 7 | Pipeline end-to-end y dashboard con datos simulados; ensayo general |
| S6 | 17–23 nov | 2, 4, 7 | Pruebas de carga y redundancia; bandas calibradas; congelado de versiones |
| S7 | 24–28 nov | — | Simulacro final, checklist del día previo, credenciales y monitoreo (26-nov PPL) |
| Día | 29 nov | — | Operación del escrutinio en vivo (proyección + forense + dashboard) |

---

## Pruebas previas (Azure e infraestructura)

Regla general: **dos canales de datos independientes** (Azure Files y API del CNE), con
monitoreo y **conmutación automática** si uno falla.

**Azure Files (canal primario)**
- **Autenticación:** validar la SAS/credenciales 2026 (vigencia, permisos de solo lectura);
  listar la share y una subcarpeta.
- **Espejo incremental:** que baje solo lo nuevo/cambiado (por ETag/tamaño), reanudable,
  con registro `(ruta, hora, etag, bytes)`.
- **Cadencia y latencia:** medir cada cuánto se publican/actualizan los archivos y cuánto
  tarda la bajada completa; comparar con el portal.
- **Formato/schema:** parsear un archivo real y mapear sus columnas a nuestra base _tidy_.
- **Fallos controlados:** SAS vencida, throttling (429/5xx), archivo parcial/en escritura y
  corte de red → reintentos con retroceso y fallback al otro canal.
- **Volumen/almacenamiento:** espacio en disco y tiempo de sincronización creciente.

**API del CNE (canal de respaldo)**
- Probar los adaptadores (`post2021`/`certero`) contra el **simulacro** del CNE si se
  publica, o contra el portal de la elección anterior mientras esté disponible.
- Verificar el `corte` (timestamp del servidor) y su uso para ordenar la carga.

**Pipeline y end-to-end**
- **Reproducción (replay):** correr el ciclo completo (captura → normalización →
  proyección → publicación → dashboard) alimentado con los datos de 2025.
- **Integridad e idempotencia:** reejecutar sin duplicar ni perder datos; versionado.
- **Reloj:** sincronización de hora local vs hora del servidor.

**Dashboard / publicación**
- Validar el contrato `datos_web.json`, el *cache-busting* y la **actualización automática**
  (~60 s) con datos frescos.
- Verificar mapas (GeoJSON de provincias y cantones) y estados (sin datos / pocos datos /
  en vivo / final).

**Día previo (28-nov) — checklist de operación**
- Credenciales vigentes y probadas; espacio en disco; procesos y logs; monitoreo activo.
- Canales Azure y API verificados; procedimiento de conmutación documentado; respaldo local.

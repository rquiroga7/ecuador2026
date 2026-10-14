# Dashboard — Diseño (a implementar)

Tablero público de proyección del escrutinio de las **Seccionales Ecuador 2026**
(29-nov-2026). Sitio estático (GitHub Pages) que lee un `datos_web.json` publicado en
la rama `data` (o el endpoint sin caché del `worker/`). Reutiliza el patrón del
`index.html` de Brasil (Chart.js) y agrega **mapas** (Leaflet + GeoJSON).

Método principal: **v1 (relleno jerárquico cantón→provincia→nación)** — el que mejor
rindió en lo local. Se podrá sumar el **swing jerárquico** cuando mejoren los datos de
partidos/familias (ver `docs/FINDINGS.md` §10-§11).

---

## 1. Pestañas

### Pestaña 1 — Prefecturas (mapa + tablero de las 23)

**Objetivo:** ver de un vistazo la proyección de las 23 prefecturas.

- **Mapa coroplético de provincias**: color por **prefecto/a proyectado/a** (o por
  partido/familia ganadora); intensidad por **margen proyectado**. Al pasar el mouse:
  tooltip con provincia, ganador proyectado, %, margen ± banda, y % escrutado.
- **Grilla de 23 tarjetas** (una por prefectura): ganador proyectado, candidatos top-2 con
  %, barras horizontales, banda de error, y mini-indicador de método (v1 / swing).
- **Cabecera**: hora de actualización, % escrutado nacional, fuentes.
- Orden de tarjetas: por electores habilitados (desc) o alfabético (toggle).

### Pestaña 2 — Detalle de una prefectura (evolución)

**Objetivo:** seguir cómo evoluciona el conteo y la proyección al avanzar el escrutinio.

- **Selector de prefectura** (dropdown).
- **Gráfico de líneas** (eje x = % escrutado): por candidato,
  - conteo **crudo** (líneas finas),
  - **proyección v1** (líneas gruesas) que converge al valor final,
  - opcional: banda p5–p95.
- **Panel de estado actual**: tabla de candidatos (votos contados, %, proyectado %, banda),
  % escrutado de la provincia, hora del último dato.
- **Franja inferior**: mini-curva de carga (actas/juntas procesadas por hora) y % de juntas
  escrutadas.

### Pestaña 3 — Alcaldías (por prefectura)

**Objetivo:** ver las 222 alcaldías agrupadas por provincia.

- **Dropdown de prefectura** arriba.
- **Mapa de cantones** de esa provincia, color por **alcalde/sa proyectado/a**.
- **Grilla de cantones**: tarjetas con ganador proyectado, top-2, %, margen, % escrutado.
- Orden por electores; buscador.

---

## 2. Contrato de datos (`datos_web.json`)

Un objeto con un bloque por **dignidad** (`prefecto`, `alcalde`) y el detalle territorial.

```jsonc
{
  "actualizado": "2026-11-29 18:45:12",
  "eleccion": "Seccionales Ecuador 2026",
  "metodo_principal": "v1",
  "escrutado_pct": 37.5,

  "prefecto": {
    "nacional": { "escrutado": 37.5, "candidatos": [ ... ] },
    "territorios": [
      {
        "cod": "01", "nombre": "Azuay",
        "escrutado": 41.2,
        "electores_habilitados": 620000,
        "candidatos": [
          {"cod":"...", "nombre":"...", "partido":"...", "familia":"RC",
           "votos_crudo": 12000, "pct_crudo": 30.1,
           "votos_proy": 31000, "pct_proy": 28.4, "p5": 26.0, "p95": 31.0}
        ],
        "ganador_proy": "RC", "margen_proy": 4.2
      }
    ],
    "serie": [ { "t":"18:00", "pct": 5.0, "candidatos": {...} } ]
  },

  "alcalde": { "territorios": [ { "cod":"01-260", "provincia":"01", ... } ] },

  "cargas": { "serie": [ {"t":"18:00","actas_pct":12.0} ] }
}
```

Notas:
- `territorios` de **prefecto**: 23 (provincias). De **alcalde**: 222 (cantones), con
  `provincia` para agrupar.
- Métodos alternativos (si están) van en bloques por método: `"v1"`, `"swing"`; la UI usa
  `metodo_principal` salvo que el usuario elija otro.
- La **banda** (p5–p95) se calibra en el backtest (`docs/FINDINGS.md` §10).

## 3. Fuentes geo

- Provincias (prefecturas): GeoJSON de Ecuador (23 provincias + Galápagos).
- Cantones (alcaldías): GeoJSON de cantones, con `cod_canton` para unir.
- Candidatos de mapas listos: `RickyTB/elecciones-2021` (`public/src/data/ecuador_*.json`);
  alternativa: `digital-guard/preserv-EC` o GeoJSON del INEC.
- Códigos: provincia `zfill(2)`, cantón `zfill(3)`; la unión con el JSON es por código.

## 4. Estados de la UI

- **Pre-elección / sin datos**: mapas en gris + mensaje "esperando escrutinio".
- **Pocos datos** (< umbral, p. ej. 2%): mostrar **conteo crudo** y aviso de alta incertidumbre.
- **En vivo**: proyección + bandas; actualización automática cada ~60 s (cache-busting).
- **Final** (100%): mostrar resultado oficial.

## 5. Reutilización y tecnología

- Base del dashboard: `index.html` (tabs, tarjetas, Chart.js). Se reescribe el contrato.
- Mapas: **Leaflet** + GeoJSON local (sin tiles de terceros para no depender de red).
- Publicación: `publicar_rodri.py` (rama `data`) o `worker/` (endpoint sin caché).
- Sin build step; todo estático.

## 6. Pendientes / TODO

- [ ] Elegir/curar los GeoJSON (provincias y cantones) y codificarlos con los códigos CNE.
- [ ] Definir el JSON final por dignidad (prefecto/alcalde) que emitirá el pipeline.
- [ ] Colores por familia/partido (paleta estable, ver `docs/FINDINGS.md` §10.3-bis).
- [ ] Calibrar bandas p5–p95 de v1 por % escrutado (backtest ya disponible).
- [ ] Concejales (opcional, fase 2): barra de composición, sin mapa.
- [ ] Accesibilidad y modo oscuro (heredados de `index.html`).

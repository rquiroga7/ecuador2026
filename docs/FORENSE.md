# Método de detección de anomalías por mesa (fiscalización)

Objetivo: producir, para cada **mesa (junta receptora del voto)** y cada dignidad, un
**puntaje de anomalía** que priorice dónde la fiscalización debe mirar primero el día
del escrutinio. Está basado en la escuela de *election forensics* de **Walter Mebane**
(University of Michigan) y colaboradores. Ver también `docs/FINDINGS.md` §6.

> Principio rector: ninguna de estas pruebas **prueba fraude**. Señalan mesas
> *atípicas* que merecen revisión (conteo manual, cotejo con el acta, observación).
> Deben combinarse entre sí y con evidencia contextual (denuncias, observadores).

---

## 0. Unidad de análisis y datos

- Unidad: **junta** (mesa). Agregar los dos registros de sexo (F+M) del dump del CNE.
- Por mesa y dignidad se necesitan:
  - `N` — electores habilitados (padrón por junta).
  - `V` — votos emitidos (sufragantes).
  - `W` — votos del **ganador/leader** (candidato o partido más votado en el ámbito).
  - `O = V − W` — votos de la oposición.
  - `A = N − V` — abstención.
  - `v_j` — votos de cada partido `j`.
- Derivadas: participación `t = V/N`, share del leader `w = W/N`,
  share del partido `s_j = v_j/V`.

Para la validación espacial se usa la jerarquía `provincia → cantón → parroquia → zona`
y la comparación con la **misma mesa en 2019 y 2023**.

---

## 1. Tests de dígitos (sobre conteos por mesa)

Estadísticas (Election Forensics Toolkit; valores esperados "sin anomalía"):

| Test | Definición | Esperado | Interpretación de desvíos |
|---|---|---:|---|
| **2BL** | media del 2.º dígito significativo de los conteos | 4.187 | < 4.187 en partidos grandes → coerción/acarreo; > 4.187 → voto estratégico |
| **LastC** | media del último dígito | 4.5 | desvío = patrón artificial de redondeo |
| **C05s** | media del indicador "último dígito ∈ {0,5}" en conteos | 0.2 | exceso = fabricación/redondeo humano |
| **P05s** | ídem, sobre **porcentajes** redondeados | 0.2 | exceso difícil de explicar benignamente |
| **Skew** | asimetría de la distribución de conteos | ≈0 | — |
| **Kurt** | curtosis | ≈3 | — |
| **DipT** | p-valor del test de unimodalidad de Hartigan | >0.05 | multimodalidad ("spikes") |

**Caveat (Mebane 2013).** El 2BL se rechaza con frecuencia en elecciones limpias por
voto estratégico, movilización y desbalance distrital. No usar como diagnóstico
aislado. **No** aplicar tests de dígitos a nivel de máquina (mecanismo REDWL); a nivel
de junta sí es razonable.

Implementación: `forense/digitos.py`. Bootstrap no-paramétrico (1000 réplicas) para
intervalos de confianza; **FDR** (Benjamini-Hochberg) al evaluar miles de mesas.

---

## 2. Participación y relación participación–voto

- **Distribución de la participación** `t` por mesa: detección de multimodalidad y de
  picos en valores "redondos" (`P05s` sobre `t` y sobre `w`).
- **Sobyanin–Sukhovolsky**: relación entre `t` (eje x) y `s_j` (share del partido,
  eje y). En elecciones limpias suele ser plana o con pendiente suave; una pendiente
  fuerte y positiva para el oficialismo y negativa para la oposición es la "firma"
  clásica de acarreo/traspaso.
- **Regresión no paramétrica** (p. ej. *smoothing spline*/kernel) de `s_j` y de la
  media del 2.º dígito contra `t`; intervalos donde `j̄ > 4.187` sugieren *vote
  switching*, y donde `j̄ < 4.187` en partidos grandes sugiere coerción.

Implementación: `forense/participacion.py`.

---

## 3. Modelo de mezclas finitas (`eforensics`)

Modelo positivo de fraude (Klimek et al. 2012 → Mebane 2016; implementación bayesiana
Ferrari, McAlister & Mebane 2018). Entrada por mesa: `N`, `V`, `W`, `A`.

Tres componentes de mezcla, con probabilidades `π1` (sin fraude), `π2` (incremental),
`π3` (extremo); el fraude **beneficia al leader** y opera por dos mecanismos:

- **manufactura**: votos inventados a partir de no votantes,
- **robo**: votos transferidos desde la oposición.

Parámetros globales: `α` (manufacturar vs. robar), `τ`/`σ_τ` (participación verdadera),
`ν`/`σ_ν` (share verdadero del leader), `θ`. Por observación:
`f0i, fii, fei` (probabilidades) y las **magnitudes** de votos manufacturados/robados.

Salidas:
- probabilidad de fraude por mesa y clasificación `Zi ∈ {1 sin, 2 incremental, 3 extremo}`;
- número estimado de votos fraudulentos por mesa y totales (`Fw`, `Ft`);
- test de razón de verosimilitud entre el modelo de 3 componentes y el de 1.

Herramientas:
- R: paquete `eforensics` (<https://github.com/UMeforensics/eforensics_public>, MCMC/JAGS)
  y `EFToolkit` (<https://github.com/kkalininMI/EFToolkit>).
- Alternativa: portar el EM de máxima verosimilitud (Mebane 2016) a Python en
  `forense/mezclas.py`.

**Advertencia:** el voto estratégico y las coaliciones también producen multimodalidad.
Los parámetros ayudan a discriminar (p. ej. `ρM0`/`ρS0` negativos con
`δM0 ≈ δS0 ≈ 0` sugieren estrategia y no "malas acciones"), pero la interpretación
requiere contexto.

---

## 4. Modelos robustos con detección de *outliers*

- `Wand, Shotts, Sekhon, Mebane, Herron & Brady (2001)`; `Mebane & Sekhon (2004)`;
  `Mebane & Herron (2005)`: multinomial sobre-parametrizado (EI/MNP) con detección de
  unidades atípicas.
- Uso aquí: comparar el patrón de transferencia de votos entre mesas normales y
  atípicas dentro del mismo cantón/provincia.

---

## 5. Score compuesto por mesa (nuestro diseño)

Combinar las señales en un único puntaje priorizado, por dignidad:

1. **Estandarizar** cada indicador dentro de su estrato (cantón o provincia) para no
   castigar diferencias legítimas de tamaño/preferencias: `z = (x − mediana)/MAD`.
2. **Indicadores base**:
   - dígitos: `|2BL − 4.187|`, `P05s`, `C05s`, `DipT` (multimodalidad);
   - participación: `P05s(t)`, pendiente Sobyanin, participación extrema (> 99%);
   - mezclas: `π2 + π3` y magnitud de votos fraudulentos estimada;
   - **salto temporal**: `|swing_2026 − swing_esperado_por_pares|` (outlier respecto de
     mesas vecinas y de la propia mesa en 2023).
3. **Consistencia cruzada**: una mesa es más creíble como anomalía si **varias**
   señales independientes coinciden (dígitos + participación + salto temporal).
4. **Score final**: combinación (p. ej. media de z-scores recortada a [0, k·MAD],
   o percentil del producto de rangos). Control de **FDR** sobre el conjunto de mesas.
5. **Salida operativa**:
   - listado priorizado de mesas (`provincia, cantón, parroquia, zona, junta`) con el
     detalle de cada señal y el partido/dignidad afectados;
   - **mapas** de calor del score por zona/parroquia;
   - para cada mesa señalada: acta asociada (`INDICE.xls` → `NOM_ARCHIVO`) y el enlace
     al acta del portal para revisión manual.

Implementación: `forense/ranking.py`.

---

## 6. Integración con la proyección

- Marcar en la proyección si el **cambio de resultado** se apoya en mesas con score
  alto (mesas "bisagra" anómalas).
- Repetir la proyección **excluyendo** las mesas señaladas y reportar la diferencia:
  sirve como análisis de sensibilidad ("¿el ganador cambia si se caen las mesas
  sospechosas?").
- Este contraste es el producto más útil para el equipo de fiscalización: dónde mirar
  y cuánto depende el resultado de esas mesas.

---

## 7. Validación

- Correr el pipeline sobre **2019 y 2023** (sin fraude conocido documentado) para
  medir la **tasa de falsos positivos** esperada y fijar umbrales.
- Si hay denuncias o recuentos oficiales en elecciones pasadas, usarlos como etiqueta
  (p. ej. casos de la 2023).
- Reportar siempre el score como **priorización**, nunca como veredicto.

---

## Referencias

Todas las obras de Mebane están en <https://websites.umich.edu/~wmebane/>. Ver la
lista completa y enlaces en `docs/FINDINGS.md` §6.5.

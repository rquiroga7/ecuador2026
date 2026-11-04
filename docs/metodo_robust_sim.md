# Método de proyección `robust_sim`

Documento de referencia del modelo **`robust_sim`** (mejor variante de `est_B` en los
backtests). Es un estimador único que combina, para cada unidad no escrutada, una
proyección **base+swing robusta** con un **promedio de pares por similitud**.

## 1. Unidades y bloques

- **Unidad** = zona electoral (recinto). Agregable a parroquia/cantón/provincia/nación.
- **Bloques** = agrupación de partidos (p. ej. 4 bloques: correísmo / derecha / izquierda /
  otros; o familias). El método es agnóstico a `K` (nº de bloques).
- **Referencia** = elección del mismo tipo del ciclo anterior (2019 para 2023; 2023 para
  2026), con shares por unidad `s_base[i, k] = base_votos[i,k] / base_validos[i]`.
- **Escutinio parcial** = primeras `f` unidades (por orden de carga) con votos observados
  `obs[i, k]`; `counted[i] = (Σ_k obs[i,k] > 0)`.

## 2. Niveles jerárquicos

Para cada unidad `i` se definen sus grupos de pertenencia, de fino a grueso:

```
parroquia → cantón → provincia → nacional
```

Cada nivel `ℓ` tiene un factor de encogimiento `k_ℓ` (por defecto `k=(2,4,8,16)`).

## 3. Componente 1 — base + swing robusto

En cada nivel `ℓ` y bloque `k`:

1. **Swing observado por grupo** (`G`): se calcula el swing **unitario** de cada unidad
   contada `j` dentro del grupo,
   ```
   d_j,k = s_obs[j,k] − s_base[j,k]        (s_obs = obs / Σ obs)
   ```
   y se toma la **mediana** entre las unidades contadas del grupo:
   ```
   d_ℓ(G,k) = median_{j∈G, counted} d_j,k
   ```
   (la mediana es **robusta** a outliers y unidades chicas; alternativa no robusta = media
   ponderada por votos).
2. **Encogimiento** hacia 0 según los votos contados del grupo `T_ℓ(G)`:
   ```
   d*_ℓ(G,k) = d_ℓ(G,k) · T_ℓ(G) / (T_ℓ(G) + k_ℓ)
   ```
   (con pocos votos contados el swing se encoge a 0; con muchos se confía en él).
3. **Mezcla de niveles** (cada nivel pesa según datos):
   ```
   w_ℓ(i) = T_ℓ(G_ℓ(i)) / (T_ℓ(G_ℓ(i)) + k_ℓ)
   Δ[i,k] = Σ_ℓ w_ℓ(i) · d*_ℓ(G_ℓ(i),k)  /  Σ_ℓ w_ℓ(i)
   ```
4. **Share proyectado** de la unidad:
   ```
   s_sw[i,:] = normalize( max(0, s_base[i,:] + Δ[i,:]) )
   ```
   El recorte a 0 evita shares negativas (p. ej. un partido que desaparece).

## 4. Componente 2 — pares por similitud

Para cada unidad no escrutada `i`:

1. Buscar el **nivel más fino** (parroquia → cantón → provincia → nacional) con al menos
   3 unidades contadas (`peers`).
2. Pesar cada par `j` por **similitud de composición base**:
   ```
   dist_ij = || s_base[i,:] − s_base[j,:] ||²
   h       = mediana{ dist_ij }
   w_ij    = exp(−dist_ij / h)
   ```
3. Share proyectado:
   ```
   s_peer[i,:] = Σ_j w_ij · s_obs[j,:] / Σ_j w_ij
   ```
   Es decir, se "presta" información de zonas con **composición política parecida en la
   referencia**, no solo de vecinas geográficas.

## 5. Mezcla final

```
s[i,:] = λ · s_sw[i,:] + (1 − λ) · s_peer[i,:]      (normalizado y recortado a ≥0)
```

- `λ` = peso de base+swing. Calibrado: **prefecto λ=0,75**, **alcalde λ=0,5**, **nacional
  λ=0,75**. (`ks` casi no influye; usar `(2,4,8,16)`.)

## 6. Votos proyectados y agregación

- Unidades **contadas**: se respetan sus votos observados.
- Unidades **no contadas**:
  ```
  proj[i,:] = base_validos[i] · s[i,:]
  ```
  (se usa el tamaño de la referencia como proxy de votos esperados).
- Se agregan a la unidad territorial deseada (provincia para prefecto, cantón para alcalde),
  se calculan shares y ganador/margen.

## 7. Pseudocódigo

```
entrada: base (unidad×bloque), obs, validos_base, niveles=[parr,cant,prov,nac], k, λ
counted = (Σ obs > 0)

# componente base+swing (mediana)
for nivel in niveles:
    para cada grupo G:
        T = votos contados en G
        d = mediana_{j∈G counted} (s_obs[j] − s_base[j])
        d = d · T/(T + k_nivel)
    Δ[i] = Σ_nivel w_nivel(i)·d_nivel(G_nivel(i)) / Σ_nivel w_nivel(i)
s_sw = normalize(clip(s_base + Δ, 0))

# componente similitud
for i no contada:
    peers = unidades contadas del primer nivel con ≥3
    w = exp(−||s_base[i]−s_base[j]||² / mediana_dist)
    s_peer[i] = Σ w·s_obs[j] / Σ w

# mezcla
s = normalize(clip(λ·s_sw + (1−λ)·s_peer, 0))
proj[counted] = obs[counted]
proj[not counted] = validos_base · s
```

## 8. Por qué funciona / validación

- **Mediana** → robusta a outliers y grupos chicos.
- **Similitud** → maneja heterogeneidad (no asume homogeneidad geográfica).
- **Ancla a la base** → conserva el patrón espacial de la referencia, clave para el ranking.
- Backtest local 2019→2023 (4 bloques, error promedio provincial correísmo+derecha):
  - prefecto λ=0,75: err 5,9/5,5/4,6 y **acc 95,7/95,7/100%** (10/15/20%).
  - alcalde λ=0,5: err 4,9/3,8/3,2 y acc 82/83/86%.
- Validación **presidencial 2021→2023** (misma arena): error provincial ~2 pts (vs ~5,5 de v1)
  y acc 87–92%. Generaliza sin sobreajuste.

## 9. Parámetros y límites

- `λ`, `k`, `nivel_mín_peers=3`, `clip=True`, `robust="median"`, `peer="sim"`.
- Requiere una **referencia homologada** por bloque (mapeo partido/alianza) y un **orden de
  carga** (timestamps) para simular el escrutinio parcial.
- La similitud depende de la calidad del share base; si el mapeo de partidos es imperfecto,
  los pares pueden elegirse mal.
- La mediana pierde algo de eficiencia frente a la media en provincias grandes.

"""Proyección del resultado final a partir del escrutinio parcial (modelo de "swing" contra 2022).

Idea: el conteo parcial engaña porque las urnas no llegan en orden aleatorio (el Nordeste suele
entrar más tarde). En cada municipio ya contado se mide cuánto cambió el voto respecto de la
elección de referencia (2022, misma vuelta); ese cambio se estima para los municipios que faltan
y se suma todo, ponderando por los votos que se esperan en cada uno.

  1. Bloques: cada candidato nuevo se asocia a uno de la elección de referencia
     (Lula <- Lula, Flávio <- Jair Bolsonaro, el resto <- el resto).
  2. En cada municipio con datos: cambio = logit(% hoy) - logit(% en 2022), por bloque
     (en log-odds y no en puntos, para no proyectar más de 100% en los bastiones).
  3. Cambio esperado donde falta: regresión ponderada (según el % de 2022 y el tamaño del
     municipio) + efectos de región, estado, región intermedia y región inmediata del IBGE,
     cada uno "encogido" hacia el nivel de arriba cuando hay pocos municipios contados.
  4. Votos esperados de cada municipio: los válidos de 2022 ajustados por la participación que
     se va viendo (o, si ya hay buena parte contada, lo contado / % de secciones escrutadas).
  5. Dentro del bloque "resto", el reparto entre candidatos (Caiado, Zema...) sale de la
     composición observada en el mismo estado/región, también encogida hacia el total.

Lo usa vivo.py en cada ciclo y scripts/probar_proyeccion.py para la prueba 2018 -> 2022.
"""
import numpy as np

PARAMS = {
    'tau': 0.15,        # dispersión típica del cambio entre municipios (log-odds)
    'k_reg': 2.0,       # cuántos "municipios equivalentes" hacen falta para confiar a medias en cada nivel
    'k_uf': 4.0,
    'k_int': 6.0,
    'k_ime': 6.0,
    'k_own': 0.15,      # confianza en el propio municipio parcialmente contado: f / (f + k_own)
    'k_comp': 20000.0,  # votos del bloque "resto" para confiar a medias en la composición de un grupo
    'k_turn': 5.0,      # ídem para la participación
    'f_e': 0.3,         # desde qué % contado se confía en lo contado / % para estimar el total
    'n_min': 20,        # votos mínimos para usar un municipio
}


def logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def expit(x):
    return 1.0 / (1.0 + np.exp(-x))


def _grupos(etiquetas):
    u = {x: i for i, x in enumerate(sorted(set(etiquetas)))}
    return np.array([u[x] for x in etiquetas]), len(u)


def _efecto(g, ng, r, w, k):
    """media ponderada de r por grupo, encogida hacia 0 con k 'unidades de peso'"""
    num = np.bincount(g, weights=w * r, minlength=ng)
    den = np.bincount(g, weights=w, minlength=ng)
    return num / (den + k)


class Proyector:
    """unidades: claves (código IBGE como texto, y 'ZZ' para el exterior).
    jer: clave -> (región, uf, región intermedia, región inmediata).
    base_bloques: [U, B] votos de referencia por bloque; base_val: [U] válidos de referencia."""

    def __init__(self, unidades, jer, base_bloques, base_val, params=None):
        self.keys = list(unidades)
        self.idx = {k: i for i, k in enumerate(self.keys)}
        self.U, self.B = base_bloques.shape
        self.p = dict(PARAMS, **(params or {}))
        V = np.asarray(base_val, float)
        self.V = np.maximum(V, 1.0)
        self.LS = logit(base_bloques / self.V[:, None])
        self.lv = np.log(np.maximum(V, 50.0))
        self.niv = [_grupos([str(jer[k][l]) for k in self.keys]) for l in range(4)]
        self.uf = np.array([str(jer[k][1]) for k in self.keys])

    def proyectar(self, obs_votos, obs_f, bloque_de, extra=None):
        """obs_votos: [U, K] votos válidos contados por candidato nuevo (0 donde no hay datos).
        obs_f: [U] fracción de secciones escrutadas (0..1).  bloque_de: [K] bloque de cada candidato.
        extra: [K] votos contados en unidades sin referencia (municipios nuevos), se suman tal cual.
        Devuelve dict con % proyectado y % contado por candidato, y la fracción contada."""
        p = self.p
        O = np.asarray(obs_votos, float)
        f = np.clip(np.asarray(obs_f, float), 0, 1)
        bloque_de = np.asarray(bloque_de)
        K = O.shape[1]
        n = O.sum(1)
        Ob = np.zeros((self.U, self.B))
        for b in range(self.B):
            Ob[:, b] = O[:, bloque_de == b].sum(1)
        vis = (n >= p['n_min']) & (f > 0)
        if vis.sum() < 3:
            return None

        # --- votos esperados por unidad (participación) ---
        okE = vis & (f >= p['f_e'])
        rho = np.zeros(self.U)
        if okE.sum() >= 3:
            r = np.where(okE, np.log(np.maximum(n, 1) / np.maximum(f, 1e-6) / self.V), 0.0)
            w = okE.astype(float)
            mu = (w * r).sum() / w.sum()
            rho[:] = mu
            res = r - mu
            for (g, ng) in self.niv:
                e = _efecto(g, ng, res, w, p['k_turn'])
                rho += e[g]
                res = np.where(okE, res - e[g], 0.0)
        Emod = self.V * np.exp(rho)
        wE = np.clip(f / p['f_e'], 0, 1)
        Eobs = np.where(f > 0, n / np.maximum(f, 1e-6), Emod)
        E = np.maximum(wE * Eobs + (1 - wE) * Emod, n)
        resto = np.where(f >= 0.999, 0.0, np.maximum(E - n, 0))

        # --- cambio (swing) por bloque ---
        Pr = np.zeros((self.U, self.B))
        X = np.column_stack([np.ones(self.U), self.LS, self.lv])  # [1, logit de cada bloque, log tamaño]
        for b in range(self.B):
            s_obs = Ob[:, b] / np.maximum(n, 1)
            y = np.where(vis, logit(s_obs) - self.LS[:, b], 0.0)
            pq = expit(self.LS[:, b]) * (1 - expit(self.LS[:, b]))
            w = np.where(vis, 1.0 / (p['tau'] ** 2 + 1.0 / np.maximum(n * pq, 1.0)), 0.0) / (1 / p['tau'] ** 2)
            # regresión ponderada, con un poco de ridge para que no se dispare con pocos datos
            Xw = X * w[:, None]
            A = X.T @ Xw + np.diag([1e-6] + [2.0] * (X.shape[1] - 1))
            beta = np.linalg.solve(A, Xw.T @ y)
            yhat = X @ beta
            res = np.where(vis, y - yhat, 0.0)
            for nombre, (g, ng) in zip(['k_reg', 'k_uf', 'k_int', 'k_ime'], self.niv):
                e = _efecto(g, ng, res, w, p[nombre])
                yhat = yhat + e[g]
                res = np.where(vis, res - e[g], 0.0)
            own = f / (f + p['k_own'])
            yhat = yhat + np.where(vis, res * own, 0.0)
            Pr[:, b] = expit(self.LS[:, b] + yhat)
        Pr = Pr / Pr.sum(1, keepdims=True)

        # --- reparto dentro de cada bloque (composición) ---
        final = O.copy()
        for b in range(self.B):
            ks = np.where(bloque_de == b)[0]
            if len(ks) == 0:
                continue
            votos_b = resto * Pr[:, b]
            if len(ks) == 1:
                final[:, ks[0]] += votos_b
                continue
            C = O[:, ks]
            tot = C.sum(0)
            comp = np.tile(tot / max(tot.sum(), 1.0), (self.U, 1))
            for (g, ng) in self.niv:
                num = np.stack([np.bincount(g, weights=C[:, j], minlength=ng) for j in range(len(ks))], 1)
                den = num.sum(1)
                comp = (num[g] + p['k_comp'] * comp) / (den[g] + p['k_comp'])[:, None]
            den = C.sum(1)
            comp = (C + p['k_comp'] / 10 * comp) / (den + p['k_comp'] / 10)[:, None]
            final[:, ks] += votos_b[:, None] * comp

        tot_final = final.sum(0)
        tot_obs = O.sum(0)
        if extra is not None:
            tot_final = tot_final + np.asarray(extra, float)
            tot_obs = tot_obs + np.asarray(extra, float)
        return {
            'proy': 100 * tot_final / tot_final.sum(),
            'conteo': 100 * tot_obs / max(tot_obs.sum(), 1),
            'contado': float(n.sum() / max(E.sum(), 1)),        # fracción de los votos esperados ya contada
            'esperados': float(E.sum()),
            'n_mun': int(vis.sum()),
            'n_uf': int(len(set(self.uf[vis]) - {'ZZ'})),   # estados con datos (el exterior no cuenta como estado)
            'final': final,          # [U, K] votos proyectados por unidad y candidato
        }


class ProyeccionEnVivo:
    """Une el modelo con lo que baja vivo.py: referencia 2022 (misma vuelta), jerarquía IBGE y
    márgenes de error calibrados en la prueba 2018 -> 2022 (scripts/probar_proyeccion.py)."""

    MIN_CONTADO = 0.02   # antes de esto no se muestra (muy poca información)
    MIN_UF = 20          # estados con datos

    def __init__(self, turno, raiz):
        import json, os
        txt = open(os.path.join(raiz, 'data', 'elecciones-2022.js'), encoding='utf-8').read()
        ref = None
        for linea in txt.splitlines():
            if linea.startswith(f"window.ELEC['2022-{turno}']"):
                ref = json.loads(linea.split(' = ', 1)[1].rstrip(';'))
        jer = json.load(open(os.path.join(raiz, 'data', 'mun-jerarquia.json'), encoding='utf-8'))
        jer['ZZ'] = ['EXT', 'ZZ', 'ZZ', 'ZZ']
        try:
            self.calib = json.load(open(os.path.join(raiz, 'data', 'proyeccion-calibracion.json'), encoding='utf-8'))[str(turno)]
        except (OSError, KeyError, ValueError):
            self.calib = None
        self.B = 3 if turno == 1 else 2
        blo = [0 if c['n'] == '13' else 1 if c['n'] == '22' else 2 for c in ref['cands']]
        unidades = [k for k in ref['mun'] if k in jer] + (['ZZ'] if 'ZZ' in ref['uf'] else [])
        base = np.zeros((len(unidades), self.B))
        for i, k in enumerate(unidades):
            v = ref['uf']['ZZ']['v'] if k == 'ZZ' else ref['mun'][k][0]
            for j, x in enumerate(v):
                base[i, min(blo[j], self.B - 1)] += x
        self.modelo = Proyector(unidades, jer, base, base.sum(1))
        # para medir el sesgo del conteo (solo municipios: el exterior se cuenta aparte y distorsiona el final)
        es_mun = np.array([k != 'ZZ' for k in unidades], float)
        self.base_lula, self.base_val = base[:, 0] * es_mun, base.sum(1) * es_mun
        self.hist = []

    def banda(self, contado):
        """margen de error (percentil 90 de la prueba) para la fracción de votos ya contada"""
        if not self.calib:
            return 1.5, 3.0
        xs = [c['contado'] for c in self.calib]
        cand = float(np.interp(contado, xs, [c['cand'] for c in self.calib]))
        marg = float(np.interp(contado, xs, [c['margen'] for c in self.calib]))
        # piso prudente: la prueba 2018 -> 2022 no captura todo lo que puede ser distinto en 2026
        return max(cand, 0.1 + 0.3 * (1 - contado)), max(marg, 0.15 + 0.5 * (1 - contado))

    def calcular(self, cands, mun, uf, pct_nac):
        """cands: [(n, nombre, partido)]; mun: ibge -> [votos, val, bn, apt, com, pct]; uf: 'ZZ' -> fila"""
        M = self.modelo
        K = len(cands)
        O = np.zeros((M.U, K)); f = np.zeros(M.U); extra = np.zeros(K)
        for ib, row in mun.items():
            i = M.idx.get(ib)
            if i is None:
                extra += np.asarray(row[0][:K], float)
                continue
            O[i, :len(row[0])] = row[0][:K]
            f[i] = row[5] / 100.0
        zz = uf.get('ZZ')
        if zz and 'ZZ' in M.idx and zz.get('pct', 0) > 0:
            O[M.idx['ZZ'], :len(zz['v'])] = zz['v'][:K]
            f[M.idx['ZZ']] = zz['pct'] / 100.0
        bloque_de = np.array([0 if n == '13' else 1 if n == '22' else 2 for n, _, _ in cands])
        bloque_de = np.minimum(bloque_de, self.B - 1)
        # sesgo del conteo: cómo votó en 2022 (a Lula) lo ya contado y lo que falta contar
        cont = float((f * self.base_val).sum())
        l22c = 100 * float((f * self.base_lula).sum()) / cont if cont else None
        falta = float(((1 - f) * self.base_val).sum())
        # cuando lo que falta es menos del 2% de los votos, su composición es ruido: no se informa
        l22f = 100 * float(((1 - f) * self.base_lula).sum()) / falta if falta > 0.02 * (falta + cont) else None
        r = M.proyectar(O, f, bloque_de, extra)
        if r is None:
            return {'ok': False, 'motivo': 'pocos datos', 'hist': self.hist, 'l22c': l22c, 'l22f': l22f}
        b_cand, b_marg = self.banda(r['contado'])
        proy = [round(float(x), 2) for x in r['proy']]
        bandas = [round(max(0.15, b_cand * float(np.sqrt(p / 100 * (1 - p / 100)) / 0.5)), 2) for p in proy]
        ok = r['contado'] >= self.MIN_CONTADO and r['n_uf'] >= self.MIN_UF
        out = {
            'ok': bool(ok), 'motivo': '' if ok else 'pocos datos',
            'proy': proy, 'banda': bandas, 'banda_margen': round(b_marg, 2),
            'conteo': [round(float(x), 2) for x in r['conteo']],
            'contado': round(r['contado'], 4), 'pct': pct_nac, 'n_mun': r['n_mun'], 'n_uf': r['n_uf'],
            'l22c': None if l22c is None else round(l22c, 2), 'l22f': None if l22f is None else round(l22f, 2),
        }
        if ok and (not self.hist or abs(self.hist[-1]['pct'] - pct_nac) > 1e-9):
            self.hist.append({'pct': pct_nac, 'p': out['proy'], 'b': out['banda'], 'c': out['conteo'], 'l22c': out['l22c'], 'l22f': out['l22f']})
        out['hist'] = self.hist
        return out

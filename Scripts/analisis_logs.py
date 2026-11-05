import re
import sys
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict, namedtuple
from statistics import mean, pstdev

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest

import motor

Entrada = namedtuple('Entrada', ['ts', 'nivel', 'msg', 'plantilla'])

MIN_LINEAS_ANOMALIAS = 20
FRECUENCIA_MAXIMA_ANOMALIA = 0.01
DIMENSIONES_CONTENIDO = 3
MIN_VECES_ANOMALIA = 3
MAX_ANOMALIAS = 15
LINEAS_FINALES = 50

PESO_NIVEL = {'CRITICAL': 5, 'ERROR': 4, 'WARN': 3, 'SIN NIVEL': 2, 'INFO': 1, 'DEBUG': 0}

# Equivalencias de los nombres de nivel más habituales con los niveles canónicos
NIVELES = {
    'trace': 'DEBUG', 'debug': 'DEBUG', 'dbg': 'DEBUG',
    'info': 'INFO', 'information': 'INFO', 'notice': 'INFO', 'log': 'INFO',
    'warn': 'WARN', 'warning': 'WARN',
    'error': 'ERROR', 'err': 'ERROR', 'eror': 'ERROR',
    'crit': 'CRITICAL', 'critical': 'CRITICAL', 'fatal': 'CRITICAL', 'panic': 'CRITICAL',
    'alert': 'CRITICAL', 'emerg': 'CRITICAL', 'emergency': 'CRITICAL'
}

ansi = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
re_logfmt = re.compile(r'\b(?:level|lvl|severity)\s*[=:]\s*"?([A-Za-z]+)', re.IGNORECASE)
re_corchetes = re.compile(r'\[(trace|debug|info|notice|warn|warning|error|crit|critical|alert|emerg|fatal)\]', re.IGNORECASE)
re_mayusculas = re.compile(r'\b(TRACE|DEBUG|INFO|NOTICE|LOG|WARN|WARNING|ERROR|ERR|CRITICAL|CRIT|FATAL|PANIC|ALERT|EMERG)\b')
re_mssql = re.compile(r'\bError: \d+, Severity: (\d+)')
re_http = re.compile(r'"\s(\d{3})\s')

# Sustituciones para reducir cada mensaje a su plantilla (el orden importa)
NORMALIZACIONES = [
    (re.compile(r'^\.?\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|\s?[A-Z]{3,4}\b|\s?[+-]\d{2}:?\d{2})?\s*'), ''),
    (re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'), '<UUID>'),
    (re.compile(r'\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b'), '<IP>'),
    (re.compile(r'\b0x[0-9a-fA-F]+\b|\b(?=[0-9a-fA-F]*\d)[0-9a-fA-F]{12,}\b'), '<HEX>'),
    (re.compile(r'\b\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\b'), '<HORA>'),
    (re.compile(r'\d+(?:[.,]\d+)*'), lambda m: m.group(0) if re_codigo.search(m.string, 0, m.start()) else '<NUM>'),
    (re.compile(r'\s+'), ' '),
]

# Los números que siguen a estas palabras identifican el tipo de error (p. ej. "Error: 18456, Severity: 14"),
# así que se conservan en la plantilla
re_codigo = re.compile(r'\b(?:error|errno|code|status|severity)\s*[:=]?\s*$', re.IGNORECASE)

re_timestamp_motor = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$')
re_timestamp_final = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})\s*$')

def leerTimestamp(ts):
    # El motor antepone a cada línea su marca RFC3339Nano (p.ej. ...17.788436412Z), que fromisoformat
    # no admite completa. Las líneas sin ella son continuaciones de un mensaje de varias líneas.
    if not re_timestamp_motor.match(ts):
        raise ValueError(ts)
    ts = re.sub(r'(\.\d{6})\d+', r'\1', ts).replace('Z', '+00:00')
    return datetime.fromisoformat(ts)

def formatear(dt):
    return dt.strftime('%d/%m/%Y %H:%M:%S')

def detectarNivel(msg):
    if msg.startswith('{'):
        try:
            datos = json.loads(msg)
            for clave in ('level', 'severity', 'lvl', 'loglevel', 'log.level'):
                if isinstance(datos.get(clave), str):
                    return NIVELES.get(datos[clave].lower(), 'SIN NIVEL')
        except (ValueError, AttributeError):
            pass

    cabecera = msg[:120]
    for patron in (re_logfmt, re_corchetes, re_mayusculas):
        m = patron.search(cabecera)
        if m and m.group(1).lower() in NIVELES:
            return NIVELES[m.group(1).lower()]

    m = re_mssql.search(msg)
    if m:
        return 'CRITICAL' if int(m.group(1)) >= 20 else 'ERROR' if int(m.group(1)) >= 11 else 'INFO'

    m = re_http.search(msg)
    if m:
        codigo = int(m.group(1))
        return 'ERROR' if codigo >= 500 else 'WARN' if codigo >= 400 else 'INFO'

    return 'SIN NIVEL'

def plantilla(msg):
    for patron, sustituto in NORMALIZACIONES:
        msg = patron.sub(sustituto, msg)
    return msg.strip()

def parsear(lineas):
    entradas = []
    for linea in lineas:
        linea = ansi.sub('', linea).rstrip()
        ts_str, _, msg = linea.partition(' ')
        try:
            ts = leerTimestamp(ts_str)
        except ValueError:
            continue
        # Si el motor parte una línea en dos fragmentos, la marca del segundo queda pegada al final
        msg = re_timestamp_final.sub('', msg)
        if not msg.strip():
            continue
        entradas.append(Entrada(ts, detectarNivel(msg), msg, plantilla(msg)))
    entradas.sort(key=lambda e: e.ts)
    return entradas

def caracteristicas(entradas, frecuencias):
    """Características de cada línea para el modelo: gravedad del nivel, rareza de su tipo de mensaje
    (-log10 de su frecuencia relativa) y el contenido de la plantilla (TF-IDF reducido con SVD a pocas
    dimensiones). Con el TF-IDF disperso directamente, el bosque casi nunca elige la dimensión que aísla
    una línea concreta y no detecta ni las más evidentes."""
    total = len(entradas)
    nivel = np.array([[PESO_NIVEL.get(e.nivel, 0)] for e in entradas], dtype=float)
    rareza = np.array([[-np.log10(frecuencias[(e.nivel, e.plantilla)] / total)] for e in entradas])

    tfidf = TfidfVectorizer(max_features=1000, token_pattern=r'(?u)\b\w+\b').fit_transform([e.plantilla for e in entradas])
    componentes = min(DIMENSIONES_CONTENIDO, tfidf.shape[1] - 1)
    contenido = TruncatedSVD(n_components=componentes, random_state=0).fit_transform(tfidf) if componentes >= 1 else np.zeros((total, 0))
    return np.hstack([nivel, rareza, contenido])

def detectarAnomalias(entradas):
    """Isolation Forest sobre las características de cada línea. Con contamination='auto' solo se marcan
    las líneas cuya puntuación supera el umbral del propio modelo, así que puede no haber ninguna.

    Con pocos tipos de mensaje que se repiten, el modelo considera aislable cualquier grupo pequeño (p. ej.
    un mensaje que aparece en el 2 % de las líneas), así que de lo que marca solo se conservan los tipos de
    mensaje raros: los que no superan el 1 % de las líneas (o 3 apariciones en logs cortos)."""
    if len(entradas) < MIN_LINEAS_ANOMALIAS or len({e.plantilla for e in entradas}) < 2:
        return None

    frecuencias = Counter((e.nivel, e.plantilla) for e in entradas)
    max_veces = max(len(entradas) * FRECUENCIA_MAXIMA_ANOMALIA, MIN_VECES_ANOMALIA)

    X = caracteristicas(entradas, frecuencias)
    modelo = IsolationForest(contamination='auto', n_estimators=200, random_state=0)
    predicciones = modelo.fit_predict(X)
    puntuaciones = modelo.score_samples(X)

    grupos = defaultdict(list)
    for e, prediccion, puntuacion in zip(entradas, predicciones, puntuaciones):
        if prediccion == -1 and frecuencias[(e.nivel, e.plantilla)] <= max_veces:
            grupos[(e.nivel, e.plantilla)].append((e, puntuacion))

    anomalias = []
    for (nivel, _), lineas in grupos.items():
        anomalias.append({
            'nivel': nivel,
            'veces': len(lineas),
            'ultima': max(e.ts for e, _ in lineas),
            'ejemplo': lineas[-1][0].msg,
            'puntuacion': min(p for _, p in lineas)
        })
    anomalias.sort(key=lambda a: (-PESO_NIVEL.get(a['nivel'], 0), a['puntuacion']))
    return anomalias

def detectarPicos(entradas, ventana=30, factor=3.0, minimo=10):
    """Ventanas de `ventana` segundos con más líneas que la media + factor·σ (y al menos `minimo`, para que
    en logs con poca actividad un par de líneas seguidas no cuenten como pico). Las consecutivas se agrupan."""
    if len(entradas) < 2:
        return []
    inicio = entradas[0].ts
    total = int((entradas[-1].ts - inicio).total_seconds() // ventana) + 1
    if total < 10:
        return []
    conteos = [0] * total
    for e in entradas:
        conteos[int((e.ts - inicio).total_seconds() // ventana)] += 1
    umbral = max(mean(conteos) + factor * pstdev(conteos), minimo - 1)

    picos = []
    for i, c in enumerate(conteos):
        if c <= umbral:
            continue
        w0 = inicio + timedelta(seconds=i * ventana)
        if picos and picos[-1][1] == w0:
            picos[-1][1] = w0 + timedelta(seconds=ventana)
            picos[-1][2] += c
        else:
            picos.append([w0, w0 + timedelta(seconds=ventana), c])
    return picos

def analizarLogs(nombre_contenedor, num_lineas):
    lineas = motor.logs(nombre_contenedor, num_lineas)
    if not lineas:
        return f"No se obtuvieron logs para '{nombre_contenedor}'."
    entradas = parsear(lineas)
    if not entradas:
        return f"No hay entradas de log parseables en '{nombre_contenedor}'."

    niveles = Counter(e.nivel for e in entradas)
    plantillas = Counter(e.plantilla for e in entradas)
    separador = '────────────'

    res = [
        f"Rango temporal (UTC): {formatear(entradas[0].ts)} → {formatear(entradas[-1].ts)}",
        f"Líneas analizadas: {len(entradas)}  ·  Mensajes distintos (plantillas): {len(plantillas)}",
        "Niveles: " + "  ".join(f"{n}:{niveles[n]}" for n in sorted(niveles, key=lambda n: -PESO_NIVEL.get(n, 0))),
        separador
    ]

    anomalias = detectarAnomalias(entradas)
    if anomalias is None:
        res.append(f"Anomalías: no hay datos suficientes (mínimo {MIN_LINEAS_ANOMALIAS} líneas y 2 tipos de mensaje).")
    elif not anomalias:
        res.append("Anomalías: no se ha detectado ninguna.")
    else:
        res.append(f"Anomalías detectadas: {sum(a['veces'] for a in anomalias)} líneas en {len(anomalias)} tipos de mensaje"
                   + (f" (se muestran {MAX_ANOMALIAS})" if len(anomalias) > MAX_ANOMALIAS else ""))
        for a in anomalias[:MAX_ANOMALIAS]:
            res.append(f"  [{a['nivel']}] ×{a['veces']}, última {formatear(a['ultima'])}: {a['ejemplo'][:200]}")

    # Un error que se repite mucho no es raro, así que el modelo no lo marca: se listan aparte
    errores = Counter(e.plantilla for e in entradas if e.nivel in ('ERROR', 'CRITICAL'))
    if errores:
        ejemplos = {e.plantilla: e.msg for e in entradas if e.nivel in ('ERROR', 'CRITICAL')}
        res.append(separador)
        res.append("Errores más frecuentes:")
        for p, veces in errores.most_common(5):
            res.append(f"  ×{veces}: {ejemplos[p][:200]}")

    picos = detectarPicos(entradas)
    if picos:
        res.append(separador)
        res.append("Picos de actividad (ventanas de 30 s por encima de la media + 3σ):")
        for w0, w1, c in picos[:10]:
            res.append(f"  {formatear(w0)} → {formatear(w1)}: {c} líneas")

    res.append(separador)
    res.append(f"Últimas {min(LINEAS_FINALES, len(entradas))} líneas:")
    for e in entradas[-LINEAS_FINALES:]:
        res.append(f"{formatear(e.ts)} [{e.nivel}] {e.msg[:300]}")

    return "\n".join(res)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python analisis_logs.py <contenedor> <líneas>")
        sys.exit(1)
    nombre, n = sys.argv[1], int(sys.argv[2])
    print(analizarLogs(nombre, n))

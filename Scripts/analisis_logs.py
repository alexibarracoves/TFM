import re
import subprocess
import sys
from datetime import datetime, timedelta
from collections import Counter, namedtuple
from statistics import mean, pstdev

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest

Entry = namedtuple('Entry', ['ts', 'level', 'msg', 'raw'])

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def clean_ansi(line: str) -> str:
    return ansi_escape.sub('', line)

def format_datetime(dt: datetime) -> str:
    return dt.strftime('%d/%m/%Y %H:%M:%S')

def detect_activity_spikes(timestamps, window_seconds=30, threshold_factor=1.0):
    if not timestamps:
        return []
    start, end = timestamps[0], timestamps[-1]
    total_secs = (end - start).total_seconds()
    num_w = int(total_secs // window_seconds) + 1
    counts = [0] * num_w
    for t in timestamps:
        idx = int((t - start).total_seconds() // window_seconds)
        counts[idx] += 1
    avg = mean(counts)
    std = pstdev(counts) if num_w > 1 else 0
    thresh = avg + threshold_factor * std
    spikes = []
    for i, c in enumerate(counts):
        if c > thresh:
            w0 = start + timedelta(seconds=i * window_seconds)
            w1 = w0 + timedelta(seconds=window_seconds)
            spikes.append((w0, w1, c))
    return spikes

def analizar_logs_puro(nombre_contenedor, num_lineas, contamination=0.05):
    # 1) Obtener raw logs
    cmd = ['podman', 'logs', '--timestamps', '--tail', str(num_lineas), nombre_contenedor]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
    if not raw:
        return f"No se obtuvieron logs para '{nombre_contenedor}'."

    # 2) Parsear y filtrar entradas válidas
    entries = []
    level_counts = Counter()
    for line in raw:
        clean = clean_ansi(line)
        parts = clean.split(' ', 3)
        if len(parts) < 4:
            continue
        ts_str, _, level, msg = parts
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        lvl = level.upper()
        if lvl == 'WARNING':
            lvl = 'WARN'
        if lvl not in ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'):
            lvl = 'OTHER'
        level_counts[lvl] += 1
        entries.append(Entry(ts=ts, level=lvl, msg=msg, raw=clean))

    if not entries:
        return f"No hay entradas de log parseables en '{nombre_contenedor}'."

    # 3) Rango temporal
    entries.sort(key=lambda e: e.ts)
    start, end = entries[0].ts, entries[-1].ts
    time_range = f"Rango temporal: {format_datetime(start)} → {format_datetime(end)}"

    # 4) Detección de anomalías
    messages = [e.msg for e in entries]
    X = TfidfVectorizer(max_features=1000).fit_transform(messages).toarray()
    iso = IsolationForest(contamination=contamination, random_state=0)
    iso.fit(X)
    scores = iso.score_samples(X)

    # Número de anomalías a mostrar: 1 por cada 100 líneas, máximo 20
    total = len(entries)
    n_show = max(1, min(total // 100, 20))
    anomalies = sorted(enumerate(scores), key=lambda x: x[1])[:n_show]

    # 5) Detección de picos de actividad
    timestamps = [e.ts for e in entries]
    spikes = detect_activity_spikes(timestamps)

    # 6) Construir reporte
    res = [
        time_range,
        f"Total de líneas analizadas: {len(raw)}"
    ]
    # niveles en orden de menor a mayor prioridad
    prioridad = ['INFO', 'DEBUG', 'WARN', 'ERROR']
    ordenados = [f"{lvl}:{level_counts[lvl]}" for lvl in prioridad if lvl in level_counts]
    resto = [f"{lvl}:{cnt}" for lvl, cnt in level_counts.items() if lvl not in prioridad]
    levels_str = "  ".join(ordenados + resto)
    res.append(f"Niveles: {levels_str}")
    res.append("────────────")
    res.append(f"Anomalías detectadas: {len(anomalies)}")
    for idx, _ in anomalies:
        e = entries[idx]
        res.append(f"{format_datetime(e.ts)} {e.level} {e.msg}")

    if spikes:
        res.append("────────────")
        res.append("Picos de actividad detectados:")
        for w0, w1, cnt in spikes:
            res.append(f"{format_datetime(w0)} → {format_datetime(w1)} : {cnt} logs")

    # 7) Volcado completo de logs
    res.append("────────────")
    res.append("Volcado completo de logs:")
    for e in entries:
        res.append(f"{format_datetime(e.ts)} {e.level} {e.msg}")

    return "\n".join(res)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python script.py <contenedor> <líneas>")
        sys.exit(1)
    nombre, n = sys.argv[1], int(sys.argv[2])
    print(analizar_logs_puro(nombre, n))

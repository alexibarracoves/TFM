import re
import subprocess, sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import IsolationForest
from collections import Counter

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def clean_ansi(line: str) -> str:
    return ansi_escape.sub('', line)

def analizar_logs_puro(nombre_contenedor, num_lineas, contamination=0.05):
    cmd = ['podman', 'logs', '--timestamps', '--tail', str(num_lineas), nombre_contenedor]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()

    messages = []
    for L in raw:
        clean = clean_ansi(L)
        parts = clean.split(' ', 1)
        if len(parts) == 2:
            messages.append(parts[1].strip())
        else:
            messages.append(clean.strip())

    if not messages or all(msg == "" for msg in messages):
        return f"No se obtuvieron logs para el contenedor '{nombre_contenedor}'."

    vect = TfidfVectorizer(max_features=1000)
    X = vect.fit_transform(messages)

    iso = IsolationForest(contamination=contamination, random_state=0)
    y = iso.fit_predict(X.toarray())
    idx_anom = [i for i, p in enumerate(y) if p == -1]

    ctr = Counter(messages)
    resumen_patrones = "\n".join(f"- {m}: {c} veces" for m, c in ctr.most_common())

    res = f"Analizadas {len(raw)} líneas.\n"
    res += f"Anomalías detectadas: {len(idx_anom)}\n"
    if idx_anom:
        res += "Líneas anómalas:\n" + "\n".join(clean_ansi(raw[i]) for i in idx_anom[:5])
        if len(idx_anom) > 5:
            res += f"\n...y {len(idx_anom)-5} más.\n"
    res += "\n\nPatrones más frecuentes:\n" + resumen_patrones
    return res

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python script.py <contenedor> <líneas>")
        sys.exit(1)
    print(analizar_logs_puro(sys.argv[1], int(sys.argv[2])))

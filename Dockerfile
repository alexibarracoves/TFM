# Frontend (Angular)
FROM node:22-alpine AS visor
WORKDIR /visor
COPY Visor/package.json Visor/package-lock.json ./
RUN npm ci
COPY Visor/ ./
RUN npm run build -- --configuration production

# Dependencias de la API (Node)
FROM node:24-trixie-slim AS servidor
WORKDIR /server
COPY Server/package.json Server/package-lock.json ./
RUN npm ci --omit=dev

FROM aquasec/trivy:0.76.1 AS trivy

# Imagen final: Python con Node y Trivy copiados como binarios
FROM python:3.13-slim

COPY --from=servidor /usr/local/bin/node /usr/local/bin/node
COPY --from=trivy /usr/local/bin/trivy /usr/local/bin/trivy

WORKDIR /app

COPY Scripts/requirements.txt /app/Scripts/requirements.txt
RUN pip install --no-cache-dir -r /app/Scripts/requirements.txt

COPY --from=servidor /server/node_modules /app/Server/node_modules
COPY Server/ /app/Server/
COPY --from=visor /visor/dist/visor/browser /app/Server/public
COPY Scripts/ /app/Scripts/

# Usuario al que el entrypoint cede la ejecución cuando el socket lo permite
RUN chmod +x /app/Scripts/entrypoint.sh \
    && useradd --system --uid 10001 --user-group --no-create-home analizador \
    && mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DB_PATH=/app/data/analizador.db \
    TRIVY_CACHE_DIR=/app/data/trivy

# Base de datos y caché de Trivy (~1 GB tras el primer escaneo)
VOLUME /app/data

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/salud', timeout=4)"

ENTRYPOINT ["/app/Scripts/entrypoint.sh"]

CMD ["python3", "/app/Scripts/analisis_contenedores.py"]

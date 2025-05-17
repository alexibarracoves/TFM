FROM python:3.10-slim

WORKDIR /app

COPY generador_logs.py /app/

RUN chmod +x /app/generador_logs.py

ENTRYPOINT ["python3", "-u", "/app/generador_logs.py"]
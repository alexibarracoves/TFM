FROM ubuntu:latest

WORKDIR /app

COPY Scripts/ /app/Scripts/
COPY Server/ /app/Server/

RUN chmod +x /app/Scripts/entrypoint.sh

RUN apt-get update && apt-get install -y wget curl gnupg lsb-release podman postgresql postgresql-contrib python3 python3-psycopg2 npm && apt-get clean

RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && apt-get install -y nodejs

RUN wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/trivy-keyring.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/trivy.list \
    && apt-get update && apt-get install -y trivy

RUN cd /app/Server && npm install

EXPOSE 3000

WORKDIR /app

ENTRYPOINT ["/app/Scripts/entrypoint.sh"]

ENV CONTAINER_HOST=unix:///run/podman/podman.sock

CMD ["python3", "/app/Scripts/analisis_contenedores.py"]
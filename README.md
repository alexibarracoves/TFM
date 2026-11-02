# Analizador de seguridad de contenedores

Herramienta autocontenida que se ejecuta como un contenedor más y analiza los contenedores en ejecución de la máquina, mostrando los resultados en un panel web:

- **Configuración en tiempo de ejecución**: estado, capacidades Linux efectivas, puertos publicados, redes y si el motor se ejecuta en modo *root* o *rootless*.
- **Vulnerabilidades de las imágenes**: escaneo con [Trivy](https://trivy.dev) de cada imagen en uso, con el recuento por severidad y el detalle de cada CVE.
- **Análisis de logs**: rango temporal, recuento por nivel, detección de anomalías (TF-IDF + Isolation Forest) y detección de picos de actividad.

Proyecto desarrollado como Trabajo Fin de Máster.

> **Estado:** actualmente solo es compatible con **Podman**. El soporte para Docker y otras mejoras están en la [hoja de ruta](#hoja-de-ruta).

## Arquitectura

Todo se ejecuta dentro de un único contenedor:

| Componente | Ruta | Función |
|---|---|---|
| Recolector | `Scripts/analisis_contenedores.py` | Cada 5 s consulta `podman ps` / `podman inspect` y guarda el estado en la base de datos. |
| Escáner de imágenes | `Scripts/analisis_imagenes.py` | Lanza Trivy cuando aparece una imagen nueva y, además, cada ~10 minutos. |
| Analizador de logs | `Scripts/analisis_logs.py` | Se ejecuta bajo demanda desde la API sobre `podman logs`. |
| Base de datos | `Scripts/db_init.sql` | PostgreSQL local con las tablas `imagenes`, `contenedores`, `vulnerabilidades` y `podman`. |
| API | `Server/` | Express (Node.js) en el puerto 3000; también sirve el frontend. |
| Visor | `Visor/` | Frontend en Angular + Angular Material. |
| Generador de logs | `Generador-logs/` | Contenedor de prueba que emite logs aleatorios con ráfagas para probar el análisis. |

El contenedor se comunica con el motor a través del socket de Podman montado en `/run/podman/podman.sock`.

## Puesta en marcha

### Requisitos

- Podman con el servicio de API activo (`podman system service`) o el socket `podman.socket` de systemd.
- Acceso a Internet en el primer arranque (Trivy descarga su base de datos de vulnerabilidades).

### Construir la imagen

```bash
podman build -t analizador-contenedores .
```

### Ejecutar

Modo *rootful* (socket del sistema):

```bash
sudo systemctl enable --now podman.socket
sudo podman run -d --name analizador -p 3000:3000 \
  -v /run/podman/podman.sock:/run/podman/podman.sock \
  analizador-contenedores
```

Modo *rootless* (socket del usuario):

```bash
systemctl --user enable --now podman.socket
podman run -d --name analizador -p 3000:3000 \
  -v $XDG_RUNTIME_DIR/podman/podman.sock:/run/podman/podman.sock \
  analizador-contenedores
```

Abre <http://localhost:3000>.

> **Aviso de seguridad:** montar el socket del motor de contenedores da a este contenedor control total sobre el resto de contenedores (y, en modo *rootful*, sobre la máquina). La API no tiene autenticación: no publiques el puerto 3000 en redes no confiables.

### Contenedor de prueba

```bash
podman build -t localhost/generador-logs Generador-logs
podman run -d --name generador-logs localhost/generador-logs
```

Pulsa **Analizar** en la fila de `generador-logs` para ver el resumen de logs.

### Probarlo con Docker Desktop (Windows / macOS)

Mientras no haya soporte nativo para Docker, puedes levantar un Podman dentro de un contenedor y conectar el analizador a su socket. El analizador solo verá los contenedores que se ejecuten dentro de ese Podman, no los de Docker.

```bash
docker build -t analizador-contenedores .
docker volume create podman-sock
docker run -d --name podman-host --privileged -v podman-sock:/run/podman \
  quay.io/podman/stable:v5.4.2 podman system service --time=0 unix:///run/podman/podman.sock
docker exec podman-host podman run -d --name web docker.io/library/nginx:1.27
docker run -d --name analizador -p 3000:3000 -v podman-sock:/run/podman analizador-contenedores
```

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/contenedores?page=&size=` | Contenedores en ejecución (paginado) y modo del motor. |
| GET | `/imagenes/:id` | Imagen con el recuento de vulnerabilidades por severidad. |
| GET | `/vulnerabilidades/:idImagen?page=&size=` | Vulnerabilidades de una imagen (paginado). |
| GET | `/contenedores/:nombre/logs/resumen` | Resumen del análisis de las últimas 10 000 líneas de log. |

## Desarrollo

Frontend:

```bash
cd Visor
npm ci
npm start        # http://localhost:4200
```

API (requiere PostgreSQL con el esquema de `Scripts/db_init.sql`):

```bash
cd Server
npm ci
node index.js
```

## Hoja de ruta

- [ ] Soporte para Docker y Podman a través de la API compatible con Docker.
- [ ] URLs relativas en el frontend (ahora apunta a `localhost:3000`).
- [ ] Imagen más ligera: SQLite en lugar de PostgreSQL, versiones de Python y Node con soporte, Trivy con versión fija y caché persistente, usuario sin privilegios.
- [ ] Endurecimiento: escuchar en `127.0.0.1` por defecto, token de acceso opcional, CORS restringido.
- [ ] Análisis de logs más robusto con formatos de log reales.
- [ ] CI con GitHub Actions y publicación en Docker Hub.

## Licencia

[MIT](LICENSE)

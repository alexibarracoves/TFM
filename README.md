# Analizador de seguridad de contenedores

Herramienta autocontenida que se ejecuta como un contenedor más y analiza los contenedores en ejecución de la máquina, mostrando los resultados en un panel web:

- **Configuración en tiempo de ejecución**: estado, capacidades Linux efectivas, puertos publicados, redes y si el motor se ejecuta en modo *root* o *rootless*.
- **Vulnerabilidades de las imágenes**: escaneo con [Trivy](https://trivy.dev) de cada imagen en uso, con el recuento por severidad y el detalle de cada CVE.
- **Análisis de logs**: rango temporal, recuento por nivel, detección de anomalías (TF-IDF + Isolation Forest) y detección de picos de actividad.

Funciona con **Docker** y con **Podman** (rootful o rootless).

Proyecto desarrollado como Trabajo Fin de Máster.

## Arquitectura

Todo se ejecuta dentro de un único contenedor:

| Componente | Ruta | Función |
|---|---|---|
| Motor | `Scripts/motor.py` | Acceso al motor de contenedores mediante la API compatible con Docker (y la API nativa de Podman cuando hace falta). |
| Recolector | `Scripts/analisis_contenedores.py` | Cada 5 s lista e inspecciona los contenedores en ejecución y guarda el estado en la base de datos. |
| Escáner de imágenes | `Scripts/analisis_imagenes.py` | Lanza Trivy cuando aparece una imagen nueva y, además, cada ~10 minutos. |
| Analizador de logs | `Scripts/analisis_logs.py` | Se ejecuta bajo demanda desde la API sobre los logs del contenedor. |
| Base de datos | `Scripts/db_init.sql` | SQLite en `/app/data` con las tablas `imagenes`, `contenedores`, `vulnerabilidades` y `motor`. El recolector escribe y la API solo lee. |
| API | `Server/` | Express (Node.js) en el puerto 3000; también sirve el frontend. |
| Visor | `Visor/` | Frontend en Angular + Angular Material. |
| Generador de logs | `Generador-logs/` | Contenedor de prueba que emite logs aleatorios con ráfagas para probar el análisis. |

El contenedor se comunica con el motor a través de su socket, que hay que montar dentro. Al arrancar busca `/var/run/docker.sock` y después `/run/podman/podman.sock`; también se puede indicar otro con la variable `DOCKER_HOST`. Trivy usa ese mismo socket, así que también analiza imágenes construidas en local.

## Puesta en marcha

> **Aviso de seguridad:** montar el socket del motor de contenedores da a este contenedor control total sobre el resto de contenedores (y, en modo *rootful*, sobre la máquina). Lee la sección de [seguridad](#seguridad) antes de exponerlo fuera de tu equipo.

Se necesita acceso a Internet en el primer arranque, porque Trivy descarga su base de datos de vulnerabilidades.

### Construir la imagen

```bash
docker build -t analizador-contenedores .
```

(o `podman build` con los mismos argumentos)

### Docker

Linux, y también Docker Desktop en Windows y macOS:

```bash
docker run -d --name analizador -p 127.0.0.1:3000:3000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v analizador-datos:/app/data \
  analizador-contenedores
```

> En Git Bash (Windows), antepón `MSYS_NO_PATHCONV=1` para que no reescriba la ruta del socket.

### Podman *rootful*

```bash
sudo systemctl enable --now podman.socket
sudo podman run -d --name analizador -p 127.0.0.1:3000:3000 \
  -v /run/podman/podman.sock:/run/podman/podman.sock \
  -v analizador-datos:/app/data \
  analizador-contenedores
```

### Podman *rootless*

```bash
systemctl --user enable --now podman.socket
podman run -d --name analizador -p 127.0.0.1:3000:3000 \
  -v $XDG_RUNTIME_DIR/podman/podman.sock:/run/podman/podman.sock \
  -v analizador-datos:/app/data \
  analizador-contenedores
```

Abre <http://localhost:3000>.

El volumen `analizador-datos` guarda la base de datos y la caché de Trivy (alrededor de 1 GB tras el primer escaneo). Sin él, cada vez que se recrea el contenedor se vuelve a descargar la base de datos de vulnerabilidades y se reescanean todas las imágenes.

El contenedor tiene un *healthcheck* sobre `GET /salud`.

## Seguridad

- **Acceso solo local por defecto.** Los ejemplos publican el puerto en `127.0.0.1`, así que el panel solo es accesible desde la propia máquina. Si lo publicas en otra interfaz, define un token.
- **Token de acceso opcional.** Con `-e ANALIZADOR_TOKEN=<token>` todas las rutas (salvo `/salud`) exigen el token:
  - en el navegador, abre una vez `http://<host>:3000/?token=<token>`; se guarda en una cookie `HttpOnly` y `SameSite=Strict` y se quita de la URL;
  - desde scripts, envía la cabecera `Authorization: Bearer <token>`.

  Genera uno aleatorio, por ejemplo con `openssl rand -hex 32`. El token viaja en claro por HTTP: para accesos remotos, pon delante un proxy con HTTPS.
- **Sin root cuando el socket lo permite.** Si el socket pertenece a un grupo distinto de root (el grupo `docker` en Linux), el contenedor deja root al arrancar y continúa como el usuario `analizador` (uid 10001), solo con ese grupo, sin *capabilities* y con `no_new_privs`. Si solo root puede usar el socket (Docker Desktop, Podman *rootful*), sigue como root y lo avisa en los logs. En Podman *rootless*, el root del contenedor ya es tu usuario sin privilegios. Para desactivar el cambio de usuario: `-e ANALIZADOR_MANTENER_ROOT=1`.
- **Superficie mínima.** La API solo lee de la base de datos y no tiene CORS (el frontend se sirve desde el mismo origen). Envía cabeceras de seguridad (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`) y limita la paginación a 100 elementos. Además, solo analiza los logs de contenedores en ejecución con nombre válido, como mucho dos análisis a la vez.

### Contenedor de prueba

```bash
docker build -t generador-logs Generador-logs
docker run -d --name generador-logs generador-logs
```

Pulsa **Analizar** en la fila de `generador-logs` para ver el resumen de logs.

### Limitaciones conocidas

- Con Docker, las capacidades efectivas se calculan a partir de las capacidades por defecto del motor y de `CapAdd`/`CapDrop`/`--privileged`. Con Podman se leen directamente de su API.
- Trivy no analiza algunas distribuciones, como Fedora. En esas imágenes el recuento de vulnerabilidades sale vacío.

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

El frontend redirige la API a `http://localhost:3000` mediante `proxy.conf.json`.

API (Node.js 22.13 o superior; lee la base de datos que indique `DB_PATH`):

```bash
cd Server
npm ci
DB_PATH=../data/analizador.db node index.js
```

Recolector (Python 3.13; crea la base de datos si no existe):

```bash
pip install -r Scripts/requirements.txt
DB_PATH=data/analizador.db python Scripts/analisis_contenedores.py
```

## Hoja de ruta

- [x] Soporte para Docker y Podman a través de la API compatible con Docker.
- [x] URLs relativas en el frontend.
- [x] Imagen más ligera: SQLite en lugar de PostgreSQL, versiones de Python y Node con soporte, Trivy con versión fija y caché persistente.
- [x] Endurecimiento: acceso local por defecto, token de acceso opcional, sin CORS, cabeceras de seguridad, validación de entrada y ejecución sin root cuando el socket lo permita.
- [ ] Análisis de logs más robusto con formatos de log reales.
- [ ] CI con GitHub Actions y publicación en Docker Hub.

## Licencia

[MIT](LICENSE)

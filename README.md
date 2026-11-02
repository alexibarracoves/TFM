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
| Base de datos | `Scripts/db_init.sql` | PostgreSQL local con las tablas `imagenes`, `contenedores`, `vulnerabilidades` y `motor`. |
| API | `Server/` | Express (Node.js) en el puerto 3000; también sirve el frontend. |
| Visor | `Visor/` | Frontend en Angular + Angular Material. |
| Generador de logs | `Generador-logs/` | Contenedor de prueba que emite logs aleatorios con ráfagas para probar el análisis. |

El contenedor se comunica con el motor a través de su socket, que hay que montar dentro. Al arrancar busca `/var/run/docker.sock` y después `/run/podman/podman.sock`; también se puede indicar otro con la variable `DOCKER_HOST`. Trivy usa ese mismo socket, así que también analiza imágenes construidas en local.

## Puesta en marcha

> **Aviso de seguridad:** montar el socket del motor de contenedores da a este contenedor control total sobre el resto de contenedores (y, en modo *rootful*, sobre la máquina). La API no tiene autenticación: no publiques el puerto 3000 en redes no confiables.

Se necesita acceso a Internet en el primer arranque, porque Trivy descarga su base de datos de vulnerabilidades.

### Construir la imagen

```bash
docker build -t analizador-contenedores .
```

(o `podman build` con los mismos argumentos)

### Docker

Linux, y también Docker Desktop en Windows y macOS:

```bash
docker run -d --name analizador -p 3000:3000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  analizador-contenedores
```

> En Git Bash (Windows), antepón `MSYS_NO_PATHCONV=1` para que no reescriba la ruta del socket.

### Podman *rootful*

```bash
sudo systemctl enable --now podman.socket
sudo podman run -d --name analizador -p 3000:3000 \
  -v /run/podman/podman.sock:/run/podman/podman.sock \
  analizador-contenedores
```

### Podman *rootless*

```bash
systemctl --user enable --now podman.socket
podman run -d --name analizador -p 3000:3000 \
  -v $XDG_RUNTIME_DIR/podman/podman.sock:/run/podman/podman.sock \
  analizador-contenedores
```

Abre <http://localhost:3000>.

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

API (requiere PostgreSQL con el esquema de `Scripts/db_init.sql`):

```bash
cd Server
npm ci
node index.js
```

## Hoja de ruta

- [x] Soporte para Docker y Podman a través de la API compatible con Docker.
- [x] URLs relativas en el frontend.
- [ ] Imagen más ligera: SQLite en lugar de PostgreSQL, versiones de Python y Node con soporte, Trivy con versión fija y caché persistente, usuario sin privilegios.
- [ ] Endurecimiento: escuchar en `127.0.0.1` por defecto, token de acceso opcional, CORS restringido.
- [ ] Análisis de logs más robusto con formatos de log reales.
- [ ] CI con GitHub Actions y publicación en Docker Hub.

## Licencia

[MIT](LICENSE)

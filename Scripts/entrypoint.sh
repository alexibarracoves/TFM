#!/bin/bash
set -e

UID_ANALIZADOR=10001

# Si el socket del motor es accesible a través de un grupo distinto de root (p. ej. el grupo
# docker en Linux), se deja de ser root y se continúa con un usuario sin privilegios de ese grupo.
# Si solo root puede usarlo (Docker Desktop, Podman rootful) no hay otra opción que seguir como root,
# y en Podman rootless el root del contenedor ya es el usuario sin privilegios del host.
if [ "$(id -u)" = 0 ] && [ "${ANALIZADOR_MANTENER_ROOT:-0}" != 1 ]; then
    socket=""
    if [[ "${DOCKER_HOST:-}" == unix://* ]]; then
        socket="${DOCKER_HOST#unix://}"
    else
        for ruta in /var/run/docker.sock /run/podman/podman.sock; do
            if [ -S "$ruta" ]; then socket="$ruta"; break; fi
        done
    fi

    if [ -S "$socket" ]; then
        gid=$(stat -c %g "$socket")
        permisos=$(stat -c %a "$socket")
        if [ "$gid" != 0 ] && [ $(( 8#$permisos & 8#060 )) -eq $(( 8#060 )) ]; then
            find /app/data ! -user "$UID_ANALIZADOR" -exec chown "$UID_ANALIZADOR:$UID_ANALIZADOR" {} +
            echo "Ejecutando como usuario sin privilegios (uid $UID_ANALIZADOR, grupo del socket $gid)"
            exec setpriv --reuid="$UID_ANALIZADOR" --regid="$UID_ANALIZADOR" --groups="$gid" \
                --inh-caps=-all --bounding-set=-all --no-new-privs \
                env HOME=/tmp "$0" "$@"
        fi
        echo "AVISO: solo root puede usar el socket $socket; el analizador se ejecuta como root"
    fi
fi

# Crea la base de datos y comprueba la conexión con el motor antes de arrancar nada
cd /app/Scripts
python3 -c "import utils; utils.inicializarDb()"

cd /app/Server
node index.js &

"$@" &

# Si cualquiera de los dos procesos termina, se para el contenedor
trap 'kill -TERM $(jobs -p) 2>/dev/null' TERM INT
wait -n
codigo=$?
kill -TERM $(jobs -p) 2>/dev/null || true
exit $codigo

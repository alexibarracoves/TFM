#!/bin/bash
set -e

UID_ANALIZADOR=10001

# Se deja de ser root siempre que el socket del motor lo permita:
#  - si es accesible a través de un grupo distinto de root (p. ej. el grupo docker en Linux),
#    se continúa como el usuario analizador con ese grupo;
#  - si pertenece a un usuario distinto de root (sockets rootless de Podman o Docker),
#    se continúa como ese usuario.
# Si solo root puede usarlo (Docker Desktop, Podman rootful) no hay otra opción que seguir como root.
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
        propietario=$(stat -c %u "$socket")
        gid=$(stat -c %g "$socket")
        permisos=$(stat -c %a "$socket")
        nuevo_uid=""
        if [ "$gid" != 0 ] && [ $(( 8#$permisos & 8#060 )) -eq $(( 8#060 )) ]; then
            nuevo_uid=$UID_ANALIZADOR; nuevo_gid=$UID_ANALIZADOR; grupos="--groups=$gid"
            echo "Ejecutando como usuario sin privilegios (uid $nuevo_uid, grupo del socket $gid)"
        elif [ "$propietario" != 0 ] && [ $(( 8#$permisos & 8#600 )) -eq $(( 8#600 )) ]; then
            nuevo_uid=$propietario; nuevo_gid=$gid; grupos="--clear-groups"
            echo "Ejecutando como el propietario del socket (uid $nuevo_uid)"
        fi

        if [ -n "$nuevo_uid" ]; then
            find /app/data ! -user "$nuevo_uid" -exec chown "$nuevo_uid:$nuevo_gid" {} +
            exec setpriv --reuid="$nuevo_uid" --regid="$nuevo_gid" $grupos \
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
python3 /app/Server/servidor.py &

"$@" &

# Si cualquiera de los dos procesos termina, se para el contenedor
trap 'kill -TERM $(jobs -p) 2>/dev/null' TERM INT
wait -n
codigo=$?
kill -TERM $(jobs -p) 2>/dev/null || true
exit $codigo

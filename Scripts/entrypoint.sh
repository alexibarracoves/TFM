#!/bin/bash
set -e

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

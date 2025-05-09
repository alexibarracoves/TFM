#!/bin/bash

service postgresql start
su - postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres';\""
su - postgres -c "psql -f /app/Scripts/db_init.sql"

service postgresql restart

cd /app/Server
node index.js &

exec "$@"
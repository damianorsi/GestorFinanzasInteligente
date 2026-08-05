#!/bin/sh
set -e

# Las migraciones corren al arrancar el contenedor. Con cero revisiones esto es
# un no-op, así que es seguro desde la fase 1.
echo "[entrypoint] Aplicando migraciones de Alembic..."
alembic upgrade head

echo "[entrypoint] Arrancando: $*"
exec "$@"

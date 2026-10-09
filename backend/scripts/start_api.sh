#!/bin/sh
set -eu

# Las migraciones se ejecutan de forma explícita en el entorno de despliegue.
# No habilitar esto en más de una réplica simultáneamente sin un mecanismo de lock.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  # alembic.ini usa rutas relativas a backend/. Al ejecutar desde esa carpeta
  # funciona igual en local y dentro de la imagen Docker (/app/backend).
  (
    cd /app/backend
    alembic -c alembic.ini upgrade head
  )
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"

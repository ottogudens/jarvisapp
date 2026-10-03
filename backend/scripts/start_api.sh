#!/bin/sh
set -eu

# Las migraciones se ejecutan de forma explícita en el entorno de despliegue.
# No habilitar esto en más de una réplica simultáneamente sin un mecanismo de lock.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic -c backend/alembic.ini upgrade head
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"

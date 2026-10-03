FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema necesarias para PostgreSQL.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente del backend
COPY backend/ ./backend

# La API no requiere privilegios de root en tiempo de ejecución.
RUN addgroup --system jarvis && adduser --system --ingroup jarvis jarvis && \
    chown -R jarvis:jarvis /app && \
    chmod 0550 /app/backend/scripts/start_api.sh
USER jarvis

EXPOSE 8000

# Fix #24: Health check integrado
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["/app/backend/scripts/start_api.sh"]

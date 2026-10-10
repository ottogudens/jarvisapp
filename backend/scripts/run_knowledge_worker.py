"""Worker durable para indexación documental.

Ejecutar como servicio separado: python -m backend.scripts.run_knowledge_worker
"""
import asyncio
import logging
import os

from backend.database import SessionLocal, inicializar_base_de_datos_remota
from backend.knowledge_service import process_next_job

# Railway y otros proveedores suelen aceptar valores en minúsculas; logging de
# Python no. Normalizar evita que el worker caiga antes de procesar trabajos.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("bonso.knowledge_worker")
POLL_SECONDS = float(os.getenv("KNOWLEDGE_WORKER_POLL_SECONDS", "2"))
WORKER_CONCURRENCY = max(1, min(int(os.getenv("KNOWLEDGE_WORKER_CONCURRENCY", "2")), 8))
ALERT_CHECK_SECONDS = 60


async def consume(worker_number: int) -> None:
    """Consume trabajos independientes; SKIP LOCKED evita procesarlos dos veces."""
    last_alert_check = 0.0
    while True:
        db = SessionLocal()
        try:
            processed = await process_next_job(db)
            now = asyncio.get_running_loop().time()
            if worker_number == 0 and now - last_alert_check >= ALERT_CHECK_SECONDS:
                from backend.operations_alerts import cleanup_operational_data, dispatch_operational_alerts, record_worker_heartbeat
                record_worker_heartbeat(db)
                removed = cleanup_operational_data(db)
                if any(removed.values()):
                    logger.info("Limpieza operacional: %s", removed)
                sent = await dispatch_operational_alerts(db)
                if sent:
                    logger.warning("Se enviaron %s alerta(s) operativa(s)", sent)
                last_alert_check = now
        except Exception:
            logger.exception("Fallo no controlado en worker documental")
            processed = False
        finally:
            db.close()
        if not processed:
            await asyncio.sleep(POLL_SECONDS)


async def run() -> None:
    inicializar_base_de_datos_remota()
    logger.info("Worker documental iniciado con %s consumidor(es)", WORKER_CONCURRENCY)
    await asyncio.gather(*(consume(number) for number in range(WORKER_CONCURRENCY)))


if __name__ == "__main__":
    asyncio.run(run())

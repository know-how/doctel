"""Application startup and FastAPI app entrypoint for DocTel."""

import asyncio
import logging

from app.startup import startup_manager
from app.workers.ingest_worker import start_worker
from app.services.bootstrap import run_bootstrap_scan

logger = logging.getLogger(__name__)

# 2c. Ingest worker (critical - enables document processing)
async def _start_ingest():
    # start_worker schedules the background worker and returns quickly.
    # Use create_task here to be explicit that this should not block startup.
    try:
        asyncio.create_task(start_worker())
        return {"status": "healthy"}
    except Exception as e:
        logger.exception("Failed to start ingest worker: %s", e)
        return {"status": "failed", "error": str(e)}

startup_manager.register("ingest_worker", _start_ingest, critical=True)

# 3d. Bootstrap scan (file indexing)
startup_manager.register("bootstrap_scan", lambda: asyncio.create_task(run_bootstrap_scan()))

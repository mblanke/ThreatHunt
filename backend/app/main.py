"""ThreatHunt backend application.

Wires together: database, CORS, agent routes, dataset routes, hunt routes,
annotation/hypothesis routes, analysis routes, network routes, job queue,
load balancer. DB tables are auto-created on startup.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db, dispose_db
from app.api.routes.agent_v2 import router as agent_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.hunts import router as hunts_router
from app.api.routes.annotations import ann_router, hyp_router
from app.api.routes.enrichment import router as enrichment_router
from app.api.routes.correlation import router as correlation_router
from app.api.routes.reports import router as reports_router
from app.api.routes.auth import router as auth_router
from app.api.routes.keywords import router as keywords_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.network import router as network_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting ThreatHunt API ...")
    await init_db()
    logger.info("Database initialised")

    # Ensure uploads directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Upload dir: %s", os.path.abspath(settings.UPLOAD_DIR))

    # Seed default AUP keyword themes
    from app.db import async_session_factory
    from app.services.keyword_defaults import seed_defaults
    async with async_session_factory() as seed_db:
        await seed_defaults(seed_db)
    logger.info("AUP keyword defaults checked")

    # Start job queue (Phase 10)
    from app.services.job_queue import job_queue, register_all_handlers
    register_all_handlers()
    await job_queue.start()
    logger.info("Job queue started (%d workers)", job_queue._max_workers)

    # Start load balancer health loop (Phase 10)
    from app.services.load_balancer import lb
    await lb.start_health_loop(interval=30.0)
    logger.info("Load balancer health loop started")

    yield

    logger.info("Shutting down ...")
    # Stop job queue
    from app.services.job_queue import job_queue as jq
    await jq.stop()
    logger.info("Job queue stopped")

    # Stop load balancer
    from app.services.load_balancer import lb as _lb
    await _lb.stop_health_loop()
    logger.info("Load balancer stopped")

    from app.agents.providers_v2 import cleanup_client
    from app.services.enrichment import enrichment_engine
    await cleanup_client()
    await enrichment_engine.cleanup()
    await dispose_db()


app = FastAPI(
    title="ThreatHunt API",
    description="Analyst-assist threat hunting platform powered by Wile & Roadrunner LLM cluster",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(datasets_router)
app.include_router(hunts_router)
app.include_router(ann_router)
app.include_router(hyp_router)
app.include_router(enrichment_router)
app.include_router(correlation_router)
app.include_router(reports_router)
app.include_router(keywords_router)
app.include_router(analysis_router)
app.include_router(network_router)


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "ThreatHunt API",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "cluster": {
            "wile": settings.wile_url,
            "roadrunner": settings.roadrunner_url,
            "openwebui": settings.OPENWEBUI_URL,
        },
    }
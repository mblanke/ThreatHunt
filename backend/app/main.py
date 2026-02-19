"""ThreatHunt backend application.

Wires together: database, CORS, agent routes, dataset routes, hunt routes,
annotation/hypothesis routes.  DB tables are auto-created on startup.
"""

import logging
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting ThreatHunt API …")
    await init_db()
    logger.info("Database initialised")
    # Seed default AUP keyword themes
    from app.db import async_session_factory
    from app.services.keyword_defaults import seed_defaults
    async with async_session_factory() as seed_db:
        await seed_defaults(seed_db)
    logger.info("AUP keyword defaults checked")
    yield
    logger.info("Shutting down …")
    from app.agents.providers_v2 import cleanup_client
    from app.services.enrichment import enrichment_engine
    await cleanup_client()
    await enrichment_engine.cleanup()
    await dispose_db()


# Create FastAPI application
app = FastAPI(
    title="ThreatHunt API",
    description="Analyst-assist threat hunting platform powered by Wile & Roadrunner LLM cluster",
    version="0.3.0",
    lifespan=lifespan,
)

# Configure CORS
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


@app.get("/", tags=["health"])
async def root():
    """API health check."""
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

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
from app.api.routes.network import router as network_router
<<<<<<< HEAD
from app.api.routes.mitre import router as mitre_router
from app.api.routes.timeline import router as timeline_router
from app.api.routes.playbooks import router as playbooks_router
from app.api.routes.saved_searches import router as searches_router
from app.api.routes.stix_export import router as stix_router
=======
from app.api.routes.analysis import router as analysis_router
from app.api.routes.cases import router as cases_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.notebooks import router as notebooks_router
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

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
<<<<<<< HEAD

    # Start job queue
    from app.services.job_queue import (
        job_queue,
        register_all_handlers,
        reconcile_stale_processing_tasks,
        JobType,
    )

    if settings.STARTUP_RECONCILE_STALE_TASKS:
        reconciled = await reconcile_stale_processing_tasks()
        if reconciled:
            logger.info("Startup reconciliation marked %d stale tasks", reconciled)

    register_all_handlers()
    await job_queue.start()
    logger.info("Job queue started (%d workers)", job_queue._max_workers)

    # Pre-warm host inventory cache for existing hunts
    from app.services.host_inventory import inventory_cache
    async with async_session_factory() as warm_db:
        from sqlalchemy import select, func
        from app.db.models import Hunt, Dataset
        stmt = (
            select(Hunt.id)
            .join(Dataset, Dataset.hunt_id == Hunt.id)
            .group_by(Hunt.id)
            .having(func.count(Dataset.id) > 0)
        )
        result = await warm_db.execute(stmt)
        hunt_ids = [row[0] for row in result.all()]
    warm_hunts = hunt_ids[: settings.STARTUP_WARMUP_MAX_HUNTS]
    for hid in warm_hunts:
        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hid)
    if warm_hunts:
        logger.info(f"Queued host inventory warm-up for {len(warm_hunts)} hunts (total hunts with data: {len(hunt_ids)})")

    # Check which datasets still need processing
    # (no anomaly results = never fully processed)
    async with async_session_factory() as reprocess_db:
        from sqlalchemy import select, exists
        from app.db.models import Dataset, AnomalyResult
        # Find datasets that have zero anomaly results (pipeline never ran or failed)
        has_anomaly = (
            select(AnomalyResult.id)
            .where(AnomalyResult.dataset_id == Dataset.id)
            .limit(1)
            .correlate(Dataset)
            .exists()
        )
        stmt = select(Dataset.id).where(~has_anomaly)
        result = await reprocess_db.execute(stmt)
        unprocessed_ids = [row[0] for row in result.all()]

    if unprocessed_ids:
        to_reprocess = unprocessed_ids[: settings.STARTUP_REPROCESS_MAX_DATASETS]
        for ds_id in to_reprocess:
            job_queue.submit(JobType.TRIAGE, dataset_id=ds_id)
            job_queue.submit(JobType.ANOMALY, dataset_id=ds_id)
            job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=ds_id)
            job_queue.submit(JobType.IOC_EXTRACT, dataset_id=ds_id)
        logger.info(f"Queued processing pipeline for {len(to_reprocess)} datasets at startup (unprocessed total: {len(unprocessed_ids)})")
        async with async_session_factory() as update_db:
            from sqlalchemy import update
            from app.db.models import Dataset
            await update_db.execute(
                update(Dataset)
                .where(Dataset.id.in_(to_reprocess))
                .values(processing_status="processing")
            )
            await update_db.commit()
    else:
        logger.info("All datasets already processed - skipping startup pipeline")

    # Start load balancer health loop
    from app.services.load_balancer import lb
    await lb.start_health_loop(interval=30.0)
    logger.info("Load balancer health loop started")

    yield

    logger.info("Shutting down ...")
    from app.services.job_queue import job_queue as jq
    await jq.stop()
    logger.info("Job queue stopped")

    from app.services.load_balancer import lb as _lb
    await _lb.stop_health_loop()
    logger.info("Load balancer stopped")

=======
    yield
    logger.info("Shutting down …")
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
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
app.include_router(network_router)
<<<<<<< HEAD
app.include_router(mitre_router)
app.include_router(timeline_router)
app.include_router(playbooks_router)
app.include_router(searches_router)
app.include_router(stix_router)
=======
app.include_router(analysis_router)
app.include_router(cases_router)
app.include_router(alerts_router)
app.include_router(notebooks_router)
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2


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
<<<<<<< HEAD


@app.get("/health", tags=["health"])
async def health():
    return {
        "service": "ThreatHunt API",
        "version": settings.APP_VERSION,
        "status": "ok",
    }
=======
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

"""Async job queue for background AI tasks.

Manages triage, profiling, report generation, anomaly detection,
keyword scanning, IOC extraction, and data queries as trackable
jobs with status, progress, and cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    TRIAGE = "triage"
    HOST_PROFILE = "host_profile"
    REPORT = "report"
    ANOMALY = "anomaly"
    QUERY = "query"
    HOST_INVENTORY = "host_inventory"
    KEYWORD_SCAN = "keyword_scan"
    IOC_EXTRACT = "ioc_extract"


# Job types that form the automatic upload pipeline
PIPELINE_JOB_TYPES = frozenset({
    JobType.TRIAGE,
    JobType.ANOMALY,
    JobType.KEYWORD_SCAN,
    JobType.IOC_EXTRACT,
})


@dataclass
class Job:
    id: str
    job_type: JobType
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0          # 0-100
    message: str = ""
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    params: dict = field(default_factory=dict)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def elapsed_ms(self) -> int:
        end = self.completed_at or time.time()
        start = self.started_at or self.created_at
        return int((end - start) * 1000)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "progress": round(self.progress, 1),
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "params": self.params,
        }

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self):
        self._cancel_event.set()
        self.status = JobStatus.CANCELLED
        self.completed_at = time.time()
        self.message = "Cancelled by user"


class JobQueue:
    """In-memory async job queue with concurrency control."""

    def __init__(self, max_workers: int = 3):
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._max_workers = max_workers
        self._workers: list[asyncio.Task] = []
        self._handlers: dict[JobType, Callable] = {}
        self._started = False
        self._completion_callbacks: list[Callable[[Job], Coroutine]] = []
        self._cleanup_task: asyncio.Task | None = None

    def register_handler(self, job_type: JobType, handler: Callable[[Job], Coroutine]):
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for {job_type.value}")

    def on_completion(self, callback: Callable[[Job], Coroutine]):
        """Register a callback invoked after any job completes or fails."""
        self._completion_callbacks.append(callback)

    async def start(self):
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Job queue started with {self._max_workers} workers")

    async def stop(self):
        self._started = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        logger.info("Job queue stopped")

    def submit(self, job_type: JobType, **params) -> Job:
        # Soft backpressure: prefer dedupe over queue amplification
        dedupe_job = self._find_active_duplicate(job_type, params)
        if dedupe_job is not None:
            logger.info(
                f"Job deduped: reusing {dedupe_job.id} ({job_type.value}) params={params}"
            )
            return dedupe_job

        if self._queue.qsize() >= settings.JOB_QUEUE_MAX_BACKLOG:
            logger.warning(
                "Job queue backlog high (%d >= %d). Accepting job but system may be degraded.",
                self._queue.qsize(), settings.JOB_QUEUE_MAX_BACKLOG,
            )

        job = Job(id=str(uuid.uuid4()), job_type=job_type, params=params)
        self._jobs[job.id] = job
        self._queue.put_nowait(job.id)
        logger.info(f"Job submitted: {job.id} ({job_type.value}) params={params}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _find_active_duplicate(self, job_type: JobType, params: dict) -> Job | None:
        """Return queued/running job with same key workload to prevent duplicate storms."""
        key_fields = ["dataset_id", "hunt_id", "hostname", "question", "mode"]
        sig = tuple((k, params.get(k)) for k in key_fields if params.get(k) is not None)
        if not sig:
            return None
        for j in self._jobs.values():
            if j.job_type != job_type:
                continue
            if j.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                continue
            other_sig = tuple((k, j.params.get(k)) for k in key_fields if j.params.get(k) is not None)
            if sig == other_sig:
                return j
        return None

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.cancel()
        return True

    def list_jobs(self, status=None, job_type=None, limit=50) -> list[dict]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        return [j.to_dict() for j in jobs[:limit]]

    def get_stats(self) -> dict:
        by_status = {}
        for j in self._jobs.values():
            by_status[j.status.value] = by_status.get(j.status.value, 0) + 1
        return {
            "total": len(self._jobs),
            "queued": self._queue.qsize(),
            "by_status": by_status,
            "workers": self._max_workers,
            "active_workers": sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING),
        }

    def is_backlogged(self) -> bool:
        return self._queue.qsize() >= settings.JOB_QUEUE_MAX_BACKLOG

    def can_accept(self, reserve: int = 0) -> bool:
        return (self._queue.qsize() + max(0, reserve)) < settings.JOB_QUEUE_MAX_BACKLOG

    def cleanup(self, max_age_seconds: float = 3600):
        now = time.time()
        terminal_states = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
        to_remove = [
            jid for jid, j in self._jobs.items()
            if j.status in terminal_states and (now - j.created_at) > max_age_seconds
        ]

        # Also cap retained terminal jobs to avoid unbounded memory growth
        terminal_jobs = sorted(
            [j for j in self._jobs.values() if j.status in terminal_states],
            key=lambda j: j.created_at,
            reverse=True,
        )
        overflow = terminal_jobs[settings.JOB_QUEUE_RETAIN_COMPLETED :]
        to_remove.extend([j.id for j in overflow])

        removed = 0
        for jid in set(to_remove):
            if jid in self._jobs:
                del self._jobs[jid]
                removed += 1
        if removed:
            logger.info(f"Cleaned up {removed} old jobs")

    async def _cleanup_loop(self):
        interval = max(10, settings.JOB_QUEUE_CLEANUP_INTERVAL_SECONDS)
        while self._started:
            try:
                self.cleanup(max_age_seconds=settings.JOB_QUEUE_CLEANUP_MAX_AGE_SECONDS)
            except Exception as e:
                logger.warning(f"Job queue cleanup loop error: {e}")
            await asyncio.sleep(interval)

    def find_pipeline_jobs(self, dataset_id: str) -> list[Job]:
        """Find all pipeline jobs for a given dataset_id."""
        return [
            j for j in self._jobs.values()
            if j.job_type in PIPELINE_JOB_TYPES
            and j.params.get("dataset_id") == dataset_id
        ]

    async def _worker(self, worker_id: int):
        logger.info(f"Worker {worker_id} started")
        while self._started:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            job = self._jobs.get(job_id)
            if not job or job.is_cancelled:
                continue

            handler = self._handlers.get(job.job_type)
            if not handler:
                job.status = JobStatus.FAILED
                job.error = f"No handler for {job.job_type.value}"
                job.completed_at = time.time()
                logger.error(f"No handler for job type {job.job_type.value}")
                continue

            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            if job.progress <= 0:
                job.progress = 5.0
            job.message = "Running..."
            await _sync_processing_task(job)
            logger.info(f"Worker {worker_id}: executing {job.id} ({job.job_type.value})")

            try:
                result = await handler(job)
                if not job.is_cancelled:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                    job.result = result
                    job.message = "Completed"
                    job.completed_at = time.time()
                    logger.info(f"Worker {worker_id}: completed {job.id} in {job.elapsed_ms}ms")
            except Exception as e:
                if not job.is_cancelled:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.message = f"Failed: {e}"
                    job.completed_at = time.time()
                    logger.error(f"Worker {worker_id}: failed {job.id}: {e}", exc_info=True)

            if job.is_cancelled and not job.completed_at:
                job.completed_at = time.time()

            await _sync_processing_task(job)

            # Fire completion callbacks
            for cb in self._completion_callbacks:
                try:
                    await cb(job)
                except Exception as cb_err:
                    logger.error(f"Completion callback error: {cb_err}", exc_info=True)


async def _sync_processing_task(job: Job):
    """Persist latest job state into processing_tasks (if linked by job_id)."""
    from datetime import datetime, timezone
    from sqlalchemy import update

    try:
        from app.db import async_session_factory
        from app.db.models import ProcessingTask

        values = {
            "status": job.status.value,
            "progress": float(job.progress),
            "message": job.message,
            "error": job.error,
        }
        if job.started_at:
            values["started_at"] = datetime.fromtimestamp(job.started_at, tz=timezone.utc)
        if job.completed_at:
            values["completed_at"] = datetime.fromtimestamp(job.completed_at, tz=timezone.utc)

        async with async_session_factory() as db:
            await db.execute(
                update(ProcessingTask)
                .where(ProcessingTask.job_id == job.id)
                .values(**values)
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to sync processing task for job {job.id}: {e}")


# -- Singleton + job handlers --

job_queue = JobQueue(max_workers=5)


async def _handle_triage(job: Job):
    """Triage handler - chains HOST_PROFILE after completion."""
    from app.services.triage import triage_dataset
    dataset_id = job.params.get("dataset_id")
    job.message = f"Triaging dataset {dataset_id}"
    await triage_dataset(dataset_id)

    # Chain: trigger host profiling now that triage results exist
    from app.db import async_session_factory
    from app.db.models import Dataset
    from sqlalchemy import select
    try:
        async with async_session_factory() as db:
            ds = await db.execute(select(Dataset.hunt_id).where(Dataset.id == dataset_id))
            row = ds.first()
            hunt_id = row[0] if row else None
        if hunt_id:
            hp_job = job_queue.submit(JobType.HOST_PROFILE, hunt_id=hunt_id)
            try:
                from sqlalchemy import select
                from app.db.models import ProcessingTask
                async with async_session_factory() as db:
                    existing = await db.execute(
                        select(ProcessingTask.id).where(ProcessingTask.job_id == hp_job.id)
                    )
                    if existing.first() is None:
                        db.add(ProcessingTask(
                            hunt_id=hunt_id,
                            dataset_id=dataset_id,
                            job_id=hp_job.id,
                            stage="host_profile",
                            status="queued",
                            progress=0.0,
                            message="Queued",
                        ))
                        await db.commit()
            except Exception as persist_err:
                logger.warning(f"Failed to persist chained HOST_PROFILE task: {persist_err}")

            logger.info(f"Triage done for {dataset_id} - chained HOST_PROFILE for hunt {hunt_id}")
    except Exception as e:
        logger.warning(f"Failed to chain host profile after triage: {e}")

    return {"dataset_id": dataset_id}


async def _handle_host_profile(job: Job):
    from app.services.host_profiler import profile_all_hosts, profile_host
    hunt_id = job.params.get("hunt_id")
    hostname = job.params.get("hostname")
    if hostname:
        job.message = f"Profiling host {hostname}"
        await profile_host(hunt_id, hostname)
        return {"hostname": hostname}
    else:
        job.message = f"Profiling all hosts in hunt {hunt_id}"
        await profile_all_hosts(hunt_id)
        return {"hunt_id": hunt_id}


async def _handle_report(job: Job):
    from app.services.report_generator import generate_report
    hunt_id = job.params.get("hunt_id")
    job.message = f"Generating report for hunt {hunt_id}"
    report = await generate_report(hunt_id)
    return {"report_id": report.id if report else None}


async def _handle_anomaly(job: Job):
    from app.services.anomaly_detector import detect_anomalies
    dataset_id = job.params.get("dataset_id")
    k = job.params.get("k", 3)
    threshold = job.params.get("threshold", 0.35)
    job.message = f"Detecting anomalies in dataset {dataset_id}"
    results = await detect_anomalies(dataset_id, k=k, outlier_threshold=threshold)
    return {"count": len(results) if results else 0}


async def _handle_query(job: Job):
    from app.services.data_query import query_dataset
    dataset_id = job.params.get("dataset_id")
    question = job.params.get("question", "")
    mode = job.params.get("mode", "quick")
    job.message = f"Querying dataset {dataset_id}"
    answer = await query_dataset(dataset_id, question, mode)
    return {"answer": answer}


async def _handle_host_inventory(job: Job):
    from app.db import async_session_factory
    from app.services.host_inventory import build_host_inventory, inventory_cache

    hunt_id = job.params.get("hunt_id")
    if not hunt_id:
        raise ValueError("hunt_id required")

    inventory_cache.set_building(hunt_id)
    job.message = f"Building host inventory for hunt {hunt_id}"

    try:
        async with async_session_factory() as db:
            result = await build_host_inventory(hunt_id, db)
        inventory_cache.put(hunt_id, result)
        job.message = f"Built inventory: {result['stats']['total_hosts']} hosts"
        return {"hunt_id": hunt_id, "total_hosts": result["stats"]["total_hosts"]}
    except Exception:
        inventory_cache.clear_building(hunt_id)
        raise


async def _handle_keyword_scan(job: Job):
    """AUP keyword scan handler."""
    from app.db import async_session_factory
    from app.services.scanner import KeywordScanner, keyword_scan_cache

    dataset_id = job.params.get("dataset_id")
    job.message = f"Running AUP keyword scan on dataset {dataset_id}"

    async with async_session_factory() as db:
        scanner = KeywordScanner(db)
        result = await scanner.scan(dataset_ids=[dataset_id])

    # Cache dataset-only result for fast API reuse
    if dataset_id:
        keyword_scan_cache.put(dataset_id, result)

    hits = result.get("total_hits", 0)
    job.message = f"Keyword scan complete: {hits} hits"
    logger.info(f"Keyword scan for {dataset_id}: {hits} hits across {result.get('rows_scanned', 0)} rows")
    return {"dataset_id": dataset_id, "total_hits": hits, "rows_scanned": result.get("rows_scanned", 0)}


async def _handle_ioc_extract(job: Job):
    """IOC extraction handler."""
    from app.db import async_session_factory
    from app.services.ioc_extractor import extract_iocs_from_dataset

    dataset_id = job.params.get("dataset_id")
    job.message = f"Extracting IOCs from dataset {dataset_id}"

    async with async_session_factory() as db:
        iocs = await extract_iocs_from_dataset(dataset_id, db)

    total = sum(len(v) for v in iocs.values())
    job.message = f"IOC extraction complete: {total} IOCs found"
    logger.info(f"IOC extract for {dataset_id}: {total} IOCs")
    return {"dataset_id": dataset_id, "total_iocs": total, "breakdown": {k: len(v) for k, v in iocs.items()}}


async def _on_pipeline_job_complete(job: Job):
    """Update Dataset.processing_status when all pipeline jobs finish."""
    if job.job_type not in PIPELINE_JOB_TYPES:
        return

    dataset_id = job.params.get("dataset_id")
    if not dataset_id:
        return

    pipeline_jobs = job_queue.find_pipeline_jobs(dataset_id)
    if not pipeline_jobs:
        return

    all_done = all(
        j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
        for j in pipeline_jobs
    )
    if not all_done:
        return

    any_failed = any(j.status == JobStatus.FAILED for j in pipeline_jobs)
    new_status = "completed_with_errors" if any_failed else "completed"

    try:
        from app.db import async_session_factory
        from app.db.models import Dataset
        from sqlalchemy import update

        async with async_session_factory() as db:
            await db.execute(
                update(Dataset)
                .where(Dataset.id == dataset_id)
                .values(processing_status=new_status)
            )
            await db.commit()
        logger.info(f"Dataset {dataset_id} processing_status -> {new_status}")
    except Exception as e:
        logger.error(f"Failed to update processing_status for {dataset_id}: {e}")




async def reconcile_stale_processing_tasks() -> int:
    """Mark queued/running processing tasks from prior runs as failed."""
    from datetime import datetime, timezone
    from sqlalchemy import update

    try:
        from app.db import async_session_factory
        from app.db.models import ProcessingTask

        now = datetime.now(timezone.utc)
        async with async_session_factory() as db:
            result = await db.execute(
                update(ProcessingTask)
                .where(ProcessingTask.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    error="Recovered after service restart before task completion",
                    message="Recovered stale task after restart",
                    completed_at=now,
                )
            )
            await db.commit()
            updated = int(result.rowcount or 0)

        if updated:
            logger.warning(
                "Reconciled %d stale processing tasks (queued/running -> failed) during startup",
                updated,
            )
        return updated
    except Exception as e:
        logger.warning(f"Failed to reconcile stale processing tasks: {e}")
        return 0


def register_all_handlers():
    """Register all job handlers and completion callbacks."""
    job_queue.register_handler(JobType.TRIAGE, _handle_triage)
    job_queue.register_handler(JobType.HOST_PROFILE, _handle_host_profile)
    job_queue.register_handler(JobType.REPORT, _handle_report)
    job_queue.register_handler(JobType.ANOMALY, _handle_anomaly)
    job_queue.register_handler(JobType.QUERY, _handle_query)
    job_queue.register_handler(JobType.HOST_INVENTORY, _handle_host_inventory)
    job_queue.register_handler(JobType.KEYWORD_SCAN, _handle_keyword_scan)
    job_queue.register_handler(JobType.IOC_EXTRACT, _handle_ioc_extract)
    job_queue.on_completion(_on_pipeline_job_complete)

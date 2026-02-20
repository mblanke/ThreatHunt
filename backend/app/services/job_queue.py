"""Async job queue for background AI tasks.

Manages triage, profiling, report generation, anomaly detection,
and data queries as trackable jobs with status, progress, and
cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

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
    """In-memory async job queue with concurrency control.

    Jobs are tracked by ID and can be listed, polled, or cancelled.
    A configurable number of workers process jobs from the queue.
    """

    def __init__(self, max_workers: int = 3):
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._max_workers = max_workers
        self._workers: list[asyncio.Task] = []
        self._handlers: dict[JobType, Callable] = {}
        self._started = False

    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[[Job], Coroutine],
    ):
        """Register an async handler for a job type.

        Handler signature: async def handler(job: Job) -> Any
        The handler can update job.progress and job.message during execution.
        It should check job.is_cancelled periodically and return early.
        """
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for {job_type.value}")

    async def start(self):
        """Start worker tasks."""
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info(f"Job queue started with {self._max_workers} workers")

    async def stop(self):
        """Stop all workers."""
        self._started = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Job queue stopped")

    def submit(self, job_type: JobType, **params) -> Job:
        """Submit a new job. Returns the Job object immediately."""
        job = Job(
            id=str(uuid.uuid4()),
            job_type=job_type,
            params=params,
        )
        self._jobs[job.id] = job
        self._queue.put_nowait(job.id)
        logger.info(f"Job submitted: {job.id} ({job_type.value}) params={params}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.cancel()
        return True

    def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List jobs, newest first."""
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        return [j.to_dict() for j in jobs[:limit]]

    def get_stats(self) -> dict:
        """Get queue statistics."""
        by_status = {}
        for j in self._jobs.values():
            by_status[j.status.value] = by_status.get(j.status.value, 0) + 1
        return {
            "total": len(self._jobs),
            "queued": self._queue.qsize(),
            "by_status": by_status,
            "workers": self._max_workers,
            "active_workers": sum(
                1 for j in self._jobs.values() if j.status == JobStatus.RUNNING
            ),
        }

    def cleanup(self, max_age_seconds: float = 3600):
        """Remove old completed/failed/cancelled jobs."""
        now = time.time()
        to_remove = [
            jid for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
            and (now - j.created_at) > max_age_seconds
        ]
        for jid in to_remove:
            del self._jobs[jid]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")

    async def _worker(self, worker_id: int):
        """Worker loop: pull jobs from queue and execute handlers."""
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
            job.message = "Running..."
            logger.info(f"Worker {worker_id}: executing {job.id} ({job.job_type.value})")

            try:
                result = await handler(job)
                if not job.is_cancelled:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                    job.result = result
                    job.message = "Completed"
                    job.completed_at = time.time()
                    logger.info(
                        f"Worker {worker_id}: completed {job.id} "
                        f"in {job.elapsed_ms}ms"
                    )
            except Exception as e:
                if not job.is_cancelled:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.message = f"Failed: {e}"
                    job.completed_at = time.time()
                    logger.error(
                        f"Worker {worker_id}: failed {job.id}: {e}",
                        exc_info=True,
                    )


#  Singleton + job handlers 

job_queue = JobQueue(max_workers=3)


async def _handle_triage(job: Job):
    """Triage handler."""
    from app.services.triage import triage_dataset
    dataset_id = job.params.get("dataset_id")
    job.message = f"Triaging dataset {dataset_id}"
    results = await triage_dataset(dataset_id)
    return {"count": len(results) if results else 0}


async def _handle_host_profile(job: Job):
    """Host profiling handler."""
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
    """Report generation handler."""
    from app.services.report_generator import generate_report
    hunt_id = job.params.get("hunt_id")
    job.message = f"Generating report for hunt {hunt_id}"
    report = await generate_report(hunt_id)
    return {"report_id": report.id if report else None}


async def _handle_anomaly(job: Job):
    """Anomaly detection handler."""
    from app.services.anomaly_detector import detect_anomalies
    dataset_id = job.params.get("dataset_id")
    k = job.params.get("k", 3)
    threshold = job.params.get("threshold", 0.35)
    job.message = f"Detecting anomalies in dataset {dataset_id}"
    results = await detect_anomalies(dataset_id, k=k, outlier_threshold=threshold)
    return {"count": len(results) if results else 0}


async def _handle_query(job: Job):
    """Data query handler (non-streaming)."""
    from app.services.data_query import query_dataset
    dataset_id = job.params.get("dataset_id")
    question = job.params.get("question", "")
    mode = job.params.get("mode", "quick")
    job.message = f"Querying dataset {dataset_id}"
    answer = await query_dataset(dataset_id, question, mode)
    return {"answer": answer}


def register_all_handlers():
    """Register all job handlers."""
    job_queue.register_handler(JobType.TRIAGE, _handle_triage)
    job_queue.register_handler(JobType.HOST_PROFILE, _handle_host_profile)
    job_queue.register_handler(JobType.REPORT, _handle_report)
    job_queue.register_handler(JobType.ANOMALY, _handle_anomaly)
    job_queue.register_handler(JobType.QUERY, _handle_query)
"""Analysis API routes - triage, host profiles, reports, IOC extraction,
host grouping, anomaly detection, data query (SSE), and job management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import HostProfile, HuntReport, TriageResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# --- Response models ---

class TriageResultResponse(BaseModel):
    id: str
    dataset_id: str
    row_start: int
    row_end: int
    risk_score: float
    verdict: str
    findings: list | None = None
    suspicious_indicators: list | None = None
    mitre_techniques: list | None = None
    model_used: str | None = None
    node_used: str | None = None

    class Config:
        from_attributes = True


class HostProfileResponse(BaseModel):
    id: str
    hunt_id: str
    hostname: str
    fqdn: str | None = None
    risk_score: float
    risk_level: str
    artifact_summary: dict | None = None
    timeline_summary: str | None = None
    suspicious_findings: list | None = None
    mitre_techniques: list | None = None
    llm_analysis: str | None = None
    model_used: str | None = None

    class Config:
        from_attributes = True


class HuntReportResponse(BaseModel):
    id: str
    hunt_id: str
    status: str
    exec_summary: str | None = None
    full_report: str | None = None
    findings: list | None = None
    recommendations: list | None = None
    mitre_mapping: dict | None = None
    ioc_table: list | None = None
    host_risk_summary: list | None = None
    models_used: list | None = None
    generation_time_ms: int | None = None

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    question: str
    mode: str = "quick"  # quick or deep


# --- Triage endpoints ---

@router.get("/triage/{dataset_id}", response_model=list[TriageResultResponse])
async def get_triage_results(
    dataset_id: str,
    min_risk: float = Query(0.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TriageResult)
        .where(TriageResult.dataset_id == dataset_id)
        .where(TriageResult.risk_score >= min_risk)
        .order_by(TriageResult.risk_score.desc())
    )
    return result.scalars().all()


@router.post("/triage/{dataset_id}")
async def trigger_triage(
    dataset_id: str,
    background_tasks: BackgroundTasks,
):
    async def _run():
        from app.services.triage import triage_dataset
        await triage_dataset(dataset_id)

    background_tasks.add_task(_run)
    return {"status": "triage_started", "dataset_id": dataset_id}


# --- Host profile endpoints ---

@router.get("/profiles/{hunt_id}", response_model=list[HostProfileResponse])
async def get_host_profiles(
    hunt_id: str,
    min_risk: float = Query(0.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HostProfile)
        .where(HostProfile.hunt_id == hunt_id)
        .where(HostProfile.risk_score >= min_risk)
        .order_by(HostProfile.risk_score.desc())
    )
    return result.scalars().all()


@router.post("/profiles/{hunt_id}")
async def trigger_all_profiles(
    hunt_id: str,
    background_tasks: BackgroundTasks,
):
    async def _run():
        from app.services.host_profiler import profile_all_hosts
        await profile_all_hosts(hunt_id)

    background_tasks.add_task(_run)
    return {"status": "profiling_started", "hunt_id": hunt_id}


@router.post("/profiles/{hunt_id}/{hostname}")
async def trigger_single_profile(
    hunt_id: str,
    hostname: str,
    background_tasks: BackgroundTasks,
):
    async def _run():
        from app.services.host_profiler import profile_host
        await profile_host(hunt_id, hostname)

    background_tasks.add_task(_run)
    return {"status": "profiling_started", "hunt_id": hunt_id, "hostname": hostname}


# --- Report endpoints ---

@router.get("/reports/{hunt_id}", response_model=list[HuntReportResponse])
async def list_reports(
    hunt_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HuntReport)
        .where(HuntReport.hunt_id == hunt_id)
        .order_by(HuntReport.created_at.desc())
    )
    return result.scalars().all()


@router.get("/reports/{hunt_id}/{report_id}", response_model=HuntReportResponse)
async def get_report(
    hunt_id: str,
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HuntReport)
        .where(HuntReport.id == report_id)
        .where(HuntReport.hunt_id == hunt_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/reports/{hunt_id}/generate")
async def trigger_report(
    hunt_id: str,
    background_tasks: BackgroundTasks,
):
    async def _run():
        from app.services.report_generator import generate_report
        await generate_report(hunt_id)

    background_tasks.add_task(_run)
    return {"status": "report_generation_started", "hunt_id": hunt_id}


# --- IOC extraction endpoints ---

@router.get("/iocs/{dataset_id}")
async def extract_iocs(
    dataset_id: str,
    max_rows: int = Query(5000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
):
    """Extract IOCs (IPs, domains, hashes, etc.) from dataset rows."""
    from app.services.ioc_extractor import extract_iocs_from_dataset
    iocs = await extract_iocs_from_dataset(dataset_id, db, max_rows=max_rows)
    total = sum(len(v) for v in iocs.values())
    return {"dataset_id": dataset_id, "iocs": iocs, "total": total}


# --- Host grouping endpoints ---

@router.get("/hosts/{hunt_id}")
async def get_host_groups(
    hunt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Group data by hostname across all datasets in a hunt."""
    from app.services.ioc_extractor import extract_host_groups
    groups = await extract_host_groups(hunt_id, db)
    return {"hunt_id": hunt_id, "hosts": groups}


# --- Anomaly detection endpoints ---

@router.get("/anomalies/{dataset_id}")
async def get_anomalies(
    dataset_id: str,
    outliers_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Get anomaly detection results for a dataset."""
    from app.db.models import AnomalyResult
    stmt = select(AnomalyResult).where(AnomalyResult.dataset_id == dataset_id)
    if outliers_only:
        stmt = stmt.where(AnomalyResult.is_outlier == True)
    stmt = stmt.order_by(AnomalyResult.anomaly_score.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "dataset_id": r.dataset_id,
            "row_id": r.row_id,
            "anomaly_score": r.anomaly_score,
            "distance_from_centroid": r.distance_from_centroid,
            "cluster_id": r.cluster_id,
            "is_outlier": r.is_outlier,
            "explanation": r.explanation,
        }
        for r in rows
    ]


@router.post("/anomalies/{dataset_id}")
async def trigger_anomaly_detection(
    dataset_id: str,
    k: int = Query(3, ge=2, le=20),
    threshold: float = Query(0.35, ge=0.1, le=0.9),
    background_tasks: BackgroundTasks = None,
):
    """Trigger embedding-based anomaly detection on a dataset."""
    async def _run():
        from app.services.anomaly_detector import detect_anomalies
        await detect_anomalies(dataset_id, k=k, outlier_threshold=threshold)

    if background_tasks:
        background_tasks.add_task(_run)
        return {"status": "anomaly_detection_started", "dataset_id": dataset_id}
    else:
        from app.services.anomaly_detector import detect_anomalies
        results = await detect_anomalies(dataset_id, k=k, outlier_threshold=threshold)
        return {"status": "complete", "dataset_id": dataset_id, "count": len(results)}


# --- Natural language data query (SSE streaming) ---

@router.post("/query/{dataset_id}")
async def query_dataset_endpoint(
    dataset_id: str,
    body: QueryRequest,
):
    """Ask a natural language question about a dataset.

    Returns an SSE stream with token-by-token LLM response.
    Event types: status, metadata, token, error, done
    """
    from app.services.data_query import query_dataset_stream

    return StreamingResponse(
        query_dataset_stream(dataset_id, body.question, body.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query/{dataset_id}/sync")
async def query_dataset_sync(
    dataset_id: str,
    body: QueryRequest,
):
    """Non-streaming version of data query."""
    from app.services.data_query import query_dataset

    try:
        answer = await query_dataset(dataset_id, body.question, body.mode)
        return {"dataset_id": dataset_id, "question": body.question, "answer": answer, "mode": body.mode}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Job queue endpoints ---

@router.get("/jobs")
async def list_jobs(
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List all tracked jobs."""
    from app.services.job_queue import job_queue, JobStatus, JobType

    s = JobStatus(status) if status else None
    t = JobType(job_type) if job_type else None
    jobs = job_queue.list_jobs(status=s, job_type=t, limit=limit)
    stats = job_queue.get_stats()
    return {"jobs": jobs, "stats": stats}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get status of a specific job."""
    from app.services.job_queue import job_queue

    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    from app.services.job_queue import job_queue

    if job_queue.cancel_job(job_id):
        return {"status": "cancelled", "job_id": job_id}
    raise HTTPException(status_code=400, detail="Job cannot be cancelled (already complete or not found)")


@router.post("/jobs/submit/{job_type}")
async def submit_job(
    job_type: str,
    params: dict = {},
):
    """Submit a new job to the queue.

    Job types: triage, host_profile, report, anomaly, query
    Params vary by type (e.g., dataset_id, hunt_id, question, mode).
    """
    from app.services.job_queue import job_queue, JobType

    try:
        jt = JobType(job_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job_type: {job_type}. Valid: {[t.value for t in JobType]}",
        )

    job = job_queue.submit(jt, **params)
    return {"job_id": job.id, "status": job.status.value, "job_type": job_type}


# --- Load balancer status ---

@router.get("/lb/status")
async def lb_status():
    """Get load balancer status for both nodes."""
    from app.services.load_balancer import lb
    return lb.get_status()


@router.post("/lb/check")
async def lb_health_check():
    """Force a health check of both nodes."""
    from app.services.load_balancer import lb
    await lb.check_health()
    return lb.get_status()
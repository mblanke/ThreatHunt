"""API routes for process trees, storyline graphs, risk scoring, LLM analysis, timeline, and field stats."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.repositories.datasets import DatasetRepository
from app.services.process_tree import (
    build_process_tree,
    build_storyline,
    compute_risk_scores,
    _fetch_rows,
)
from app.services.llm_analysis import (
    AnalysisRequest,
    AnalysisResult,
    run_llm_analysis,
)
from app.services.timeline import (
    build_timeline_bins,
    compute_field_stats,
    search_rows,
)
from app.services.mitre import (
    map_to_attack,
    build_knowledge_graph,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ── Response models ───────────────────────────────────────────────────


class ProcessTreeResponse(BaseModel):
    trees: list[dict] = Field(default_factory=list)
    total_processes: int = 0


class StorylineResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class RiskHostEntry(BaseModel):
    hostname: str
    score: int = 0
    signals: list[str] = Field(default_factory=list)
    event_count: int = 0
    process_count: int = 0
    network_count: int = 0
    file_count: int = 0


class RiskSummaryResponse(BaseModel):
    hosts: list[RiskHostEntry] = Field(default_factory=list)
    overall_score: int = 0
    total_events: int = 0
    severity_breakdown: dict[str, int] = Field(default_factory=dict)


# ── Routes ────────────────────────────────────────────────────────────


@router.get(
    "/process-tree",
    response_model=ProcessTreeResponse,
    summary="Build process tree from dataset rows",
    description=(
        "Extracts parent→child process relationships from dataset rows "
        "and returns a hierarchical forest of process nodes."
    ),
)
async def get_process_tree(
    dataset_id: str | None = Query(None, description="Dataset ID"),
    hunt_id: str | None = Query(None, description="Hunt ID (scans all datasets in hunt)"),
    hostname: str | None = Query(None, description="Filter by hostname"),
    db: AsyncSession = Depends(get_db),
):
    """Return process tree(s) for a dataset or hunt."""
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")

    trees = await build_process_tree(
        db, dataset_id=dataset_id, hunt_id=hunt_id, hostname_filter=hostname,
    )

    # Count total processes recursively
    def _count(node: dict) -> int:
        return 1 + sum(_count(c) for c in node.get("children", []))

    total = sum(_count(t) for t in trees)

    return ProcessTreeResponse(trees=trees, total_processes=total)


@router.get(
    "/storyline",
    response_model=StorylineResponse,
    summary="Build CrowdStrike-style storyline attack graph",
    description=(
        "Creates a Cytoscape-compatible graph of events connected by "
        "process lineage (spawned) and temporal sequence within each host."
    ),
)
async def get_storyline(
    dataset_id: str | None = Query(None, description="Dataset ID"),
    hunt_id: str | None = Query(None, description="Hunt ID (scans all datasets in hunt)"),
    hostname: str | None = Query(None, description="Filter by hostname"),
    db: AsyncSession = Depends(get_db),
):
    """Return a storyline graph for a dataset or hunt."""
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")

    result = await build_storyline(
        db, dataset_id=dataset_id, hunt_id=hunt_id, hostname_filter=hostname,
    )

    return StorylineResponse(**result)


@router.get(
    "/risk-summary",
    response_model=RiskSummaryResponse,
    summary="Compute risk scores per host",
    description=(
        "Analyzes dataset rows for suspicious patterns (encoded PowerShell, "
        "credential dumping, lateral movement) and produces per-host risk scores."
    ),
)
async def get_risk_summary(
    hunt_id: str | None = Query(None, description="Hunt ID"),
    db: AsyncSession = Depends(get_db),
):
    """Return risk scores for all hosts in a hunt."""
    result = await compute_risk_scores(db, hunt_id=hunt_id)
    return RiskSummaryResponse(**result)


# ── LLM Analysis ─────────────────────────────────────────────────────


@router.post(
    "/llm-analyze",
    response_model=AnalysisResult,
    summary="Run LLM-powered threat analysis on dataset",
    description=(
        "Loads dataset rows server-side, builds a summary, and sends to "
        "Wile (deep analysis) or Roadrunner (quick) for comprehensive "
        "threat analysis. Returns structured findings, IOCs, MITRE techniques."
    ),
)
async def llm_analyze(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run LLM analysis on a dataset or hunt."""
    if not request.dataset_id and not request.hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")

    # Load rows
    rows_objs = await _fetch_rows(
        db,
        dataset_id=request.dataset_id,
        hunt_id=request.hunt_id,
        limit=2000,
    )

    if not rows_objs:
        raise HTTPException(status_code=404, detail="No rows found for analysis")

    # Extract data dicts
    rows = [r.normalized_data or r.data for r in rows_objs]

    # Get dataset name
    ds_name = "hunt datasets"
    if request.dataset_id:
        repo = DatasetRepository(db)
        ds = await repo.get_dataset(request.dataset_id)
        if ds:
            ds_name = ds.name

    result = await run_llm_analysis(rows, request, dataset_name=ds_name)
    return result


# ── Timeline ──────────────────────────────────────────────────────────


@router.get(
    "/timeline",
    summary="Get event timeline histogram bins",
)
async def get_timeline(
    dataset_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    bins: int = Query(60, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
):
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")
    return await build_timeline_bins(db, dataset_id=dataset_id, hunt_id=hunt_id, bins=bins)


@router.get(
    "/field-stats",
    summary="Get per-field value distributions",
)
async def get_field_stats(
    dataset_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    fields: str | None = Query(None, description="Comma-separated field names"),
    top_n: int = Query(20, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    return await compute_field_stats(
        db, dataset_id=dataset_id, hunt_id=hunt_id,
        fields=field_list, top_n=top_n,
    )


class SearchRequest(BaseModel):
    dataset_id: Optional[str] = None
    hunt_id: Optional[str] = None
    query: str = ""
    filters: dict[str, str] = Field(default_factory=dict)
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    limit: int = 500
    offset: int = 0


@router.post(
    "/search",
    summary="Search and filter dataset rows",
)
async def search_dataset_rows(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    if not request.dataset_id and not request.hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")
    return await search_rows(
        db,
        dataset_id=request.dataset_id,
        hunt_id=request.hunt_id,
        query=request.query,
        filters=request.filters,
        time_start=request.time_start,
        time_end=request.time_end,
        limit=request.limit,
        offset=request.offset,
    )


# ── MITRE ATT&CK ─────────────────────────────────────────────────────


@router.get(
    "/mitre-map",
    summary="Map dataset events to MITRE ATT&CK techniques",
)
async def get_mitre_map(
    dataset_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")
    return await map_to_attack(db, dataset_id=dataset_id, hunt_id=hunt_id)


@router.get(
    "/knowledge-graph",
    summary="Build entity-technique knowledge graph",
)
async def get_knowledge_graph(
    dataset_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
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

    if not job_queue.can_accept():
        raise HTTPException(status_code=429, detail="Job queue is busy. Retry shortly.")
    if not job_queue.can_accept():
        raise HTTPException(status_code=429, detail="Job queue is busy. Retry shortly.")
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
=======
    if not dataset_id and not hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")
    return await build_knowledge_graph(db, dataset_id=dataset_id, hunt_id=hunt_id)
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

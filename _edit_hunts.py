from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/hunts.py')
new='''"""API routes for hunt management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Hunt, Dataset
from app.services.job_queue import job_queue
from app.services.host_inventory import inventory_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hunts", tags=["hunts"])


class HuntCreate(BaseModel):
    name: str = Field(..., max_length=256)
    description: str | None = None


class HuntUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class HuntResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    owner_id: str | None
    created_at: str
    updated_at: str
    dataset_count: int = 0
    hypothesis_count: int = 0


class HuntListResponse(BaseModel):
    hunts: list[HuntResponse]
    total: int


class HuntProgressResponse(BaseModel):
    hunt_id: str
    status: str
    progress_percent: float
    dataset_total: int
    dataset_completed: int
    dataset_processing: int
    dataset_errors: int
    active_jobs: int
    queued_jobs: int
    network_status: str
    stages: dict


@router.post("", response_model=HuntResponse, summary="Create a new hunt")
async def create_hunt(body: HuntCreate, db: AsyncSession = Depends(get_db)):
    hunt = Hunt(name=body.name, description=body.description)
    db.add(hunt)
    await db.flush()
    return HuntResponse(
        id=hunt.id,
        name=hunt.name,
        description=hunt.description,
        status=hunt.status,
        owner_id=hunt.owner_id,
        created_at=hunt.created_at.isoformat(),
        updated_at=hunt.updated_at.isoformat(),
    )


@router.get("", response_model=HuntListResponse, summary="List hunts")
async def list_hunts(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Hunt).order_by(Hunt.updated_at.desc())
    if status:
        stmt = stmt.where(Hunt.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    hunts = result.scalars().all()

    count_stmt = select(func.count(Hunt.id))
    if status:
        count_stmt = count_stmt.where(Hunt.status == status)
    total = (await db.execute(count_stmt)).scalar_one()

    return HuntListResponse(
        hunts=[
            HuntResponse(
                id=h.id,
                name=h.name,
                description=h.description,
                status=h.status,
                owner_id=h.owner_id,
                created_at=h.created_at.isoformat(),
                updated_at=h.updated_at.isoformat(),
                dataset_count=len(h.datasets) if h.datasets else 0,
                hypothesis_count=len(h.hypotheses) if h.hypotheses else 0,
            )
            for h in hunts
        ],
        total=total,
    )


@router.get("/{hunt_id}", response_model=HuntResponse, summary="Get hunt details")
async def get_hunt(hunt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    return HuntResponse(
        id=hunt.id,
        name=hunt.name,
        description=hunt.description,
        status=hunt.status,
        owner_id=hunt.owner_id,
        created_at=hunt.created_at.isoformat(),
        updated_at=hunt.updated_at.isoformat(),
        dataset_count=len(hunt.datasets) if hunt.datasets else 0,
        hypothesis_count=len(hunt.hypotheses) if hunt.hypotheses else 0,
    )


@router.get("/{hunt_id}/progress", response_model=HuntProgressResponse, summary="Get hunt processing progress")
async def get_hunt_progress(hunt_id: str, db: AsyncSession = Depends(get_db)):
    hunt = await db.get(Hunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")

    ds_rows = await db.execute(
        select(Dataset.id, Dataset.processing_status)
        .where(Dataset.hunt_id == hunt_id)
    )
    datasets = ds_rows.all()
    dataset_ids = {row[0] for row in datasets}

    dataset_total = len(datasets)
    dataset_completed = sum(1 for _, st in datasets if st == "completed")
    dataset_errors = sum(1 for _, st in datasets if st == "completed_with_errors")
    dataset_processing = max(0, dataset_total - dataset_completed - dataset_errors)

    jobs = job_queue.list_jobs(limit=5000)
    relevant_jobs = [
        j for j in jobs
        if j.get("params", {}).get("hunt_id") == hunt_id
        or j.get("params", {}).get("dataset_id") in dataset_ids
    ]
    active_jobs = sum(1 for j in relevant_jobs if j.get("status") == "running")
    queued_jobs = sum(1 for j in relevant_jobs if j.get("status") == "queued")

    if inventory_cache.get(hunt_id) is not None:
        network_status = "ready"
        network_ratio = 1.0
    elif inventory_cache.is_building(hunt_id):
        network_status = "building"
        network_ratio = 0.5
    else:
        network_status = "none"
        network_ratio = 0.0

    dataset_ratio = ((dataset_completed + dataset_errors) / dataset_total) if dataset_total > 0 else 1.0
    overall_ratio = min(1.0, (dataset_ratio * 0.85) + (network_ratio * 0.15))
    progress_percent = round(overall_ratio * 100.0, 1)

    status = "ready"
    if dataset_total == 0:
        status = "idle"
    elif progress_percent < 100:
        status = "processing"

    stages = {
        "datasets": {
            "total": dataset_total,
            "completed": dataset_completed,
            "processing": dataset_processing,
            "errors": dataset_errors,
            "percent": round(dataset_ratio * 100.0, 1),
        },
        "network": {
            "status": network_status,
            "percent": round(network_ratio * 100.0, 1),
        },
        "jobs": {
            "active": active_jobs,
            "queued": queued_jobs,
            "total_seen": len(relevant_jobs),
        },
    }

    return HuntProgressResponse(
        hunt_id=hunt_id,
        status=status,
        progress_percent=progress_percent,
        dataset_total=dataset_total,
        dataset_completed=dataset_completed,
        dataset_processing=dataset_processing,
        dataset_errors=dataset_errors,
        active_jobs=active_jobs,
        queued_jobs=queued_jobs,
        network_status=network_status,
        stages=stages,
    )


@router.put("/{hunt_id}", response_model=HuntResponse, summary="Update a hunt")
async def update_hunt(
    hunt_id: str, body: HuntUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    if body.name is not None:
        hunt.name = body.name
    if body.description is not None:
        hunt.description = body.description
    if body.status is not None:
        hunt.status = body.status
    await db.flush()
    return HuntResponse(
        id=hunt.id,
        name=hunt.name,
        description=hunt.description,
        status=hunt.status,
        owner_id=hunt.owner_id,
        created_at=hunt.created_at.isoformat(),
        updated_at=hunt.updated_at.isoformat(),
    )


@router.delete("/{hunt_id}", summary="Delete a hunt")
async def delete_hunt(hunt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    await db.delete(hunt)
    return {"message": "Hunt deleted", "id": hunt_id}
'''
p.write_text(new,encoding='utf-8')
print('updated hunts.py')

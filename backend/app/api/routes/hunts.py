"""API routes for hunt management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Hunt, Conversation, Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hunts", tags=["hunts"])


# ── Models ────────────────────────────────────────────────────────────


class HuntCreate(BaseModel):
    name: str = Field(..., max_length=256)
    description: str | None = None


class HuntUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None  # active | closed | archived


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


# ── Routes ────────────────────────────────────────────────────────────


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

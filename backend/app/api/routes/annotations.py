"""API routes for annotations and hypotheses."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Annotation, Hypothesis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["annotations"])


# ── Annotation models ─────────────────────────────────────────────────


class AnnotationCreate(BaseModel):
    row_id: int | None = None
    dataset_id: str | None = None
    text: str = Field(..., max_length=2000)
    severity: str = Field(default="info")  # info|low|medium|high|critical
    tag: str | None = None  # suspicious|benign|needs-review
    highlight_color: str | None = None


class AnnotationUpdate(BaseModel):
    text: str | None = None
    severity: str | None = None
    tag: str | None = None
    highlight_color: str | None = None


class AnnotationResponse(BaseModel):
    id: str
    row_id: int | None
    dataset_id: str | None
    author_id: str | None
    text: str
    severity: str
    tag: str | None
    highlight_color: str | None
    created_at: str
    updated_at: str


class AnnotationListResponse(BaseModel):
    annotations: list[AnnotationResponse]
    total: int


# ── Hypothesis models ─────────────────────────────────────────────────


class HypothesisCreate(BaseModel):
    hunt_id: str | None = None
    title: str = Field(..., max_length=256)
    description: str | None = None
    mitre_technique: str | None = None
    status: str = Field(default="draft")


class HypothesisUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    mitre_technique: str | None = None
    status: str | None = None  # draft|active|confirmed|rejected
    evidence_row_ids: list[int] | None = None
    evidence_notes: str | None = None


class HypothesisResponse(BaseModel):
    id: str
    hunt_id: str | None
    title: str
    description: str | None
    mitre_technique: str | None
    status: str
    evidence_row_ids: list | None
    evidence_notes: str | None
    created_at: str
    updated_at: str


class HypothesisListResponse(BaseModel):
    hypotheses: list[HypothesisResponse]
    total: int


# ── Annotation routes ─────────────────────────────────────────────────


ann_router = APIRouter(prefix="/api/annotations")


@ann_router.post("", response_model=AnnotationResponse, summary="Create annotation")
async def create_annotation(body: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    ann = Annotation(
        row_id=body.row_id,
        dataset_id=body.dataset_id,
        text=body.text,
        severity=body.severity,
        tag=body.tag,
        highlight_color=body.highlight_color,
    )
    db.add(ann)
    await db.flush()
    return AnnotationResponse(
        id=ann.id, row_id=ann.row_id, dataset_id=ann.dataset_id,
        author_id=ann.author_id, text=ann.text, severity=ann.severity,
        tag=ann.tag, highlight_color=ann.highlight_color,
        created_at=ann.created_at.isoformat(), updated_at=ann.updated_at.isoformat(),
    )


@ann_router.get("", response_model=AnnotationListResponse, summary="List annotations")
async def list_annotations(
    dataset_id: str | None = Query(None),
    row_id: int | None = Query(None),
    tag: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Annotation).order_by(Annotation.created_at.desc())
    if dataset_id:
        stmt = stmt.where(Annotation.dataset_id == dataset_id)
    if row_id:
        stmt = stmt.where(Annotation.row_id == row_id)
    if tag:
        stmt = stmt.where(Annotation.tag == tag)
    if severity:
        stmt = stmt.where(Annotation.severity == severity)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    annotations = result.scalars().all()

    count_stmt = select(func.count(Annotation.id))
    if dataset_id:
        count_stmt = count_stmt.where(Annotation.dataset_id == dataset_id)
    total = (await db.execute(count_stmt)).scalar_one()

    return AnnotationListResponse(
        annotations=[
            AnnotationResponse(
                id=a.id, row_id=a.row_id, dataset_id=a.dataset_id,
                author_id=a.author_id, text=a.text, severity=a.severity,
                tag=a.tag, highlight_color=a.highlight_color,
                created_at=a.created_at.isoformat(), updated_at=a.updated_at.isoformat(),
            )
            for a in annotations
        ],
        total=total,
    )


@ann_router.put("/{annotation_id}", response_model=AnnotationResponse, summary="Update annotation")
async def update_annotation(
    annotation_id: str, body: AnnotationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    if body.text is not None:
        ann.text = body.text
    if body.severity is not None:
        ann.severity = body.severity
    if body.tag is not None:
        ann.tag = body.tag
    if body.highlight_color is not None:
        ann.highlight_color = body.highlight_color
    await db.flush()
    return AnnotationResponse(
        id=ann.id, row_id=ann.row_id, dataset_id=ann.dataset_id,
        author_id=ann.author_id, text=ann.text, severity=ann.severity,
        tag=ann.tag, highlight_color=ann.highlight_color,
        created_at=ann.created_at.isoformat(), updated_at=ann.updated_at.isoformat(),
    )


@ann_router.delete("/{annotation_id}", summary="Delete annotation")
async def delete_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await db.delete(ann)
    return {"message": "Annotation deleted", "id": annotation_id}


# ── Hypothesis routes ─────────────────────────────────────────────────


hyp_router = APIRouter(prefix="/api/hypotheses")


@hyp_router.post("", response_model=HypothesisResponse, summary="Create hypothesis")
async def create_hypothesis(body: HypothesisCreate, db: AsyncSession = Depends(get_db)):
    hyp = Hypothesis(
        hunt_id=body.hunt_id,
        title=body.title,
        description=body.description,
        mitre_technique=body.mitre_technique,
        status=body.status,
    )
    db.add(hyp)
    await db.flush()
    return HypothesisResponse(
        id=hyp.id, hunt_id=hyp.hunt_id, title=hyp.title,
        description=hyp.description, mitre_technique=hyp.mitre_technique,
        status=hyp.status, evidence_row_ids=hyp.evidence_row_ids,
        evidence_notes=hyp.evidence_notes,
        created_at=hyp.created_at.isoformat(), updated_at=hyp.updated_at.isoformat(),
    )


@hyp_router.get("", response_model=HypothesisListResponse, summary="List hypotheses")
async def list_hypotheses(
    hunt_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Hypothesis).order_by(Hypothesis.updated_at.desc())
    if hunt_id:
        stmt = stmt.where(Hypothesis.hunt_id == hunt_id)
    if status:
        stmt = stmt.where(Hypothesis.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    hyps = result.scalars().all()

    count_stmt = select(func.count(Hypothesis.id))
    if hunt_id:
        count_stmt = count_stmt.where(Hypothesis.hunt_id == hunt_id)
    total = (await db.execute(count_stmt)).scalar_one()

    return HypothesisListResponse(
        hypotheses=[
            HypothesisResponse(
                id=h.id, hunt_id=h.hunt_id, title=h.title,
                description=h.description, mitre_technique=h.mitre_technique,
                status=h.status, evidence_row_ids=h.evidence_row_ids,
                evidence_notes=h.evidence_notes,
                created_at=h.created_at.isoformat(), updated_at=h.updated_at.isoformat(),
            )
            for h in hyps
        ],
        total=total,
    )


@hyp_router.get("/{hypothesis_id}", response_model=HypothesisResponse, summary="Get hypothesis")
async def get_hypothesis(hypothesis_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hypothesis).where(Hypothesis.id == hypothesis_id))
    hyp = result.scalar_one_or_none()
    if not hyp:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return HypothesisResponse(
        id=hyp.id, hunt_id=hyp.hunt_id, title=hyp.title,
        description=hyp.description, mitre_technique=hyp.mitre_technique,
        status=hyp.status, evidence_row_ids=hyp.evidence_row_ids,
        evidence_notes=hyp.evidence_notes,
        created_at=hyp.created_at.isoformat(), updated_at=hyp.updated_at.isoformat(),
    )


@hyp_router.put("/{hypothesis_id}", response_model=HypothesisResponse, summary="Update hypothesis")
async def update_hypothesis(
    hypothesis_id: str, body: HypothesisUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Hypothesis).where(Hypothesis.id == hypothesis_id))
    hyp = result.scalar_one_or_none()
    if not hyp:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    if body.title is not None:
        hyp.title = body.title
    if body.description is not None:
        hyp.description = body.description
    if body.mitre_technique is not None:
        hyp.mitre_technique = body.mitre_technique
    if body.status is not None:
        hyp.status = body.status
    if body.evidence_row_ids is not None:
        hyp.evidence_row_ids = body.evidence_row_ids
    if body.evidence_notes is not None:
        hyp.evidence_notes = body.evidence_notes
    await db.flush()
    return HypothesisResponse(
        id=hyp.id, hunt_id=hyp.hunt_id, title=hyp.title,
        description=hyp.description, mitre_technique=hyp.mitre_technique,
        status=hyp.status, evidence_row_ids=hyp.evidence_row_ids,
        evidence_notes=hyp.evidence_notes,
        created_at=hyp.created_at.isoformat(), updated_at=hyp.updated_at.isoformat(),
    )


@hyp_router.delete("/{hypothesis_id}", summary="Delete hypothesis")
async def delete_hypothesis(hypothesis_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hypothesis).where(Hypothesis.id == hypothesis_id))
    hyp = result.scalar_one_or_none()
    if not hyp:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    await db.delete(hyp)
    return {"message": "Hypothesis deleted", "id": hypothesis_id}

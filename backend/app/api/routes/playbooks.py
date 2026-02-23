"""API routes for investigation playbooks."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Playbook, PlaybookStep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


# -- Request / Response schemas ---

class StepCreate(BaseModel):
    title: str
    description: str | None = None
    step_type: str = "manual"
    target_route: str | None = None

class PlaybookCreate(BaseModel):
    name: str
    description: str | None = None
    hunt_id: str | None = None
    is_template: bool = False
    steps: list[StepCreate] = []

class PlaybookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None

class StepUpdate(BaseModel):
    is_completed: bool | None = None
    notes: str | None = None


# -- Default investigation templates ---

DEFAULT_TEMPLATES = [
    {
        "name": "Standard Threat Hunt",
        "description": "Step-by-step investigation workflow for a typical threat hunting engagement.",
        "steps": [
            {"title": "Upload Artifacts", "description": "Import CSV exports from Velociraptor or other tools", "step_type": "upload", "target_route": "/upload"},
            {"title": "Create Hunt", "description": "Create a new hunt and associate uploaded datasets", "step_type": "action", "target_route": "/hunts"},
            {"title": "AUP Keyword Scan", "description": "Run AUP keyword scanner for policy violations", "step_type": "analysis", "target_route": "/aup"},
            {"title": "Auto-Triage", "description": "Trigger AI triage on all datasets", "step_type": "analysis", "target_route": "/analysis"},
            {"title": "Review Triage Results", "description": "Review flagged rows and risk scores", "step_type": "review", "target_route": "/analysis"},
            {"title": "Enrich IOCs", "description": "Enrich flagged IPs, hashes, and domains via external sources", "step_type": "analysis", "target_route": "/enrichment"},
            {"title": "Host Profiling", "description": "Generate deep host profiles for suspicious hosts", "step_type": "analysis", "target_route": "/analysis"},
            {"title": "Cross-Hunt Correlation", "description": "Identify shared IOCs and patterns across hunts", "step_type": "analysis", "target_route": "/correlation"},
            {"title": "Document Hypotheses", "description": "Record investigation hypotheses with MITRE mappings", "step_type": "action", "target_route": "/hypotheses"},
            {"title": "Generate Report", "description": "Generate final AI-assisted hunt report", "step_type": "action", "target_route": "/analysis"},
        ],
    },
    {
        "name": "Incident Response Triage",
        "description": "Fast-track workflow for active incident response.",
        "steps": [
            {"title": "Upload Artifacts", "description": "Import forensic data from affected hosts", "step_type": "upload", "target_route": "/upload"},
            {"title": "Auto-Triage", "description": "Immediate AI triage for threat indicators", "step_type": "analysis", "target_route": "/analysis"},
            {"title": "IOC Extraction", "description": "Extract all IOCs from flagged data", "step_type": "analysis", "target_route": "/analysis"},
            {"title": "Enrich Critical IOCs", "description": "Priority enrichment of high-risk indicators", "step_type": "analysis", "target_route": "/enrichment"},
            {"title": "Network Map", "description": "Visualize host connections and lateral movement", "step_type": "review", "target_route": "/network"},
            {"title": "Generate Situation Report", "description": "Create executive summary for incident command", "step_type": "action", "target_route": "/analysis"},
        ],
    },
]


# -- Routes ---

@router.get("")
async def list_playbooks(
    include_templates: bool = True,
    hunt_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Playbook)
    if hunt_id:
        q = q.where(Playbook.hunt_id == hunt_id)
    if not include_templates:
        q = q.where(Playbook.is_template == False)
    q = q.order_by(Playbook.created_at.desc())
    result = await db.execute(q.limit(100))
    playbooks = result.scalars().all()

    return {"playbooks": [
        {
            "id": p.id, "name": p.name, "description": p.description,
            "is_template": p.is_template, "hunt_id": p.hunt_id,
            "status": p.status,
            "total_steps": len(p.steps),
            "completed_steps": sum(1 for s in p.steps if s.is_completed),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in playbooks
    ]}


@router.get("/templates")
async def get_templates():
    """Return built-in investigation templates."""
    return {"templates": DEFAULT_TEMPLATES}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_playbook(body: PlaybookCreate, db: AsyncSession = Depends(get_db)):
    pb = Playbook(
        name=body.name,
        description=body.description,
        hunt_id=body.hunt_id,
        is_template=body.is_template,
    )
    db.add(pb)
    await db.flush()

    created_steps = []
    for i, step in enumerate(body.steps):
        s = PlaybookStep(
            playbook_id=pb.id,
            order_index=i,
            title=step.title,
            description=step.description,
            step_type=step.step_type,
            target_route=step.target_route,
        )
        db.add(s)
        created_steps.append(s)

    await db.flush()

    return {
        "id": pb.id, "name": pb.name, "description": pb.description,
        "hunt_id": pb.hunt_id, "is_template": pb.is_template,
        "steps": [
            {"id": s.id, "order_index": s.order_index, "title": s.title,
             "description": s.description, "step_type": s.step_type,
             "target_route": s.target_route, "is_completed": False}
            for s in created_steps
        ],
    }


@router.get("/{playbook_id}")
async def get_playbook(playbook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")

    return {
        "id": pb.id, "name": pb.name, "description": pb.description,
        "is_template": pb.is_template, "hunt_id": pb.hunt_id,
        "status": pb.status,
        "created_at": pb.created_at.isoformat() if pb.created_at else None,
        "steps": [
            {
                "id": s.id, "order_index": s.order_index, "title": s.title,
                "description": s.description, "step_type": s.step_type,
                "target_route": s.target_route,
                "is_completed": s.is_completed,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "notes": s.notes,
            }
            for s in sorted(pb.steps, key=lambda x: x.order_index)
        ],
    }


@router.put("/{playbook_id}")
async def update_playbook(playbook_id: str, body: PlaybookUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")

    if body.name is not None:
        pb.name = body.name
    if body.description is not None:
        pb.description = body.description
    if body.status is not None:
        pb.status = body.status
    return {"status": "updated"}


@router.delete("/{playbook_id}")
async def delete_playbook(playbook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await db.delete(pb)
    return {"status": "deleted"}


@router.put("/steps/{step_id}")
async def update_step(step_id: int, body: StepUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlaybookStep).where(PlaybookStep.id == step_id))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if body.is_completed is not None:
        step.is_completed = body.is_completed
        step.completed_at = datetime.now(timezone.utc) if body.is_completed else None
    if body.notes is not None:
        step.notes = body.notes
    return {"status": "updated", "is_completed": step.is_completed}


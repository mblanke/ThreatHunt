"""API routes for case management — CRUD for cases, tasks, and activity logs."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Case, CaseTask, ActivityLog, _new_id, _utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["cases"])


# ── Pydantic models ──────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    tlp: str = "amber"
    pap: str = "amber"
    priority: int = 2
    assignee: Optional[str] = None
    tags: Optional[list[str]] = None
    hunt_id: Optional[str] = None
    mitre_techniques: Optional[list[str]] = None
    iocs: Optional[list[dict]] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    tlp: Optional[str] = None
    pap: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    assignee: Optional[str] = None
    tags: Optional[list[str]] = None
    mitre_techniques: Optional[list[str]] = None
    iocs: Optional[list[dict]] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    order: Optional[int] = None


# ── Helper: log activity ─────────────────────────────────────────────

async def _log_activity(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    action: str,
    details: dict | None = None,
):
    log = ActivityLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details,
        created_at=_utcnow(),
    )
    db.add(log)


# ── Case CRUD ─────────────────────────────────────────────────────────

@router.post("", summary="Create a case")
async def create_case(body: CaseCreate, db: AsyncSession = Depends(get_db)):
    now = _utcnow()
    case = Case(
        id=_new_id(),
        title=body.title,
        description=body.description,
        severity=body.severity,
        tlp=body.tlp,
        pap=body.pap,
        priority=body.priority,
        assignee=body.assignee,
        tags=body.tags,
        hunt_id=body.hunt_id,
        mitre_techniques=body.mitre_techniques,
        iocs=body.iocs,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    await _log_activity(db, "case", case.id, "created", {"title": body.title})
    await db.commit()
    await db.refresh(case)
    return _case_to_dict(case)


@router.get("", summary="List cases")
async def list_cases(
    status: Optional[str] = Query(None),
    hunt_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Case).order_by(desc(Case.updated_at))
    if status:
        q = q.where(Case.status == status)
    if hunt_id:
        q = q.where(Case.hunt_id == hunt_id)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    cases = result.scalars().all()

    count_q = select(func.count(Case.id))
    if status:
        count_q = count_q.where(Case.status == status)
    if hunt_id:
        count_q = count_q.where(Case.hunt_id == hunt_id)
    total = (await db.execute(count_q)).scalar() or 0

    return {"cases": [_case_to_dict(c) for c in cases], "total": total}


@router.get("/{case_id}", summary="Get case detail")
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_to_dict(case)


@router.put("/{case_id}", summary="Update a case")
async def update_case(case_id: str, body: CaseUpdate, db: AsyncSession = Depends(get_db)):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    changes = {}
    for field in ["title", "description", "severity", "tlp", "pap", "status",
                   "priority", "assignee", "tags", "mitre_techniques", "iocs"]:
        val = getattr(body, field)
        if val is not None:
            old = getattr(case, field)
            setattr(case, field, val)
            changes[field] = {"old": old, "new": val}
    if "status" in changes and changes["status"]["new"] == "in-progress" and not case.started_at:
        case.started_at = _utcnow()
    if "status" in changes and changes["status"]["new"] in ("resolved", "closed"):
        case.resolved_at = _utcnow()
    case.updated_at = _utcnow()
    await _log_activity(db, "case", case.id, "updated", changes)
    await db.commit()
    await db.refresh(case)
    return _case_to_dict(case)


@router.delete("/{case_id}", summary="Delete a case")
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db)):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.commit()
    return {"deleted": True}


# ── Task CRUD ─────────────────────────────────────────────────────────

@router.post("/{case_id}/tasks", summary="Add task to case")
async def create_task(case_id: str, body: TaskCreate, db: AsyncSession = Depends(get_db)):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    now = _utcnow()
    task = CaseTask(
        id=_new_id(),
        case_id=case_id,
        title=body.title,
        description=body.description,
        assignee=body.assignee,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await _log_activity(db, "case", case_id, "task_created", {"title": body.title})
    await db.commit()
    await db.refresh(task)
    return _task_to_dict(task)


@router.put("/{case_id}/tasks/{task_id}", summary="Update a task")
async def update_task(case_id: str, task_id: str, body: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(CaseTask, task_id)
    if not task or task.case_id != case_id:
        raise HTTPException(status_code=404, detail="Task not found")
    for field in ["title", "description", "status", "assignee", "order"]:
        val = getattr(body, field)
        if val is not None:
            setattr(task, field, val)
    task.updated_at = _utcnow()
    await _log_activity(db, "case", case_id, "task_updated", {"task_id": task_id})
    await db.commit()
    await db.refresh(task)
    return _task_to_dict(task)


@router.delete("/{case_id}/tasks/{task_id}", summary="Delete a task")
async def delete_task(case_id: str, task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(CaseTask, task_id)
    if not task or task.case_id != case_id:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
    return {"deleted": True}


# ── Activity Log ──────────────────────────────────────────────────────

@router.get("/{case_id}/activity", summary="Get case activity log")
async def get_activity(
    case_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(ActivityLog)
        .where(ActivityLog.entity_type == "case", ActivityLog.entity_id == case_id)
        .order_by(desc(ActivityLog.created_at))
        .limit(limit)
    )
    result = await db.execute(q)
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": l.id,
                "action": l.action,
                "details": l.details,
                "user_id": l.user_id,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    }


# ── Helpers ───────────────────────────────────────────────────────────

def _case_to_dict(c: Case) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "severity": c.severity,
        "tlp": c.tlp,
        "pap": c.pap,
        "status": c.status,
        "priority": c.priority,
        "assignee": c.assignee,
        "tags": c.tags or [],
        "hunt_id": c.hunt_id,
        "owner_id": c.owner_id,
        "mitre_techniques": c.mitre_techniques or [],
        "iocs": c.iocs or [],
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "tasks": [_task_to_dict(t) for t in (c.tasks or [])],
    }


def _task_to_dict(t: CaseTask) -> dict:
    return {
        "id": t.id,
        "case_id": t.case_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "assignee": t.assignee,
        "order": t.order,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }

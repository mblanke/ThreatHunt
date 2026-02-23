"""API routes for investigation notebooks and playbooks."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Notebook, PlaybookRun, _new_id, _utcnow
from app.services.playbook import (
    get_builtin_playbooks,
    get_playbook_template,
    validate_notebook_cells,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


# ── Pydantic models ──────────────────────────────────────────────────


class NotebookCreate(BaseModel):
    title: str
    description: Optional[str] = None
    cells: Optional[list[dict]] = None
    hunt_id: Optional[str] = None
    case_id: Optional[str] = None
    tags: Optional[list[str]] = None


class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    cells: Optional[list[dict]] = None
    tags: Optional[list[str]] = None


class CellUpdate(BaseModel):
    """Update a single cell or add a new one."""
    cell_id: str
    cell_type: Optional[str] = None
    source: Optional[str] = None
    output: Optional[str] = None
    metadata: Optional[dict] = None


class PlaybookStart(BaseModel):
    playbook_name: str
    hunt_id: Optional[str] = None
    case_id: Optional[str] = None
    started_by: Optional[str] = None


class StepComplete(BaseModel):
    notes: Optional[str] = None
    status: str = "completed"  # completed | skipped


# ── Helpers ───────────────────────────────────────────────────────────


def _notebook_to_dict(nb: Notebook) -> dict:
    return {
        "id": nb.id,
        "title": nb.title,
        "description": nb.description,
        "cells": nb.cells or [],
        "hunt_id": nb.hunt_id,
        "case_id": nb.case_id,
        "owner_id": nb.owner_id,
        "tags": nb.tags or [],
        "cell_count": len(nb.cells or []),
        "created_at": nb.created_at.isoformat() if nb.created_at else None,
        "updated_at": nb.updated_at.isoformat() if nb.updated_at else None,
    }


def _run_to_dict(run: PlaybookRun) -> dict:
    return {
        "id": run.id,
        "playbook_name": run.playbook_name,
        "status": run.status,
        "current_step": run.current_step,
        "total_steps": run.total_steps,
        "step_results": run.step_results or [],
        "hunt_id": run.hunt_id,
        "case_id": run.case_id,
        "started_by": run.started_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


# ── Notebook CRUD ─────────────────────────────────────────────────────


@router.get("", summary="List notebooks")
async def list_notebooks(
    hunt_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Notebook)
    count_stmt = select(func.count(Notebook.id))
    if hunt_id:
        stmt = stmt.where(Notebook.hunt_id == hunt_id)
        count_stmt = count_stmt.where(Notebook.hunt_id == hunt_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    results = (await db.execute(
        stmt.order_by(desc(Notebook.updated_at)).offset(offset).limit(limit)
    )).scalars().all()

    return {"notebooks": [_notebook_to_dict(n) for n in results], "total": total}


@router.get("/{notebook_id}", summary="Get notebook")
async def get_notebook(notebook_id: str, db: AsyncSession = Depends(get_db)):
    nb = await db.get(Notebook, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return _notebook_to_dict(nb)


@router.post("", summary="Create notebook")
async def create_notebook(body: NotebookCreate, db: AsyncSession = Depends(get_db)):
    cells = validate_notebook_cells(body.cells or [])
    if not cells:
        # Start with a default markdown cell
        cells = [{"id": "cell-0", "cell_type": "markdown", "source": "# Investigation Notes\n\nStart documenting your findings here.", "output": None, "metadata": {}}]

    nb = Notebook(
        id=_new_id(),
        title=body.title,
        description=body.description,
        cells=cells,
        hunt_id=body.hunt_id,
        case_id=body.case_id,
        tags=body.tags,
    )
    db.add(nb)
    await db.commit()
    await db.refresh(nb)
    return _notebook_to_dict(nb)


@router.put("/{notebook_id}", summary="Update notebook")
async def update_notebook(
    notebook_id: str, body: NotebookUpdate, db: AsyncSession = Depends(get_db)
):
    nb = await db.get(Notebook, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    if body.title is not None:
        nb.title = body.title
    if body.description is not None:
        nb.description = body.description
    if body.cells is not None:
        nb.cells = validate_notebook_cells(body.cells)
    if body.tags is not None:
        nb.tags = body.tags

    await db.commit()
    await db.refresh(nb)
    return _notebook_to_dict(nb)


@router.post("/{notebook_id}/cells", summary="Add or update a cell")
async def upsert_cell(
    notebook_id: str, body: CellUpdate, db: AsyncSession = Depends(get_db)
):
    nb = await db.get(Notebook, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    cells = list(nb.cells or [])
    found = False
    for i, c in enumerate(cells):
        if c.get("id") == body.cell_id:
            if body.cell_type is not None:
                cells[i]["cell_type"] = body.cell_type
            if body.source is not None:
                cells[i]["source"] = body.source
            if body.output is not None:
                cells[i]["output"] = body.output
            if body.metadata is not None:
                cells[i]["metadata"] = body.metadata
            found = True
            break

    if not found:
        cells.append({
            "id": body.cell_id,
            "cell_type": body.cell_type or "markdown",
            "source": body.source or "",
            "output": body.output,
            "metadata": body.metadata or {},
        })

    nb.cells = cells
    await db.commit()
    await db.refresh(nb)
    return _notebook_to_dict(nb)


@router.delete("/{notebook_id}/cells/{cell_id}", summary="Delete a cell")
async def delete_cell(
    notebook_id: str, cell_id: str, db: AsyncSession = Depends(get_db)
):
    nb = await db.get(Notebook, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    cells = [c for c in (nb.cells or []) if c.get("id") != cell_id]
    nb.cells = cells
    await db.commit()
    return {"ok": True, "remaining_cells": len(cells)}


@router.delete("/{notebook_id}", summary="Delete notebook")
async def delete_notebook(notebook_id: str, db: AsyncSession = Depends(get_db)):
    nb = await db.get(Notebook, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    await db.delete(nb)
    await db.commit()
    return {"ok": True}


# ── Playbooks ─────────────────────────────────────────────────────────


@router.get("/playbooks/templates", summary="List built-in playbook templates")
async def list_playbook_templates():
    templates = get_builtin_playbooks()
    return {
        "templates": [
            {
                "name": t["name"],
                "description": t["description"],
                "category": t["category"],
                "tags": t["tags"],
                "step_count": len(t["steps"]),
            }
            for t in templates
        ]
    }


@router.get("/playbooks/templates/{name}", summary="Get playbook template detail")
async def get_playbook_template_detail(name: str):
    template = get_playbook_template(name)
    if not template:
        raise HTTPException(status_code=404, detail="Playbook template not found")
    return template


@router.post("/playbooks/start", summary="Start a playbook run")
async def start_playbook(body: PlaybookStart, db: AsyncSession = Depends(get_db)):
    template = get_playbook_template(body.playbook_name)
    if not template:
        raise HTTPException(status_code=404, detail="Playbook template not found")

    run = PlaybookRun(
        id=_new_id(),
        playbook_name=body.playbook_name,
        status="in-progress",
        current_step=1,
        total_steps=len(template["steps"]),
        step_results=[],
        hunt_id=body.hunt_id,
        case_id=body.case_id,
        started_by=body.started_by,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return _run_to_dict(run)


@router.get("/playbooks/runs", summary="List playbook runs")
async def list_playbook_runs(
    status: str | None = Query(None),
    hunt_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PlaybookRun)
    if status:
        stmt = stmt.where(PlaybookRun.status == status)
    if hunt_id:
        stmt = stmt.where(PlaybookRun.hunt_id == hunt_id)

    results = (await db.execute(
        stmt.order_by(desc(PlaybookRun.created_at)).limit(limit)
    )).scalars().all()

    return {"runs": [_run_to_dict(r) for r in results]}


@router.get("/playbooks/runs/{run_id}", summary="Get playbook run detail")
async def get_playbook_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PlaybookRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Also include the template steps
    template = get_playbook_template(run.playbook_name)
    result = _run_to_dict(run)
    result["steps"] = template["steps"] if template else []
    return result


@router.post("/playbooks/runs/{run_id}/complete-step", summary="Complete current playbook step")
async def complete_step(
    run_id: str, body: StepComplete, db: AsyncSession = Depends(get_db)
):
    run = await db.get(PlaybookRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "in-progress":
        raise HTTPException(status_code=400, detail="Run is not in progress")

    step_results = list(run.step_results or [])
    step_results.append({
        "step": run.current_step,
        "status": body.status,
        "notes": body.notes,
        "completed_at": _utcnow().isoformat(),
    })
    run.step_results = step_results

    if run.current_step >= run.total_steps:
        run.status = "completed"
        run.completed_at = _utcnow()
    else:
        run.current_step += 1

    await db.commit()
    await db.refresh(run)
    return _run_to_dict(run)


@router.post("/playbooks/runs/{run_id}/abort", summary="Abort a playbook run")
async def abort_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PlaybookRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run.status = "aborted"
    run.completed_at = _utcnow()
    await db.commit()
    return _run_to_dict(run)

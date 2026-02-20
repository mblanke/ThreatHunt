"""API routes for alerts — CRUD, analyze triggers, and alert rules."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Alert, AlertRule, _new_id, _utcnow
from app.db.repositories.datasets import DatasetRepository
from app.services.analyzers import (
    get_available_analyzers,
    get_analyzer,
    run_all_analyzers,
    AlertCandidate,
)
from app.services.process_tree import _fetch_rows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── Pydantic models ──────────────────────────────────────────────────


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    assignee: Optional[str] = None
    case_id: Optional[str] = None
    tags: Optional[list[str]] = None


class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    analyzer: str
    config: Optional[dict] = None
    severity_override: Optional[str] = None
    enabled: bool = True
    hunt_id: Optional[str] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    severity_override: Optional[str] = None
    enabled: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    dataset_id: Optional[str] = None
    hunt_id: Optional[str] = None
    analyzers: Optional[list[str]] = None  # None = run all
    config: Optional[dict] = None
    auto_create: bool = True  # automatically persist alerts


# ── Helpers ───────────────────────────────────────────────────────────


def _alert_to_dict(a: Alert) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "severity": a.severity,
        "status": a.status,
        "analyzer": a.analyzer,
        "score": a.score,
        "evidence": a.evidence or [],
        "mitre_technique": a.mitre_technique,
        "tags": a.tags or [],
        "hunt_id": a.hunt_id,
        "dataset_id": a.dataset_id,
        "case_id": a.case_id,
        "assignee": a.assignee,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _rule_to_dict(r: AlertRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "analyzer": r.analyzer,
        "config": r.config,
        "severity_override": r.severity_override,
        "enabled": r.enabled,
        "hunt_id": r.hunt_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ── Alert CRUD ────────────────────────────────────────────────────────


@router.get("", summary="List alerts")
async def list_alerts(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    analyzer: str | None = Query(None),
    hunt_id: str | None = Query(None),
    dataset_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert)
    count_stmt = select(func.count(Alert.id))
    if status:
        stmt = stmt.where(Alert.status == status)
        count_stmt = count_stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
        count_stmt = count_stmt.where(Alert.severity == severity)
    if analyzer:
        stmt = stmt.where(Alert.analyzer == analyzer)
        count_stmt = count_stmt.where(Alert.analyzer == analyzer)
    if hunt_id:
        stmt = stmt.where(Alert.hunt_id == hunt_id)
        count_stmt = count_stmt.where(Alert.hunt_id == hunt_id)
    if dataset_id:
        stmt = stmt.where(Alert.dataset_id == dataset_id)
        count_stmt = count_stmt.where(Alert.dataset_id == dataset_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    results = (await db.execute(
        stmt.order_by(desc(Alert.score), desc(Alert.created_at)).offset(offset).limit(limit)
    )).scalars().all()

    return {"alerts": [_alert_to_dict(a) for a in results], "total": total}


@router.get("/stats", summary="Alert statistics dashboard")
async def alert_stats(
    hunt_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated alert statistics."""
    base = select(Alert)
    if hunt_id:
        base = base.where(Alert.hunt_id == hunt_id)

    # Severity breakdown
    sev_stmt = select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
    if hunt_id:
        sev_stmt = sev_stmt.where(Alert.hunt_id == hunt_id)
    sev_rows = (await db.execute(sev_stmt)).all()
    severity_counts = {s: c for s, c in sev_rows}

    # Status breakdown
    status_stmt = select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
    if hunt_id:
        status_stmt = status_stmt.where(Alert.hunt_id == hunt_id)
    status_rows = (await db.execute(status_stmt)).all()
    status_counts = {s: c for s, c in status_rows}

    # Analyzer breakdown
    analyzer_stmt = select(Alert.analyzer, func.count(Alert.id)).group_by(Alert.analyzer)
    if hunt_id:
        analyzer_stmt = analyzer_stmt.where(Alert.hunt_id == hunt_id)
    analyzer_rows = (await db.execute(analyzer_stmt)).all()
    analyzer_counts = {a: c for a, c in analyzer_rows}

    # Top MITRE techniques
    mitre_stmt = (
        select(Alert.mitre_technique, func.count(Alert.id))
        .where(Alert.mitre_technique.isnot(None))
        .group_by(Alert.mitre_technique)
        .order_by(desc(func.count(Alert.id)))
        .limit(10)
    )
    if hunt_id:
        mitre_stmt = mitre_stmt.where(Alert.hunt_id == hunt_id)
    mitre_rows = (await db.execute(mitre_stmt)).all()
    top_mitre = [{"technique": t, "count": c} for t, c in mitre_rows]

    total = sum(severity_counts.values())

    return {
        "total": total,
        "severity_counts": severity_counts,
        "status_counts": status_counts,
        "analyzer_counts": analyzer_counts,
        "top_mitre": top_mitre,
    }


@router.get("/{alert_id}", summary="Get alert detail")
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.get(Alert, alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_dict(result)


@router.put("/{alert_id}", summary="Update alert (status, assignee, etc.)")
async def update_alert(
    alert_id: str, body: AlertUpdate, db: AsyncSession = Depends(get_db)
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if body.status is not None:
        alert.status = body.status
        if body.status == "acknowledged" and not alert.acknowledged_at:
            alert.acknowledged_at = _utcnow()
        if body.status in ("resolved", "false-positive") and not alert.resolved_at:
            alert.resolved_at = _utcnow()
    if body.severity is not None:
        alert.severity = body.severity
    if body.assignee is not None:
        alert.assignee = body.assignee
    if body.case_id is not None:
        alert.case_id = body.case_id
    if body.tags is not None:
        alert.tags = body.tags

    await db.commit()
    await db.refresh(alert)
    return _alert_to_dict(alert)


@router.delete("/{alert_id}", summary="Delete alert")
async def delete_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"ok": True}


# ── Bulk operations ──────────────────────────────────────────────────


@router.post("/bulk-update", summary="Bulk update alert statuses")
async def bulk_update_alerts(
    alert_ids: list[str],
    status: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    updated = 0
    for aid in alert_ids:
        alert = await db.get(Alert, aid)
        if alert:
            alert.status = status
            if status == "acknowledged" and not alert.acknowledged_at:
                alert.acknowledged_at = _utcnow()
            if status in ("resolved", "false-positive") and not alert.resolved_at:
                alert.resolved_at = _utcnow()
            updated += 1
    await db.commit()
    return {"updated": updated}


# ── Run Analyzers ────────────────────────────────────────────────────


@router.get("/analyzers/list", summary="List available analyzers")
async def list_analyzers():
    return {"analyzers": get_available_analyzers()}


@router.post("/analyze", summary="Run analyzers on a dataset/hunt and optionally create alerts")
async def run_analysis(
    request: AnalyzeRequest, db: AsyncSession = Depends(get_db)
):
    if not request.dataset_id and not request.hunt_id:
        raise HTTPException(status_code=400, detail="Provide dataset_id or hunt_id")

    # Load rows
    rows_objs = await _fetch_rows(
        db, dataset_id=request.dataset_id, hunt_id=request.hunt_id, limit=10000,
    )
    if not rows_objs:
        raise HTTPException(status_code=404, detail="No rows found")

    rows = [r.normalized_data or r.data for r in rows_objs]

    # Run analyzers
    candidates = await run_all_analyzers(rows, enabled=request.analyzers, config=request.config)

    created_alerts: list[dict] = []
    if request.auto_create and candidates:
        for c in candidates:
            alert = Alert(
                id=_new_id(),
                title=c.title,
                description=c.description,
                severity=c.severity,
                analyzer=c.analyzer,
                score=c.score,
                evidence=c.evidence,
                mitre_technique=c.mitre_technique,
                tags=c.tags,
                hunt_id=request.hunt_id,
                dataset_id=request.dataset_id,
            )
            db.add(alert)
            created_alerts.append(_alert_to_dict(alert))
        await db.commit()

    return {
        "candidates_found": len(candidates),
        "alerts_created": len(created_alerts),
        "alerts": created_alerts,
        "summary": {
            "by_severity": _count_by(candidates, "severity"),
            "by_analyzer": _count_by(candidates, "analyzer"),
            "rows_analyzed": len(rows),
        },
    }


def _count_by(items: list[AlertCandidate], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = getattr(item, attr, "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


# ── Alert Rules CRUD ─────────────────────────────────────────────────


@router.get("/rules/list", summary="List alert rules")
async def list_rules(
    enabled: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AlertRule)
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    results = (await db.execute(stmt.order_by(AlertRule.created_at))).scalars().all()
    return {"rules": [_rule_to_dict(r) for r in results]}


@router.post("/rules", summary="Create alert rule")
async def create_rule(body: RuleCreate, db: AsyncSession = Depends(get_db)):
    # Validate analyzer exists
    if not get_analyzer(body.analyzer):
        raise HTTPException(status_code=400, detail=f"Unknown analyzer: {body.analyzer}")

    rule = AlertRule(
        id=_new_id(),
        name=body.name,
        description=body.description,
        analyzer=body.analyzer,
        config=body.config,
        severity_override=body.severity_override,
        enabled=body.enabled,
        hunt_id=body.hunt_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.put("/rules/{rule_id}", summary="Update alert rule")
async def update_rule(
    rule_id: str, body: RuleUpdate, db: AsyncSession = Depends(get_db)
):
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    if body.config is not None:
        rule.config = body.config
    if body.severity_override is not None:
        rule.severity_override = body.severity_override
    if body.enabled is not None:
        rule.enabled = body.enabled

    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/rules/{rule_id}", summary="Delete alert rule")
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"ok": True}

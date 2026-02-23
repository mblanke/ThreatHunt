"""API routes for saved searches and bookmarked queries."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import SavedSearch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/searches", tags=["saved-searches"])


class SearchCreate(BaseModel):
    name: str
    description: str | None = None
    search_type: str  # "nlp_query", "ioc_search", "keyword_scan", "correlation"
    query_params: dict
    threshold: float | None = None


class SearchUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    query_params: dict | None = None
    threshold: float | None = None


@router.get("")
async def list_searches(
    search_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(SavedSearch).order_by(SavedSearch.created_at.desc())
    if search_type:
        q = q.where(SavedSearch.search_type == search_type)
    result = await db.execute(q.limit(100))
    searches = result.scalars().all()
    return {"searches": [
        {
            "id": s.id, "name": s.name, "description": s.description,
            "search_type": s.search_type, "query_params": s.query_params,
            "threshold": s.threshold,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "last_result_count": s.last_result_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in searches
    ]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_search(body: SearchCreate, db: AsyncSession = Depends(get_db)):
    s = SavedSearch(
        name=body.name,
        description=body.description,
        search_type=body.search_type,
        query_params=body.query_params,
        threshold=body.threshold,
    )
    db.add(s)
    await db.flush()
    return {
        "id": s.id, "name": s.name, "search_type": s.search_type,
        "query_params": s.query_params, "threshold": s.threshold,
    }


@router.get("/{search_id}")
async def get_search(search_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {
        "id": s.id, "name": s.name, "description": s.description,
        "search_type": s.search_type, "query_params": s.query_params,
        "threshold": s.threshold,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "last_result_count": s.last_result_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.put("/{search_id}")
async def update_search(search_id: str, body: SearchUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Saved search not found")
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.query_params is not None:
        s.query_params = body.query_params
    if body.threshold is not None:
        s.threshold = body.threshold
    return {"status": "updated"}


@router.delete("/{search_id}")
async def delete_search(search_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await db.delete(s)
    return {"status": "deleted"}


@router.post("/{search_id}/run")
async def run_saved_search(search_id: str, db: AsyncSession = Depends(get_db)):
    """Execute a saved search and return results with delta from last run."""
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Saved search not found")

    previous_count = s.last_result_count or 0
    results = []
    count = 0

    if s.search_type == "ioc_search":
        from app.db.models import EnrichmentResult
        ioc_value = s.query_params.get("ioc_value", "")
        if ioc_value:
            q = select(EnrichmentResult).where(
                EnrichmentResult.ioc_value.contains(ioc_value)
            )
            res = await db.execute(q.limit(100))
            for er in res.scalars().all():
                results.append({
                    "ioc_value": er.ioc_value, "ioc_type": er.ioc_type,
                    "source": er.source, "verdict": er.verdict,
                })
            count = len(results)

    elif s.search_type == "keyword_scan":
        from app.db.models import KeywordTheme
        res = await db.execute(select(KeywordTheme).where(KeywordTheme.enabled == True))
        themes = res.scalars().all()
        count = sum(len(t.keywords) for t in themes)
        results = [{"theme": t.name, "keyword_count": len(t.keywords)} for t in themes]

    # Update last run metadata
    s.last_run_at = datetime.now(timezone.utc)
    s.last_result_count = count

    delta = count - previous_count

    return {
        "search_id": s.id, "search_name": s.name,
        "search_type": s.search_type,
        "result_count": count,
        "previous_count": previous_count,
        "delta": delta,
        "results": results[:50],
    }

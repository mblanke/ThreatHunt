from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/keywords.py')
new_text='''"""API routes for AUP keyword themes, keyword CRUD, and scanning."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import KeywordTheme, Keyword
from app.services.scanner import KeywordScanner, keyword_scan_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


class ThemeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    color: str = Field(default="#9e9e9e", max_length=16)
    enabled: bool = True


class ThemeUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    enabled: bool | None = None


class KeywordOut(BaseModel):
    id: int
    theme_id: str
    value: str
    is_regex: bool
    created_at: str


class ThemeOut(BaseModel):
    id: str
    name: str
    color: str
    enabled: bool
    is_builtin: bool
    created_at: str
    keyword_count: int
    keywords: list[KeywordOut]


class ThemeListResponse(BaseModel):
    themes: list[ThemeOut]
    total: int


class KeywordCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=256)
    is_regex: bool = False


class KeywordBulkCreate(BaseModel):
    values: list[str] = Field(..., min_items=1)
    is_regex: bool = False


class ScanRequest(BaseModel):
    dataset_ids: list[str] | None = None
    theme_ids: list[str] | None = None
    scan_hunts: bool = False
    scan_annotations: bool = False
    scan_messages: bool = False
    prefer_cache: bool = True
    force_rescan: bool = False


class ScanHit(BaseModel):
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None


class ScanResponse(BaseModel):
    total_hits: int
    hits: list[ScanHit]
    themes_scanned: int
    keywords_scanned: int
    rows_scanned: int
    cache_used: bool = False
    cache_status: str = "miss"
    cached_at: str | None = None


def _theme_to_out(t: KeywordTheme) -> ThemeOut:
    return ThemeOut(
        id=t.id,
        name=t.name,
        color=t.color,
        enabled=t.enabled,
        is_builtin=t.is_builtin,
        created_at=t.created_at.isoformat(),
        keyword_count=len(t.keywords),
        keywords=[
            KeywordOut(
                id=k.id,
                theme_id=k.theme_id,
                value=k.value,
                is_regex=k.is_regex,
                created_at=k.created_at.isoformat(),
            )
            for k in t.keywords
        ],
    )


def _merge_cached_results(entries: list[dict], allowed_theme_names: set[str] | None = None) -> dict:
    hits: list[dict] = []
    total_rows = 0
    cached_at: str | None = None

    for entry in entries:
        result = entry["result"]
        total_rows += int(result.get("rows_scanned", 0) or 0)
        if entry.get("built_at"):
            if not cached_at or entry["built_at"] > cached_at:
                cached_at = entry["built_at"]
        for h in result.get("hits", []):
            if allowed_theme_names is not None and h.get("theme_name") not in allowed_theme_names:
                continue
            hits.append(h)

    return {
        "total_hits": len(hits),
        "hits": hits,
        "rows_scanned": total_rows,
        "cached_at": cached_at,
    }


@router.get("/themes", response_model=ThemeListResponse)
async def list_themes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KeywordTheme).order_by(KeywordTheme.name))
    themes = result.scalars().all()
    return ThemeListResponse(themes=[_theme_to_out(t) for t in themes], total=len(themes))


@router.post("/themes", response_model=ThemeOut, status_code=201)
async def create_theme(body: ThemeCreate, db: AsyncSession = Depends(get_db)):
    exists = await db.scalar(select(KeywordTheme.id).where(KeywordTheme.name == body.name))
    if exists:
        raise HTTPException(409, f"Theme '{body.name}' already exists")
    theme = KeywordTheme(name=body.name, color=body.color, enabled=body.enabled)
    db.add(theme)
    await db.flush()
    await db.refresh(theme)
    keyword_scan_cache.clear()
    return _theme_to_out(theme)


@router.put("/themes/{theme_id}", response_model=ThemeOut)
async def update_theme(theme_id: str, body: ThemeUpdate, db: AsyncSession = Depends(get_db)):
    theme = await db.get(KeywordTheme, theme_id)
    if not theme:
        raise HTTPException(404, "Theme not found")
    if body.name is not None:
        dup = await db.scalar(
            select(KeywordTheme.id).where(KeywordTheme.name == body.name, KeywordTheme.id != theme_id)
        )
        if dup:
            raise HTTPException(409, f"Theme '{body.name}' already exists")
        theme.name = body.name
    if body.color is not None:
        theme.color = body.color
    if body.enabled is not None:
        theme.enabled = body.enabled
    await db.flush()
    await db.refresh(theme)
    keyword_scan_cache.clear()
    return _theme_to_out(theme)


@router.delete("/themes/{theme_id}", status_code=204)
async def delete_theme(theme_id: str, db: AsyncSession = Depends(get_db)):
    theme = await db.get(KeywordTheme, theme_id)
    if not theme:
        raise HTTPException(404, "Theme not found")
    await db.delete(theme)
    keyword_scan_cache.clear()


@router.post("/themes/{theme_id}/keywords", response_model=KeywordOut, status_code=201)
async def add_keyword(theme_id: str, body: KeywordCreate, db: AsyncSession = Depends(get_db)):
    theme = await db.get(KeywordTheme, theme_id)
    if not theme:
        raise HTTPException(404, "Theme not found")
    kw = Keyword(theme_id=theme_id, value=body.value, is_regex=body.is_regex)
    db.add(kw)
    await db.flush()
    await db.refresh(kw)
    keyword_scan_cache.clear()
    return KeywordOut(
        id=kw.id, theme_id=kw.theme_id, value=kw.value,
        is_regex=kw.is_regex, created_at=kw.created_at.isoformat(),
    )


@router.post("/themes/{theme_id}/keywords/bulk", response_model=dict, status_code=201)
async def add_keywords_bulk(theme_id: str, body: KeywordBulkCreate, db: AsyncSession = Depends(get_db)):
    theme = await db.get(KeywordTheme, theme_id)
    if not theme:
        raise HTTPException(404, "Theme not found")
    added = 0
    for val in body.values:
        val = val.strip()
        if not val:
            continue
        db.add(Keyword(theme_id=theme_id, value=val, is_regex=body.is_regex))
        added += 1
    await db.flush()
    keyword_scan_cache.clear()
    return {"added": added, "theme_id": theme_id}


@router.delete("/keywords/{keyword_id}", status_code=204)
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    kw = await db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(404, "Keyword not found")
    await db.delete(kw)
    keyword_scan_cache.clear()


@router.post("/scan", response_model=ScanResponse)
async def run_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):
    scanner = KeywordScanner(db)

    can_use_cache = (
        body.prefer_cache
        and not body.force_rescan
        and bool(body.dataset_ids)
        and not body.scan_hunts
        and not body.scan_annotations
        and not body.scan_messages
    )

    if can_use_cache:
        themes = await scanner._load_themes(body.theme_ids)
        allowed_theme_names = {t.name for t in themes}
        keywords_scanned = sum(len(theme.keywords) for theme in themes)

        cached_entries: list[dict] = []
        missing: list[str] = []
        for dataset_id in (body.dataset_ids or []):
            entry = keyword_scan_cache.get(dataset_id)
            if not entry:
                missing.append(dataset_id)
                continue
            cached_entries.append({"result": entry.result, "built_at": entry.built_at})

        if not missing and cached_entries:
            merged = _merge_cached_results(cached_entries, allowed_theme_names if body.theme_ids else None)
            return {
                "total_hits": merged["total_hits"],
                "hits": merged["hits"],
                "themes_scanned": len(themes),
                "keywords_scanned": keywords_scanned,
                "rows_scanned": merged["rows_scanned"],
                "cache_used": True,
                "cache_status": "hit",
                "cached_at": merged["cached_at"],
            }

    result = await scanner.scan(
        dataset_ids=body.dataset_ids,
        theme_ids=body.theme_ids,
        scan_hunts=body.scan_hunts,
        scan_annotations=body.scan_annotations,
        scan_messages=body.scan_messages,
    )

    return {
        **result,
        "cache_used": False,
        "cache_status": "miss",
        "cached_at": None,
    }


@router.get("/scan/quick", response_model=ScanResponse)
async def quick_scan(
    dataset_id: str = Query(..., description="Dataset to scan"),
    db: AsyncSession = Depends(get_db),
):
    entry = keyword_scan_cache.get(dataset_id)
    if entry is not None:
        result = entry.result
        return {
            **result,
            "cache_used": True,
            "cache_status": "hit",
            "cached_at": entry.built_at,
        }

    scanner = KeywordScanner(db)
    result = await scanner.scan(dataset_ids=[dataset_id])
    keyword_scan_cache.put(dataset_id, result)
    return {
        **result,
        "cache_used": False,
        "cache_status": "miss",
        "cached_at": None,
    }
'''
p.write_text(new_text,encoding='utf-8')
print('updated keywords.py')

"""Timeline and field-statistics service.

Provides temporal histogram bins and per-field distribution stats
for dataset rows — used by the TimelineScrubber and QueryBar components.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)


# ── Timeline bins ─────────────────────────────────────────────────────


async def build_timeline_bins(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    bins: int = 60,
) -> dict:
    """Create histogram bins of events over time.

    Returns {bins: [{start, end, count, events_by_type}], total, range}.
    """
    rows = await _fetch_rows(db, dataset_id=dataset_id, hunt_id=hunt_id)
    if not rows:
        return {"bins": [], "total": 0, "range": None}

    # Extract timestamps
    events: list[dict] = []
    for r in rows:
        data = r.normalized_data or r.data
        ts_str = data.get("timestamp", "")
        if not ts_str:
            continue
        ts = _parse_ts(str(ts_str))
        if ts:
            events.append({
                "timestamp": ts,
                "event_type": _classify_type(data),
                "hostname": data.get("hostname", ""),
            })

    if not events:
        return {"bins": [], "total": len(rows), "range": None}

    events.sort(key=lambda e: e["timestamp"])
    ts_min = events[0]["timestamp"]
    ts_max = events[-1]["timestamp"]

    if ts_min == ts_max:
        return {
            "bins": [{"start": ts_min.isoformat(), "end": ts_max.isoformat(),
                       "count": len(events), "events_by_type": {}}],
            "total": len(events),
            "range": {"start": ts_min.isoformat(), "end": ts_max.isoformat()},
        }

    delta = (ts_max - ts_min) / bins
    result_bins: list[dict] = []

    for i in range(bins):
        bin_start = ts_min + delta * i
        bin_end = ts_min + delta * (i + 1)
        bin_events = [e for e in events
                      if bin_start <= e["timestamp"] < bin_end
                      or (i == bins - 1 and e["timestamp"] == ts_max)]
        type_counts: dict[str, int] = Counter(e["event_type"] for e in bin_events)
        result_bins.append({
            "start": bin_start.isoformat(),
            "end": bin_end.isoformat(),
            "count": len(bin_events),
            "events_by_type": dict(type_counts),
        })

    return {
        "bins": result_bins,
        "total": len(events),
        "range": {"start": ts_min.isoformat(), "end": ts_max.isoformat()},
    }


# ── Field stats ───────────────────────────────────────────────────────


async def compute_field_stats(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    fields: list[str] | None = None,
    top_n: int = 20,
) -> dict:
    """Compute per-field value distributions.

    Returns {fields: {field_name: {total, unique, top: [{value, count}]}}}
    """
    rows = await _fetch_rows(db, dataset_id=dataset_id, hunt_id=hunt_id)
    if not rows:
        return {"fields": {}, "total_rows": 0}

    # Determine which fields to analyze
    sample_data = rows[0].normalized_data or rows[0].data
    all_fields = list(sample_data.keys())
    target_fields = fields if fields else all_fields[:30]

    stats: dict[str, dict] = {}
    for field in target_fields:
        values = []
        for r in rows:
            data = r.normalized_data or r.data
            v = data.get(field)
            if v is not None and str(v).strip() not in ("", "N/A", "n/a", "-", "None"):
                values.append(str(v))

        counter = Counter(values)
        top = [{"value": v, "count": c} for v, c in counter.most_common(top_n)]
        stats[field] = {
            "total": len(values),
            "unique": len(counter),
            "top": top,
        }

    return {
        "fields": stats,
        "total_rows": len(rows),
        "available_fields": all_fields,
    }


# ── Row search with filters ──────────────────────────────────────────


async def search_rows(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    query: str = "",
    filters: dict[str, str] | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict:
    """Search/filter dataset rows.

    Supports:
    - Free-text search across all fields
    - Field-specific filters {field: value}
    - Time range filters
    """
    rows = await _fetch_rows(db, dataset_id=dataset_id, hunt_id=hunt_id, limit=50000)
    if not rows:
        return {"rows": [], "total": 0, "offset": offset, "limit": limit}

    results: list[dict] = []
    ts_start = _parse_ts(time_start) if time_start else None
    ts_end = _parse_ts(time_end) if time_end else None

    for r in rows:
        data = r.normalized_data or r.data

        # Time filter
        if ts_start or ts_end:
            ts = _parse_ts(str(data.get("timestamp", "")))
            if ts:
                if ts_start and ts < ts_start:
                    continue
                if ts_end and ts > ts_end:
                    continue

        # Field filters
        if filters:
            match = True
            for field, value in filters.items():
                field_val = str(data.get(field, "")).lower()
                if value.lower() not in field_val:
                    match = False
                    break
            if not match:
                continue

        # Free-text search
        if query:
            q = query.lower()
            found = any(q in str(v).lower() for v in data.values())
            if not found:
                continue

        results.append(data)

    total = len(results)
    paged = results[offset:offset + limit]

    return {"rows": paged, "total": total, "offset": offset, "limit": limit}


# ── Internal helpers ──────────────────────────────────────────────────


async def _fetch_rows(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    limit: int = 50_000,
) -> Sequence[DatasetRow]:
    stmt = select(DatasetRow).join(Dataset)
    if dataset_id:
        stmt = stmt.where(DatasetRow.dataset_id == dataset_id)
    elif hunt_id:
        stmt = stmt.where(Dataset.hunt_id == hunt_id)
    stmt = stmt.order_by(DatasetRow.row_index).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


def _parse_ts(ts_str: str | None) -> datetime | None:
    """Best-effort timestamp parsing."""
    if not ts_str:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
    ):
        try:
            return datetime.strptime(ts_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _classify_type(data: dict) -> str:
    if data.get("pid") or data.get("process_name"):
        if data.get("dst_ip") or data.get("dst_port"):
            return "network"
        return "process"
    if data.get("dst_ip") or data.get("src_ip"):
        return "network"
    if data.get("file_path"):
        return "file"
    return "other"

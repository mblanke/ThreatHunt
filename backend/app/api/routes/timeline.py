"""API routes for forensic timeline visualization."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Dataset, DatasetRow, Hunt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


def _parse_timestamp(val: str | None) -> str | None:
    """Try to parse a timestamp string, return ISO format or None."""
    if not val:
        return None
    val = str(val).strip()
    if not val:
        return None
    # Try common formats
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S",
    ]:
        try:
            return datetime.strptime(val, fmt).isoformat() + "Z"
        except ValueError:
            continue
    return None


# Columns likely to contain timestamps
TIME_COLUMNS = {
    "timestamp", "time", "datetime", "date", "created", "modified",
    "eventtime", "event_time", "start_time", "end_time",
    "lastmodified", "last_modified", "created_at", "updated_at",
    "mtime", "atime", "ctime", "btime",
    "timecreated", "timegenerated", "sourcetime",
}


@router.get("/hunt/{hunt_id}")
async def get_hunt_timeline(
    hunt_id: str,
    limit: int = 2000,
    db: AsyncSession = Depends(get_db),
):
    """Build a timeline of events across all datasets in a hunt."""
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")

    result = await db.execute(select(Dataset).where(Dataset.hunt_id == hunt_id))
    datasets = result.scalars().all()
    if not datasets:
        return {"hunt_id": hunt_id, "events": [], "datasets": []}

    events = []
    dataset_info = []

    for ds in datasets:
        artifact_type = getattr(ds, "artifact_type", None) or "Unknown"
        dataset_info.append({
            "id": ds.id, "name": ds.name, "artifact_type": artifact_type,
            "row_count": ds.row_count,
        })

        # Find time columns for this dataset
        schema = ds.column_schema or {}
        time_cols = []
        for col in (ds.normalized_columns or {}).values():
            if col.lower() in TIME_COLUMNS:
                time_cols.append(col)
        if not time_cols:
            for col in schema:
                if col.lower() in TIME_COLUMNS or "time" in col.lower() or "date" in col.lower():
                    time_cols.append(col)
        if not time_cols:
            continue

        # Fetch rows
        rows_result = await db.execute(
            select(DatasetRow)
            .where(DatasetRow.dataset_id == ds.id)
            .order_by(DatasetRow.row_index)
            .limit(limit // max(len(datasets), 1))
        )
        for r in rows_result.scalars().all():
            data = r.normalized_data or r.data
            ts = None
            for tc in time_cols:
                ts = _parse_timestamp(data.get(tc))
                if ts:
                    break
            if ts:
                hostname = data.get("hostname") or data.get("Hostname") or data.get("Fqdn") or ""
                process = data.get("process_name") or data.get("Name") or data.get("ProcessName") or ""
                summary = data.get("command_line") or data.get("CommandLine") or data.get("Details") or ""
                events.append({
                    "timestamp": ts,
                    "dataset_id": ds.id,
                    "dataset_name": ds.name,
                    "artifact_type": artifact_type,
                    "row_index": r.row_index,
                    "hostname": str(hostname)[:128],
                    "process": str(process)[:128],
                    "summary": str(summary)[:256],
                    "data": {k: str(v)[:100] for k, v in list(data.items())[:8]},
                })

    # Sort by timestamp
    events.sort(key=lambda e: e["timestamp"])

    return {
        "hunt_id": hunt_id,
        "hunt_name": hunt.name,
        "event_count": len(events),
        "datasets": dataset_info,
        "events": events[:limit],
    }

"""API routes for cross-hunt correlation analysis."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.correlation import correlation_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/correlation", tags=["correlation"])


class CorrelateRequest(BaseModel):
    hunt_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=20,
        description="List of hunt IDs to correlate",
    )


@router.post(
    "/analyze",
    summary="Run correlation analysis across hunts",
    description="Find shared IOCs, overlapping time windows, common MITRE techniques, "
    "and host patterns across the specified hunts.",
)
async def correlate_hunts(
    body: CorrelateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await correlation_engine.correlate_hunts(body.hunt_ids, db)

    return {
        "hunt_ids": result.hunt_ids,
        "summary": result.summary,
        "total_correlations": result.total_correlations,
        "ioc_overlaps": [asdict(o) for o in result.ioc_overlaps],
        "time_overlaps": [asdict(o) for o in result.time_overlaps],
        "technique_overlaps": [asdict(o) for o in result.technique_overlaps],
        "host_overlaps": result.host_overlaps,
    }


@router.get(
    "/all",
    summary="Correlate all hunts",
    description="Run correlation across all hunts in the system.",
)
async def correlate_all(db: AsyncSession = Depends(get_db)):
    result = await correlation_engine.correlate_all(db)
    return {
        "hunt_ids": result.hunt_ids,
        "summary": result.summary,
        "total_correlations": result.total_correlations,
        "ioc_overlaps": [asdict(o) for o in result.ioc_overlaps[:20]],
        "time_overlaps": [asdict(o) for o in result.time_overlaps[:10]],
        "technique_overlaps": [asdict(o) for o in result.technique_overlaps[:10]],
        "host_overlaps": result.host_overlaps[:10],
    }


@router.get(
    "/ioc/{ioc_value}",
    summary="Find IOC across all hunts",
    description="Search for a specific IOC value across all datasets and hunts.",
)
async def find_ioc(
    ioc_value: str,
    db: AsyncSession = Depends(get_db),
):
    occurrences = await correlation_engine.find_ioc_across_hunts(ioc_value, db)
    return {
        "ioc_value": ioc_value,
        "occurrences": occurrences,
        "total": len(occurrences),
        "unique_hunts": len(set(o["hunt_id"] for o in occurrences if o.get("hunt_id"))),
    }

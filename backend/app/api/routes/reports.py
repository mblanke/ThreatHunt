"""API routes for report generation and export."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.reports import report_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/hunt/{hunt_id}",
    summary="Generate hunt investigation report",
    description="Generate a comprehensive report for a hunt. Supports JSON, HTML, and CSV formats.",
)
async def generate_hunt_report(
    hunt_id: str,
    format: str = Query("json", description="Report format: json, html, csv"),
    include_rows: bool = Query(False, description="Include raw data rows"),
    max_rows: int = Query(500, ge=0, le=5000, description="Max rows to include"),
    db: AsyncSession = Depends(get_db),
):
    result = await report_generator.generate_hunt_report(
        hunt_id, db, format=format,
        include_rows=include_rows, max_rows=max_rows,
    )

    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    if format == "html":
        return HTMLResponse(content=result, headers={
            "Content-Disposition": f"inline; filename=threathunt_report_{hunt_id}.html",
        })
    elif format == "csv":
        return PlainTextResponse(content=result, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename=threathunt_report_{hunt_id}.csv",
        })
    else:
        return result


@router.get(
    "/hunt/{hunt_id}/summary",
    summary="Quick hunt summary",
    description="Get a lightweight summary of the hunt for dashboard display.",
)
async def hunt_summary(
    hunt_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await report_generator.generate_hunt_report(
        hunt_id, db, format="json", include_rows=False,
    )
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "hunt": result.get("hunt"),
        "summary": result.get("summary"),
    }

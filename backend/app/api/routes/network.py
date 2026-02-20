"""API routes for Network Picture — deduplicated host inventory."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.network_inventory import build_network_picture

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["network"])


# ── Response models ───────────────────────────────────────────────────


class HostEntry(BaseModel):
    hostname: str
    ips: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)
    os: list[str] = Field(default_factory=list)
    mac_addresses: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    open_ports: list[str] = Field(default_factory=list)
    remote_targets: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    connection_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


class PictureSummary(BaseModel):
    total_hosts: int = 0
    total_connections: int = 0
    total_unique_ips: int = 0
    datasets_scanned: int = 0


class NetworkPictureResponse(BaseModel):
    hosts: list[HostEntry]
    summary: PictureSummary


# ── Routes ────────────────────────────────────────────────────────────


@router.get(
    "/picture",
    response_model=NetworkPictureResponse,
    summary="Build deduplicated host inventory for a hunt",
    description=(
        "Scans all datasets in the specified hunt, extracts host-identifying "
        "fields (hostname, IP, username, OS, MAC, ports), deduplicates by "
        "hostname, and returns a clean one-row-per-host network picture."
    ),
)
async def get_network_picture(
    hunt_id: str = Query(..., description="Hunt ID to scan"),
    db: AsyncSession = Depends(get_db),
):
    """Return a deduplicated network picture for a hunt."""
    if not hunt_id:
        raise HTTPException(status_code=400, detail="hunt_id is required")

    result = await build_network_picture(db, hunt_id)
    return result

"""Network topology API - host inventory endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.host_inventory import build_host_inventory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/host-inventory")
async def get_host_inventory(
    hunt_id: str = Query(..., description="Hunt ID to build inventory for"),
    db: AsyncSession = Depends(get_db),
):
    """Build a deduplicated host inventory from all datasets in a hunt.

    Returns unique hosts with hostname, IPs, OS, logged-in users, and
    network connections derived from netstat/connection data.
    """
    result = await build_host_inventory(hunt_id, db)
    if result["stats"]["total_hosts"] == 0:
        return result
    return result
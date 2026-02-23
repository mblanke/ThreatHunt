<<<<<<< HEAD
"""Network topology API - host inventory endpoint with background caching."""
=======
"""API routes for Network Picture — deduplicated host inventory."""
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
<<<<<<< HEAD
from fastapi.responses import JSONResponse
=======
from pydantic import BaseModel, Field
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
<<<<<<< HEAD
from app.services.host_inventory import build_host_inventory, inventory_cache
from app.services.job_queue import job_queue, JobType
=======
from app.services.network_inventory import build_network_picture
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["network"])


<<<<<<< HEAD
@router.get("/host-inventory")
async def get_host_inventory(
    hunt_id: str = Query(..., description="Hunt ID to build inventory for"),
    force: bool = Query(False, description="Force rebuild, ignoring cache"),
    db: AsyncSession = Depends(get_db),
):
    """Return a deduplicated host inventory for the hunt.

    Returns instantly from cache if available (pre-built after upload or on startup).
    If cache is cold, triggers a background build and returns 202 so the
    frontend can poll /inventory-status and re-request when ready.
    """
    # Force rebuild: invalidate cache, queue background job, return 202
    if force:
        inventory_cache.invalidate(hunt_id)
        if not inventory_cache.is_building(hunt_id):
            if job_queue.is_backlogged():
                return JSONResponse(status_code=202, content={"status": "deferred", "message": "Queue busy, retry shortly"})
            job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
        return JSONResponse(
            status_code=202,
            content={"status": "building", "message": "Rebuild queued"},
        )

    # Try cache first
    cached = inventory_cache.get(hunt_id)
    if cached is not None:
        logger.info(f"Serving cached host inventory for {hunt_id}")
        return cached

    # Cache miss: trigger background build instead of blocking for 90+ seconds
    if not inventory_cache.is_building(hunt_id):
        logger.info(f"Cache miss for {hunt_id}, triggering background build")
        if job_queue.is_backlogged():
            return JSONResponse(status_code=202, content={"status": "deferred", "message": "Queue busy, retry shortly"})
        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)

    return JSONResponse(
        status_code=202,
        content={"status": "building", "message": "Inventory is being built in the background"},
    )


def _build_summary(inv: dict, top_n: int = 20) -> dict:
    hosts = inv.get("hosts", [])
    conns = inv.get("connections", [])
    top_hosts = sorted(hosts, key=lambda h: h.get("row_count", 0), reverse=True)[:top_n]
    top_edges = sorted(conns, key=lambda c: c.get("count", 0), reverse=True)[:top_n]
    return {
        "stats": inv.get("stats", {}),
        "top_hosts": [
            {
                "id": h.get("id"),
                "hostname": h.get("hostname"),
                "row_count": h.get("row_count", 0),
                "ip_count": len(h.get("ips", [])),
                "user_count": len(h.get("users", [])),
            }
            for h in top_hosts
        ],
        "top_edges": top_edges,
    }


def _build_subgraph(inv: dict, node_id: str | None, max_hosts: int, max_edges: int) -> dict:
    hosts = inv.get("hosts", [])
    conns = inv.get("connections", [])

    max_hosts = max(1, min(max_hosts, settings.NETWORK_SUBGRAPH_MAX_HOSTS))
    max_edges = max(1, min(max_edges, settings.NETWORK_SUBGRAPH_MAX_EDGES))

    if node_id:
        rel_edges = [c for c in conns if c.get("source") == node_id or c.get("target") == node_id]
        rel_edges = sorted(rel_edges, key=lambda c: c.get("count", 0), reverse=True)[:max_edges]
        ids = {node_id}
        for c in rel_edges:
            ids.add(c.get("source"))
            ids.add(c.get("target"))
        rel_hosts = [h for h in hosts if h.get("id") in ids][:max_hosts]
    else:
        rel_hosts = sorted(hosts, key=lambda h: h.get("row_count", 0), reverse=True)[:max_hosts]
        allowed = {h.get("id") for h in rel_hosts}
        rel_edges = [
            c for c in sorted(conns, key=lambda c: c.get("count", 0), reverse=True)
            if c.get("source") in allowed and c.get("target") in allowed
        ][:max_edges]

    return {
        "hosts": rel_hosts,
        "connections": rel_edges,
        "stats": {
            **inv.get("stats", {}),
            "subgraph_hosts": len(rel_hosts),
            "subgraph_connections": len(rel_edges),
            "truncated": len(rel_hosts) < len(hosts) or len(rel_edges) < len(conns),
        },
    }


@router.get("/summary")
async def get_inventory_summary(
    hunt_id: str = Query(..., description="Hunt ID"),
    top_n: int = Query(20, ge=1, le=200),
):
    """Return a lightweight summary view for large hunts."""
    cached = inventory_cache.get(hunt_id)
    if cached is None:
        if not inventory_cache.is_building(hunt_id):
            if job_queue.is_backlogged():
                return JSONResponse(
                    status_code=202,
                    content={"status": "deferred", "message": "Queue busy, retry shortly"},
                )
            job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
        return JSONResponse(status_code=202, content={"status": "building"})
    return _build_summary(cached, top_n=top_n)


@router.get("/subgraph")
async def get_inventory_subgraph(
    hunt_id: str = Query(..., description="Hunt ID"),
    node_id: str | None = Query(None, description="Optional focal node"),
    max_hosts: int = Query(200, ge=1, le=5000),
    max_edges: int = Query(1500, ge=1, le=20000),
):
    """Return a bounded subgraph for scale-safe rendering."""
    cached = inventory_cache.get(hunt_id)
    if cached is None:
        if not inventory_cache.is_building(hunt_id):
            if job_queue.is_backlogged():
                return JSONResponse(
                    status_code=202,
                    content={"status": "deferred", "message": "Queue busy, retry shortly"},
                )
            job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
        return JSONResponse(status_code=202, content={"status": "building"})
    return _build_subgraph(cached, node_id=node_id, max_hosts=max_hosts, max_edges=max_edges)


@router.get("/inventory-status")
async def get_inventory_status(
    hunt_id: str = Query(..., description="Hunt ID to check"),
):
    """Check whether pre-computed host inventory is ready for a hunt.

    Returns: { status: "ready" | "building" | "none" }
    """
    return {"hunt_id": hunt_id, "status": inventory_cache.status(hunt_id)}


@router.post("/rebuild-inventory")
async def trigger_rebuild(
    hunt_id: str = Query(..., description="Hunt to rebuild inventory for"),
):
    """Trigger a background rebuild of the host inventory cache."""
    inventory_cache.invalidate(hunt_id)
    job = job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
    return {"job_id": job.id, "status": "queued"}
=======
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
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2

from pathlib import Path
import re

root = Path(r"d:\Projects\Dev\ThreatHunt")

# ---------- config.py ----------
cfg = root / "backend/app/config.py"
text = cfg.read_text(encoding="utf-8")
marker = "    JOB_QUEUE_CLEANUP_MAX_AGE_SECONDS: int = Field(\n        default=3600, description=\"Age threshold for in-memory completed job cleanup\"\n    )\n"
add = marker + "\n    # -- Startup throttling ------------------------------------------------\n    STARTUP_WARMUP_MAX_HUNTS: int = Field(\n        default=5, description=\"Max hunts to warm inventory cache for at startup\"\n    )\n    STARTUP_REPROCESS_MAX_DATASETS: int = Field(\n        default=25, description=\"Max unprocessed datasets to enqueue at startup\"\n    )\n\n    # -- Network API scale guards -----------------------------------------\n    NETWORK_SUBGRAPH_MAX_HOSTS: int = Field(\n        default=400, description=\"Hard cap for hosts returned by network subgraph endpoint\"\n    )\n    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(\n        default=3000, description=\"Hard cap for edges returned by network subgraph endpoint\"\n    )\n"
if marker in text and "STARTUP_WARMUP_MAX_HUNTS" not in text:
    text = text.replace(marker, add)
cfg.write_text(text, encoding="utf-8")

# ---------- job_queue.py ----------
jq = root / "backend/app/services/job_queue.py"
text = jq.read_text(encoding="utf-8")

# add helper methods after get_stats
anchor = "    def get_stats(self) -> dict:\n        by_status = {}\n        for j in self._jobs.values():\n            by_status[j.status.value] = by_status.get(j.status.value, 0) + 1\n        return {\n            \"total\": len(self._jobs),\n            \"queued\": self._queue.qsize(),\n            \"by_status\": by_status,\n            \"workers\": self._max_workers,\n            \"active_workers\": sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING),\n        }\n"
if "def is_backlogged(" not in text:
    insert = anchor + "\n    def is_backlogged(self) -> bool:\n        return self._queue.qsize() >= settings.JOB_QUEUE_MAX_BACKLOG\n\n    def can_accept(self, reserve: int = 0) -> bool:\n        return (self._queue.qsize() + max(0, reserve)) < settings.JOB_QUEUE_MAX_BACKLOG\n"
    text = text.replace(anchor, insert)

jq.write_text(text, encoding="utf-8")

# ---------- host_inventory.py keyset pagination ----------
hi = root / "backend/app/services/host_inventory.py"
text = hi.read_text(encoding="utf-8")
old = '''        batch_size = 5000
        offset = 0
        while True:
            rr = await db.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .order_by(DatasetRow.row_index)
                .offset(offset).limit(batch_size)
            )
            rows = rr.scalars().all()
            if not rows:
                break
'''
new = '''        batch_size = 5000
        last_row_index = -1
        while True:
            rr = await db.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .where(DatasetRow.row_index > last_row_index)
                .order_by(DatasetRow.row_index)
                .limit(batch_size)
            )
            rows = rr.scalars().all()
            if not rows:
                break
'''
if old in text:
    text = text.replace(old, new)
text = text.replace("            offset += batch_size\n            if len(rows) < batch_size:\n                break\n", "            last_row_index = rows[-1].row_index\n            if len(rows) < batch_size:\n                break\n")
hi.write_text(text, encoding="utf-8")

# ---------- network.py add summary/subgraph + backpressure ----------
net = root / "backend/app/api/routes/network.py"
text = net.read_text(encoding="utf-8")
text = text.replace("from fastapi import APIRouter, Depends, HTTPException, Query", "from fastapi import APIRouter, Depends, HTTPException, Query")
if "from app.config import settings" not in text:
    text = text.replace("from app.db import get_db\n", "from app.config import settings\nfrom app.db import get_db\n")

# add helpers and endpoints before inventory-status endpoint
if "def _build_summary" not in text:
    helper_block = '''

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
'''
    text = text.replace("\n\n@router.get(\"/inventory-status\")", helper_block + "\n\n@router.get(\"/inventory-status\")")

# add backpressure in host-inventory enqueue points
text = text.replace(
"        if not inventory_cache.is_building(hunt_id):\n            job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)",
"        if not inventory_cache.is_building(hunt_id):\n            if job_queue.is_backlogged():\n                return JSONResponse(status_code=202, content={\"status\": \"deferred\", \"message\": \"Queue busy, retry shortly\"})\n            job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)"
)
text = text.replace(
"    if not inventory_cache.is_building(hunt_id):\n        logger.info(f\"Cache miss for {hunt_id}, triggering background build\")\n        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)",
"    if not inventory_cache.is_building(hunt_id):\n        logger.info(f\"Cache miss for {hunt_id}, triggering background build\")\n        if job_queue.is_backlogged():\n            return JSONResponse(status_code=202, content={\"status\": \"deferred\", \"message\": \"Queue busy, retry shortly\"})\n        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)"
)

net.write_text(text, encoding="utf-8")

# ---------- analysis.py backpressure on manual submit ----------
analysis = root / "backend/app/api/routes/analysis.py"
text = analysis.read_text(encoding="utf-8")
text = text.replace(
"    job = job_queue.submit(jt, **params)\n    return {\"job_id\": job.id, \"status\": job.status.value, \"job_type\": job_type}",
"    if not job_queue.can_accept():\n        raise HTTPException(status_code=429, detail=\"Job queue is busy. Retry shortly.\")\n    job = job_queue.submit(jt, **params)\n    return {\"job_id\": job.id, \"status\": job.status.value, \"job_type\": job_type}"
)
analysis.write_text(text, encoding="utf-8")

# ---------- main.py startup throttles ----------
main = root / "backend/app/main.py"
text = main.read_text(encoding="utf-8")

text = text.replace(
"    for hid in hunt_ids:\n        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hid)\n    if hunt_ids:\n        logger.info(f\"Queued host inventory warm-up for {len(hunt_ids)} hunts\")",
"    warm_hunts = hunt_ids[: settings.STARTUP_WARMUP_MAX_HUNTS]\n    for hid in warm_hunts:\n        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hid)\n    if warm_hunts:\n        logger.info(f\"Queued host inventory warm-up for {len(warm_hunts)} hunts (total hunts with data: {len(hunt_ids)})\")"
)

text = text.replace(
"    if unprocessed_ids:\n        for ds_id in unprocessed_ids:\n            job_queue.submit(JobType.TRIAGE, dataset_id=ds_id)\n            job_queue.submit(JobType.ANOMALY, dataset_id=ds_id)\n            job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=ds_id)\n            job_queue.submit(JobType.IOC_EXTRACT, dataset_id=ds_id)\n        logger.info(f\"Queued processing pipeline for {len(unprocessed_ids)} unprocessed datasets\")\n        async with async_session_factory() as update_db:\n            from sqlalchemy import update\n            from app.db.models import Dataset\n            await update_db.execute(\n                update(Dataset)\n                .where(Dataset.id.in_(unprocessed_ids))\n                .values(processing_status=\"processing\")\n            )\n            await update_db.commit()",
"    if unprocessed_ids:\n        to_reprocess = unprocessed_ids[: settings.STARTUP_REPROCESS_MAX_DATASETS]\n        for ds_id in to_reprocess:\n            job_queue.submit(JobType.TRIAGE, dataset_id=ds_id)\n            job_queue.submit(JobType.ANOMALY, dataset_id=ds_id)\n            job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=ds_id)\n            job_queue.submit(JobType.IOC_EXTRACT, dataset_id=ds_id)\n        logger.info(f\"Queued processing pipeline for {len(to_reprocess)} datasets at startup (unprocessed total: {len(unprocessed_ids)})\")\n        async with async_session_factory() as update_db:\n            from sqlalchemy import update\n            from app.db.models import Dataset\n            await update_db.execute(\n                update(Dataset)\n                .where(Dataset.id.in_(to_reprocess))\n                .values(processing_status=\"processing\")\n            )\n            await update_db.commit()"
)

main.write_text(text, encoding="utf-8")

print("Patched Phase 2 files")
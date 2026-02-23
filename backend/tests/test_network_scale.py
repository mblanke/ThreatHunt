"""Scale-oriented network endpoint tests (summary/subgraph/backpressure)."""

import pytest

from app.config import settings
from app.services.host_inventory import inventory_cache


@pytest.mark.asyncio
async def test_network_summary_from_cache(client):
    hunt_id = "scale-hunt-summary"
    inv = {
        "hosts": [
            {"id": "h1", "hostname": "H1", "ips": ["10.0.0.1"], "users": ["a"], "row_count": 50},
            {"id": "h2", "hostname": "H2", "ips": [], "users": [], "row_count": 10},
        ],
        "connections": [
            {"source": "h1", "target": "8.8.8.8", "count": 7},
            {"source": "h1", "target": "h2", "count": 3},
        ],
        "stats": {"total_hosts": 2, "total_rows_scanned": 60},
    }
    inventory_cache.put(hunt_id, inv)

    res = await client.get(f"/api/network/summary?hunt_id={hunt_id}&top_n=1")
    assert res.status_code == 200
    body = res.json()
    assert body["stats"]["total_hosts"] == 2
    assert len(body["top_hosts"]) == 1
    assert body["top_hosts"][0]["id"] == "h1"


@pytest.mark.asyncio
async def test_network_subgraph_truncates(client):
    hunt_id = "scale-hunt-subgraph"
    inv = {
        "hosts": [
            {"id": f"h{i}", "hostname": f"H{i}", "ips": [], "users": [], "row_count": 100 - i}
            for i in range(1, 8)
        ],
        "connections": [
            {"source": "h1", "target": "h2", "count": 20},
            {"source": "h1", "target": "h3", "count": 15},
            {"source": "h2", "target": "h4", "count": 5},
            {"source": "h3", "target": "h5", "count": 4},
        ],
        "stats": {"total_hosts": 7, "total_rows_scanned": 999},
    }
    inventory_cache.put(hunt_id, inv)

    res = await client.get(f"/api/network/subgraph?hunt_id={hunt_id}&max_hosts=3&max_edges=2")
    assert res.status_code == 200
    body = res.json()
    assert len(body["hosts"]) <= 3
    assert len(body["connections"]) <= 2
    assert body["stats"]["truncated"] is True


@pytest.mark.asyncio
async def test_manual_job_submit_backpressure_returns_429(client):
    old = settings.JOB_QUEUE_MAX_BACKLOG
    settings.JOB_QUEUE_MAX_BACKLOG = 0
    try:
        res = await client.post("/api/analysis/jobs/submit/triage", json={"params": {"dataset_id": "abc"}})
        assert res.status_code == 429
    finally:
        settings.JOB_QUEUE_MAX_BACKLOG = old
@pytest.mark.asyncio
async def test_network_host_inventory_deferred_when_queue_backlogged(client):
    hunt_id = "deferred-hunt"
    inventory_cache.invalidate(hunt_id)
    inventory_cache.clear_building(hunt_id)

    old = settings.JOB_QUEUE_MAX_BACKLOG
    settings.JOB_QUEUE_MAX_BACKLOG = 0
    try:
        res = await client.get(f"/api/network/host-inventory?hunt_id={hunt_id}")
        assert res.status_code == 202
        body = res.json()
        assert body["status"] == "deferred"
    finally:
        settings.JOB_QUEUE_MAX_BACKLOG = old

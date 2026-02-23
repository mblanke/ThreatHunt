"""Tests for network inventory endpoints and cache/polling behavior."""

import io

import pytest

from app.services.host_inventory import inventory_cache
from tests.conftest import SAMPLE_CSV


@pytest.mark.asyncio
async def test_inventory_status_none_for_unknown_hunt(client):
    hunt_id = "hunt-does-not-exist"
    inventory_cache.invalidate(hunt_id)
    inventory_cache.clear_building(hunt_id)

    res = await client.get(f"/api/network/inventory-status?hunt_id={hunt_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["hunt_id"] == hunt_id
    assert body["status"] == "none"


@pytest.mark.asyncio
async def test_host_inventory_cold_cache_returns_202(client):
    # Create hunt and upload dataset linked to that hunt
    hunt = await client.post("/api/hunts", json={"name": "Net Hunt"})
    hunt_id = hunt.json()["id"]

    files = {"file": ("network.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
    up = await client.post("/api/datasets/upload", files=files, params={"hunt_id": hunt_id})
    assert up.status_code == 200

    # Ensure cache is cold for this hunt
    inventory_cache.invalidate(hunt_id)
    inventory_cache.clear_building(hunt_id)

    res = await client.get(f"/api/network/host-inventory?hunt_id={hunt_id}")
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "building"


@pytest.mark.asyncio
async def test_host_inventory_ready_cache_returns_200(client):
    hunt = await client.post("/api/hunts", json={"name": "Ready Hunt"})
    hunt_id = hunt.json()["id"]

    mock_inventory = {
        "hosts": [
            {
                "id": "host-1",
                "hostname": "HOST-1",
                "fqdn": "HOST-1.local",
                "client_id": "C.1234abcd",
                "ips": ["10.0.0.10"],
                "os": "Windows 10",
                "users": ["alice"],
                "datasets": ["test"],
                "row_count": 5,
            }
        ],
        "connections": [],
        "stats": {
            "total_hosts": 1,
            "hosts_with_ips": 1,
            "hosts_with_users": 1,
            "total_datasets_scanned": 1,
            "total_rows_scanned": 5,
        },
    }

    inventory_cache.put(hunt_id, mock_inventory)

    res = await client.get(f"/api/network/host-inventory?hunt_id={hunt_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["stats"]["total_hosts"] == 1
    assert len(body["hosts"]) == 1
    assert body["hosts"][0]["hostname"] == "HOST-1"

    status_res = await client.get(f"/api/network/inventory-status?hunt_id={hunt_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "ready"
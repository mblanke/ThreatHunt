"""Tests for AUP keyword themes, keyword CRUD, and scanner."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Theme CRUD ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_themes_empty(client: AsyncClient):
    """Initially (no seed in tests) the themes list should be empty or seeded."""
    res = await client.get("/api/keywords/themes")
    assert res.status_code == 200
    data = res.json()
    assert "themes" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_theme(client: AsyncClient):
    res = await client.post("/api/keywords/themes", json={
        "name": "Test Gambling", "color": "#f44336", "enabled": True,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Gambling"
    assert data["color"] == "#f44336"
    assert data["enabled"] is True
    assert data["keyword_count"] == 0
    return data["id"]


@pytest.mark.asyncio
async def test_create_duplicate_theme(client: AsyncClient):
    await client.post("/api/keywords/themes", json={"name": "Dup Theme"})
    res = await client.post("/api/keywords/themes", json={"name": "Dup Theme"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_theme(client: AsyncClient):
    create = await client.post("/api/keywords/themes", json={"name": "Updatable"})
    tid = create.json()["id"]
    res = await client.put(f"/api/keywords/themes/{tid}", json={
        "name": "Updated Name", "color": "#00ff00", "enabled": False,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Name"
    assert data["color"] == "#00ff00"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_theme(client: AsyncClient):
    create = await client.post("/api/keywords/themes", json={"name": "ToDelete"})
    tid = create.json()["id"]
    res = await client.delete(f"/api/keywords/themes/{tid}")
    assert res.status_code == 204

    # Verify gone
    check = await client.get("/api/keywords/themes")
    names = [t["name"] for t in check.json()["themes"]]
    assert "ToDelete" not in names


@pytest.mark.asyncio
async def test_delete_nonexistent_theme(client: AsyncClient):
    res = await client.delete("/api/keywords/themes/nonexistent")
    assert res.status_code == 404


# ── Keyword CRUD ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_keyword(client: AsyncClient):
    create = await client.post("/api/keywords/themes", json={"name": "KW Test Theme"})
    tid = create.json()["id"]

    res = await client.post(f"/api/keywords/themes/{tid}/keywords", json={
        "value": "poker", "is_regex": False,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["value"] == "poker"
    assert data["is_regex"] is False
    assert data["theme_id"] == tid


@pytest.mark.asyncio
async def test_add_keywords_bulk(client: AsyncClient):
    create = await client.post("/api/keywords/themes", json={"name": "Bulk KW Theme"})
    tid = create.json()["id"]

    res = await client.post(f"/api/keywords/themes/{tid}/keywords/bulk", json={
        "values": ["steam", "epic games", "discord"],
    })
    assert res.status_code == 201
    data = res.json()
    assert data["added"] == 3
    assert data["theme_id"] == tid

    # Verify via theme list
    themes = await client.get("/api/keywords/themes")
    theme = [t for t in themes.json()["themes"] if t["id"] == tid][0]
    assert theme["keyword_count"] == 3


@pytest.mark.asyncio
async def test_delete_keyword(client: AsyncClient):
    create = await client.post("/api/keywords/themes", json={"name": "Del KW Theme"})
    tid = create.json()["id"]

    kw_res = await client.post(f"/api/keywords/themes/{tid}/keywords", json={"value": "removeme"})
    kw_id = kw_res.json()["id"]

    res = await client.delete(f"/api/keywords/keywords/{kw_id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_add_keyword_to_nonexistent_theme(client: AsyncClient):
    res = await client.post("/api/keywords/themes/fakeid/keywords", json={"value": "test"})
    assert res.status_code == 404


# ── Scanner ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scan_empty(client: AsyncClient):
    """Scan with no data should return zero hits."""
    res = await client.post("/api/keywords/scan", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["total_hits"] == 0
    assert data["hits"] == []


@pytest.mark.asyncio
async def test_scan_with_dataset(client: AsyncClient):
    """Upload a dataset with known keywords, verify scanner finds them."""
    # Create a theme + keyword
    theme_res = await client.post("/api/keywords/themes", json={
        "name": "Scan Test", "color": "#ff0000",
    })
    tid = theme_res.json()["id"]
    await client.post(f"/api/keywords/themes/{tid}/keywords", json={"value": "chrome.exe"})

    # Upload CSV dataset that contains "chrome.exe"
    from tests.conftest import SAMPLE_CSV
    import io
    files = {"file": ("test_scan.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
    upload = await client.post("/api/datasets/upload", files=files)
    assert upload.status_code == 200
    ds_id = upload.json()["id"]

    # Scan
    res = await client.post("/api/keywords/scan", json={
        "dataset_ids": [ds_id],
        "theme_ids": [tid],
        "scan_hunts": False,
        "scan_annotations": False,
        "scan_messages": False,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total_hits"] > 0
    # Verify the hit references chrome.exe
    kw_hits = [h for h in data["hits"] if h["keyword"] == "chrome.exe"]
    assert len(kw_hits) > 0


@pytest.mark.asyncio
async def test_quick_scan(client: AsyncClient):
    """Quick scan endpoint should work with a dataset_id parameter."""
    # Create theme + keyword
    theme_res = await client.post("/api/keywords/themes", json={
        "name": "Quick Scan Theme", "color": "#00ff00",
    })
    tid = theme_res.json()["id"]
    await client.post(f"/api/keywords/themes/{tid}/keywords", json={"value": "powershell"})

    # Upload dataset
    from tests.conftest import SAMPLE_CSV
    import io
    files = {"file": ("quick_scan.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
    upload = await client.post("/api/datasets/upload", files=files)
    ds_id = upload.json()["id"]

    res = await client.get(f"/api/keywords/scan/quick?dataset_id={ds_id}")
    assert res.status_code == 200
    data = res.json()
    assert "total_hits" in data
    # powershell should match at least one row
    assert data["total_hits"] > 0


@pytest.mark.asyncio
async def test_quick_scan_cache_hit(client: AsyncClient):
    """Second quick scan should return cache hit metadata."""
    theme_res = await client.post("/api/keywords/themes", json={"name": "Quick Cache Theme", "color": "#00aa00"})
    tid = theme_res.json()["id"]
    await client.post(f"/api/keywords/themes/{tid}/keywords", json={"value": "chrome.exe"})

    from tests.conftest import SAMPLE_CSV
    import io
    files = {"file": ("cache_quick.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
    upload = await client.post("/api/datasets/upload", files=files)
    ds_id = upload.json()["id"]

    first = await client.get(f"/api/keywords/scan/quick?dataset_id={ds_id}")
    assert first.status_code == 200
    assert first.json().get("cache_status") in ("miss", "hit")

    second = await client.get(f"/api/keywords/scan/quick?dataset_id={ds_id}")
    assert second.status_code == 200
    body = second.json()
    assert body.get("cache_used") is True
    assert body.get("cache_status") == "hit"

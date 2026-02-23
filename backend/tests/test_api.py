"""Tests for API endpoints — datasets, hunts, annotations."""

import io
import pytest
from tests.conftest import SAMPLE_CSV


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test basic health endpoints."""

    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ThreatHunt API"
        assert data["status"] == "running"

    async def test_openapi_docs(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "/api/agent/assist" in data["paths"]
        assert "/api/datasets/upload" in data["paths"]
        assert "/api/hunts" in data["paths"]


@pytest.mark.asyncio
class TestHuntEndpoints:
    """Test hunt CRUD operations."""

    async def test_create_hunt(self, client):
        resp = await client.post("/api/hunts", json={
            "name": "Test Hunt",
            "description": "Testing hunt creation",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Hunt"
        assert data["status"] == "active"
        assert data["id"]

    async def test_list_hunts(self, client):
        # Create a hunt first
        await client.post("/api/hunts", json={"name": "Hunt 1"})
        await client.post("/api/hunts", json={"name": "Hunt 2"})

        resp = await client.get("/api/hunts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    async def test_get_hunt(self, client):
        # Create
        create_resp = await client.post("/api/hunts", json={"name": "Specific Hunt"})
        hunt_id = create_resp.json()["id"]

        # Get
        resp = await client.get(f"/api/hunts/{hunt_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Specific Hunt"

    async def test_update_hunt(self, client):
        create_resp = await client.post("/api/hunts", json={"name": "Original"})
        hunt_id = create_resp.json()["id"]

        resp = await client.put(f"/api/hunts/{hunt_id}", json={
            "name": "Updated",
            "status": "closed",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["status"] == "closed"

    async def test_get_nonexistent_hunt(self, client):
        resp = await client.get("/api/hunts/nonexistent-id")
        assert resp.status_code == 404


    async def test_hunt_progress(self, client):
        create = await client.post("/api/hunts", json={"name": "Progress Hunt"})
        hunt_id = create.json()["id"]

        # attach one dataset so progress has scope
        from tests.conftest import SAMPLE_CSV
        import io
        files = {"file": ("progress.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
        up = await client.post(f"/api/datasets/upload?hunt_id={hunt_id}", files=files)
        assert up.status_code == 200

        res = await client.get(f"/api/hunts/{hunt_id}/progress")
        assert res.status_code == 200
        body = res.json()
        assert body["hunt_id"] == hunt_id
        assert "progress_percent" in body
        assert "dataset_total" in body
        assert "network_status" in body


@pytest.mark.asyncio
class TestDatasetEndpoints:
    """Test dataset upload and retrieval."""

    async def test_upload_csv(self, client):
        files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
        resp = await client.post(
            "/api/datasets/upload",
            files=files,
            params={"name": "Test Dataset"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Dataset"
        assert data["row_count"] == 5
        assert "timestamp" in data["columns"]

    async def test_upload_invalid_extension(self, client):
        files = {"file": ("bad.exe", io.BytesIO(b"not csv"), "application/octet-stream")}
        resp = await client.post("/api/datasets/upload", files=files)
        assert resp.status_code == 400

    async def test_upload_empty_file(self, client):
        files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
        resp = await client.post("/api/datasets/upload", files=files)
        assert resp.status_code == 400

    async def test_list_datasets(self, client):
        # Upload first
        files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
        await client.post("/api/datasets/upload", files=files, params={"name": "DS1"})

        resp = await client.get("/api/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_get_dataset_rows(self, client):
        files = {"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
        upload_resp = await client.post("/api/datasets/upload", files=files, params={"name": "RowTest"})
        ds_id = upload_resp.json()["id"]

        resp = await client.get(f"/api/datasets/{ds_id}/rows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["rows"]) == 5


@pytest.mark.asyncio
class TestAnnotationEndpoints:
    """Test annotation CRUD."""

    async def test_create_annotation(self, client):
        resp = await client.post("/api/annotations", json={
            "text": "Suspicious process detected",
            "severity": "high",
            "tag": "suspicious",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Suspicious process detected"
        assert data["severity"] == "high"

    async def test_list_annotations(self, client):
        await client.post("/api/annotations", json={"text": "Ann 1", "severity": "info"})
        await client.post("/api/annotations", json={"text": "Ann 2", "severity": "critical"})

        resp = await client.get("/api/annotations")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    async def test_filter_annotations_by_severity(self, client):
        await client.post("/api/annotations", json={"text": "Critical finding", "severity": "critical"})

        resp = await client.get("/api/annotations", params={"severity": "critical"})
        assert resp.status_code == 200
        for ann in resp.json()["annotations"]:
            assert ann["severity"] == "critical"


@pytest.mark.asyncio
class TestHypothesisEndpoints:
    """Test hypothesis CRUD."""

    async def test_create_hypothesis(self, client):
        resp = await client.post("/api/hypotheses", json={
            "title": "Living off the Land",
            "description": "Attacker using LOLBins for execution",
            "mitre_technique": "T1059",
            "status": "active",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Living off the Land"
        assert data["mitre_technique"] == "T1059"

    async def test_update_hypothesis_status(self, client):
        create_resp = await client.post("/api/hypotheses", json={
            "title": "Test Hyp",
            "status": "draft",
        })
        hyp_id = create_resp.json()["id"]

        resp = await client.put(f"/api/hypotheses/{hyp_id}", json={
            "status": "confirmed",
            "evidence_notes": "Confirmed via process tree analysis",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

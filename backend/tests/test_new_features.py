"""Tests for new feature API routes: MITRE, Timeline, Playbooks, Saved Searches."""

import pytest
import pytest_asyncio


class TestMitreRoutes:
    """Tests for /api/mitre endpoints."""

    @pytest.mark.asyncio
    async def test_mitre_coverage_empty(self, client):
        resp = await client.get("/api/mitre/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert "tactics" in data
        assert "technique_count" in data
        assert data["technique_count"] == 0
        assert len(data["tactics"]) == 14  # 14 MITRE tactics

    @pytest.mark.asyncio
    async def test_mitre_coverage_with_hunt_filter(self, client):
        resp = await client.get("/api/mitre/coverage?hunt_id=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["technique_count"] == 0


class TestTimelineRoutes:
    """Tests for /api/timeline endpoints."""

    @pytest.mark.asyncio
    async def test_timeline_hunt_not_found(self, client):
        resp = await client.get("/api/timeline/hunt/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_timeline_with_hunt(self, client):
        # Create a hunt first
        hunt_resp = await client.post("/api/hunts", json={"name": "Timeline Test"})
        assert hunt_resp.status_code in (200, 201)
        hunt_id = hunt_resp.json()["id"]

        resp = await client.get(f"/api/timeline/hunt/{hunt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hunt_id"] == hunt_id
        assert "events" in data
        assert "datasets" in data


class TestPlaybookRoutes:
    """Tests for /api/playbooks endpoints."""

    @pytest.mark.asyncio
    async def test_list_playbooks_empty(self, client):
        resp = await client.get("/api/playbooks")
        assert resp.status_code == 200
        assert resp.json()["playbooks"] == []

    @pytest.mark.asyncio
    async def test_get_templates(self, client):
        resp = await client.get("/api/playbooks/templates")
        assert resp.status_code == 200
        templates = resp.json()["templates"]
        assert len(templates) >= 2
        assert templates[0]["name"] == "Standard Threat Hunt"

    @pytest.mark.asyncio
    async def test_create_playbook(self, client):
        resp = await client.post("/api/playbooks", json={
            "name": "My Investigation",
            "description": "Test playbook",
            "steps": [
                {"title": "Step 1", "description": "Upload data", "step_type": "upload", "target_route": "/upload"},
                {"title": "Step 2", "description": "Triage", "step_type": "analysis", "target_route": "/analysis"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Investigation"
        assert len(data["steps"]) == 2

    @pytest.mark.asyncio
    async def test_playbook_crud(self, client):
        # Create
        resp = await client.post("/api/playbooks", json={
            "name": "CRUD Test",
            "steps": [{"title": "Do something"}],
        })
        assert resp.status_code == 201
        pb_id = resp.json()["id"]

        # Get
        resp = await client.get(f"/api/playbooks/{pb_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "CRUD Test"
        assert len(resp.json()["steps"]) == 1

        # Update
        resp = await client.put(f"/api/playbooks/{pb_id}", json={"name": "Updated"})
        assert resp.status_code == 200

        # Delete
        resp = await client.delete(f"/api/playbooks/{pb_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_playbook_step_completion(self, client):
        # Create with step
        resp = await client.post("/api/playbooks", json={
            "name": "Step Test",
            "steps": [{"title": "Task 1"}],
        })
        pb_id = resp.json()["id"]

        # Get to find step ID
        resp = await client.get(f"/api/playbooks/{pb_id}")
        steps = resp.json()["steps"]
        step_id = steps[0]["id"]
        assert steps[0]["is_completed"] is False

        # Mark complete
        resp = await client.put(f"/api/playbooks/steps/{step_id}", json={"is_completed": True, "notes": "Done!"})
        assert resp.status_code == 200
        assert resp.json()["is_completed"] is True


class TestSavedSearchRoutes:
    """Tests for /api/searches endpoints."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        resp = await client.get("/api/searches")
        assert resp.status_code == 200
        assert resp.json()["searches"] == []

    @pytest.mark.asyncio
    async def test_create_saved_search(self, client):
        resp = await client.post("/api/searches", json={
            "name": "Suspicious IPs",
            "search_type": "ioc_search",
            "query_params": {"ioc_value": "203.0.113"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Suspicious IPs"
        assert data["search_type"] == "ioc_search"

    @pytest.mark.asyncio
    async def test_search_crud(self, client):
        # Create
        resp = await client.post("/api/searches", json={
            "name": "Test Query",
            "search_type": "keyword_scan",
            "query_params": {"theme": "malware"},
        })
        s_id = resp.json()["id"]

        # Get
        resp = await client.get(f"/api/searches/{s_id}")
        assert resp.status_code == 200

        # Update
        resp = await client.put(f"/api/searches/{s_id}", json={"name": "Updated Query"})
        assert resp.status_code == 200

        # Run
        resp = await client.post(f"/api/searches/{s_id}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "result_count" in data
        assert "delta" in data

        # Delete
        resp = await client.delete(f"/api/searches/{s_id}")
        assert resp.status_code == 200



class TestStixExport:
    """Tests for /api/export/stix endpoints."""

    @pytest.mark.asyncio
    async def test_stix_export_hunt_not_found(self, client):
        resp = await client.get("/api/export/stix/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stix_export_empty_hunt(self, client):
        """Export from a real hunt with no data returns valid but minimal bundle."""
        hunt_resp = await client.post("/api/hunts", json={"name": "STIX Test Hunt"})
        assert hunt_resp.status_code in (200, 201)
        hunt_id = hunt_resp.json()["id"]

        resp = await client.get(f"/api/export/stix/{hunt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "bundle"
        assert data["objects"][0]["spec_version"] == "2.1"  # spec_version is on objects, not bundle
        assert "objects" in data
        # At minimum should have the identity object
        types = [o["type"] for o in data["objects"]]
        assert "identity" in types


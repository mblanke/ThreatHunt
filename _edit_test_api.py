from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/tests/test_api.py')
t=p.read_text(encoding='utf-8')
insert='''
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
'''
needle='''    async def test_get_nonexistent_hunt(self, client):
        resp = await client.get("/api/hunts/nonexistent-id")
        assert resp.status_code == 404
'''
if needle in t and 'test_hunt_progress' not in t:
    t=t.replace(needle, needle+'\n'+insert)
p.write_text(t,encoding='utf-8')
print('updated test_api.py')

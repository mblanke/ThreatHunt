from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/tests/test_keywords.py')
t=p.read_text(encoding='utf-8')
add='''

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
'''
if 'test_quick_scan_cache_hit' not in t:
    t=t + add
p.write_text(t,encoding='utf-8')
print('updated test_keywords.py')

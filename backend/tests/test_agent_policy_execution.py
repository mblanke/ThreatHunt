"""Tests for execution-mode behavior in /api/agent/assist."""

import io

import pytest


@pytest.mark.asyncio
async def test_agent_assist_policy_query_executes_scan(client):
    # 1) Create hunt
    h = await client.post("/api/hunts", json={"name": "Policy Hunt"})
    assert h.status_code == 200
    hunt_id = h.json()["id"]

    # 2) Upload browser-history-like CSV
    csv_bytes = (
        b"User,visited_url,title,ClientId,Fqdn\n"
        b"Alice,https://www.pornhub.com/view_video.php,site,HOST-A,host-a.local\n"
        b"Bob,https://news.example.org/article,news,HOST-B,host-b.local\n"
    )
    files = {"file": ("web_history.csv", io.BytesIO(csv_bytes), "text/csv")}
    up = await client.post(f"/api/datasets/upload?hunt_id={hunt_id}", files=files)
    assert up.status_code == 200

    # 3) Ensure policy theme/keyword exists
    t = await client.post(
        "/api/keywords/themes",
        json={
            "name": "Adult Content",
            "color": "#e91e63",
            "enabled": True,
        },
    )
    assert t.status_code in (201, 409)

    themes = await client.get("/api/keywords/themes")
    assert themes.status_code == 200
    adult = next(x for x in themes.json()["themes"] if x["name"] == "Adult Content")

    k = await client.post(
        f"/api/keywords/themes/{adult['id']}/keywords",
        json={"value": "pornhub", "is_regex": False},
    )
    assert k.status_code in (201, 409)

    # 4) Execution-mode query
    q = await client.post(
        "/api/agent/assist",
        json={
            "query": "Analyze browser history for policy-violating domains and summarize by user and host.",
            "hunt_id": hunt_id,
        },
    )
    assert q.status_code == 200
    body = q.json()

    assert body["model_used"] == "execution:keyword_scanner"
    assert body["execution"] is not None
    assert body["execution"]["policy_hits"] >= 1
    assert len(body["execution"]["top_user_hosts"]) >= 1


@pytest.mark.asyncio
async def test_agent_assist_execution_preference_off_stays_advisory(client):
    h = await client.post("/api/hunts", json={"name": "No Exec Hunt"})
    assert h.status_code == 200
    hunt_id = h.json()["id"]

    q = await client.post(
        "/api/agent/assist",
        json={
            "query": "Analyze browser history for policy-violating domains and summarize by user and host.",
            "hunt_id": hunt_id,
            "execution_preference": "off",
        },
    )
    assert q.status_code == 200
    body = q.json()
    assert body["model_used"] != "execution:keyword_scanner"
    assert body["execution"] is None


@pytest.mark.asyncio
async def test_agent_assist_execution_preference_force_executes(client):
    # Create hunt + dataset even when the query text is not policy-specific
    h = await client.post("/api/hunts", json={"name": "Force Exec Hunt"})
    assert h.status_code == 200
    hunt_id = h.json()["id"]

    csv_bytes = (
        b"User,visited_url,title,ClientId,Fqdn\n"
        b"Alice,https://www.pornhub.com/view_video.php,site,HOST-A,host-a.local\n"
    )
    files = {"file": ("web_history.csv", io.BytesIO(csv_bytes), "text/csv")}
    up = await client.post(f"/api/datasets/upload?hunt_id={hunt_id}", files=files)
    assert up.status_code == 200

    t = await client.post(
        "/api/keywords/themes",
        json={"name": "Adult Content", "color": "#e91e63", "enabled": True},
    )
    assert t.status_code in (201, 409)

    themes = await client.get("/api/keywords/themes")
    assert themes.status_code == 200
    adult = next(x for x in themes.json()["themes"] if x["name"] == "Adult Content")
    k = await client.post(
        f"/api/keywords/themes/{adult['id']}/keywords",
        json={"value": "pornhub", "is_regex": False},
    )
    assert k.status_code in (201, 409)

    q = await client.post(
        "/api/agent/assist",
        json={
            "query": "Summarize notable activity in this hunt.",
            "hunt_id": hunt_id,
            "execution_preference": "force",
        },
    )
    assert q.status_code == 200
    body = q.json()
    assert body["model_used"] == "execution:keyword_scanner"
    assert body["execution"] is not None

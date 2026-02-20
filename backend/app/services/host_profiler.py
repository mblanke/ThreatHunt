"""Host profiler - per-host deep threat analysis via Wile heavy models."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session
from app.db.models import Dataset, DatasetRow, HostProfile, TriageResult

logger = logging.getLogger(__name__)

HEAVY_MODEL = settings.DEFAULT_HEAVY_MODEL
WILE_URL = f"{settings.wile_url}/api/generate"


async def _get_triage_summary(db, dataset_id: str) -> str:
    result = await db.execute(
        select(TriageResult)
        .where(TriageResult.dataset_id == dataset_id)
        .where(TriageResult.risk_score >= 3.0)
        .order_by(TriageResult.risk_score.desc())
        .limit(10)
    )
    triages = result.scalars().all()
    if not triages:
        return "No significant triage findings."
    lines = []
    for t in triages:
        lines.append(
            f"- Rows {t.row_start}-{t.row_end}: risk={t.risk_score:.1f} "
            f"verdict={t.verdict} findings={json.dumps(t.findings, default=str)[:300]}"
        )
    return "\n".join(lines)


async def _collect_host_data(db, hunt_id: str, hostname: str, fqdn: str | None = None) -> dict:
    result = await db.execute(select(Dataset).where(Dataset.hunt_id == hunt_id))
    datasets = result.scalars().all()

    host_data: dict[str, list[dict]] = {}
    triage_parts: list[str] = []

    for ds in datasets:
        artifact_type = getattr(ds, "artifact_type", None) or "Unknown"
        rows_result = await db.execute(
            select(DatasetRow).where(DatasetRow.dataset_id == ds.id).limit(500)
        )
        rows = rows_result.scalars().all()

        matching = []
        for r in rows:
            data = r.normalized_data or r.data
            row_host = (
                data.get("hostname", "") or data.get("Fqdn", "")
                or data.get("ClientId", "") or data.get("client_id", "")
            )
            if hostname.lower() in str(row_host).lower():
                matching.append(data)
            elif fqdn and fqdn.lower() in str(row_host).lower():
                matching.append(data)

        if matching:
            host_data[artifact_type] = matching[:50]
            triage_info = await _get_triage_summary(db, ds.id)
            triage_parts.append(f"\n### {artifact_type} ({len(matching)} rows)\n{triage_info}")

    return {
        "artifacts": host_data,
        "triage_summary": "\n".join(triage_parts) or "No triage data.",
        "artifact_count": sum(len(v) for v in host_data.values()),
    }


async def profile_host(
    hunt_id: str, hostname: str, fqdn: str | None = None, client_id: str | None = None,
) -> None:
    logger.info("Profiling host %s in hunt %s", hostname, hunt_id)

    async with async_session() as db:
        host_data = await _collect_host_data(db, hunt_id, hostname, fqdn)
        if host_data["artifact_count"] == 0:
            logger.info("No data found for host %s, skipping", hostname)
            return

        system_prompt = (
            "You are a senior threat hunting analyst performing deep host analysis.\n"
            "You receive consolidated forensic artifacts and prior triage results for a single host.\n\n"
            "Provide a comprehensive host threat profile as JSON:\n"
            "- risk_score: 0.0 (clean) to 10.0 (actively compromised)\n"
            "- risk_level: low/medium/high/critical\n"
            "- suspicious_findings: list of specific concerns\n"
            "- mitre_techniques: list of MITRE ATT&CK technique IDs\n"
            "- timeline_summary: brief timeline of suspicious activity\n"
            "- analysis: detailed narrative assessment\n\n"
            "Consider: cross-artifact correlation, attack patterns, LOLBins, anomalies.\n"
            "Respond with valid JSON only."
        )

        artifact_summary = {}
        for art_type, rows in host_data["artifacts"].items():
            artifact_summary[art_type] = [
                {k: str(v)[:150] for k, v in row.items() if v} for row in rows[:20]
            ]

        prompt = (
            f"Host: {hostname}\nFQDN: {fqdn or 'unknown'}\n\n"
            f"## Prior Triage Results\n{host_data['triage_summary']}\n\n"
            f"## Artifact Data ({host_data['artifact_count']} total rows)\n"
            f"{json.dumps(artifact_summary, indent=1, default=str)[:8000]}\n\n"
            "Provide your comprehensive host threat profile as JSON."
        )

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    WILE_URL,
                    json={
                        "model": HEAVY_MODEL,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 4096},
                    },
                )
                resp.raise_for_status()
                llm_text = resp.json().get("response", "")

            from app.services.triage import _parse_llm_response
            parsed = _parse_llm_response(llm_text)

            profile = HostProfile(
                hunt_id=hunt_id,
                hostname=hostname,
                fqdn=fqdn,
                client_id=client_id,
                risk_score=float(parsed.get("risk_score", 0.0)),
                risk_level=parsed.get("risk_level", "low"),
                artifact_summary={a: len(r) for a, r in host_data["artifacts"].items()},
                timeline_summary=parsed.get("timeline_summary", ""),
                suspicious_findings=parsed.get("suspicious_findings", []),
                mitre_techniques=parsed.get("mitre_techniques", []),
                llm_analysis=parsed.get("analysis", llm_text[:5000]),
                model_used=HEAVY_MODEL,
                node_used="wile",
            )
            db.add(profile)
            await db.commit()
            logger.info("Host profile %s: risk=%.1f level=%s", hostname, profile.risk_score, profile.risk_level)

        except Exception as e:
            logger.error("Failed to profile host %s: %s", hostname, e)
            profile = HostProfile(
                hunt_id=hunt_id, hostname=hostname, fqdn=fqdn,
                risk_score=0.0, risk_level="unknown",
                llm_analysis=f"Error: {e}",
                model_used=HEAVY_MODEL, node_used="wile",
            )
            db.add(profile)
            await db.commit()


async def profile_all_hosts(hunt_id: str) -> None:
    logger.info("Starting host profiling for hunt %s", hunt_id)

    async with async_session() as db:
        result = await db.execute(select(Dataset).where(Dataset.hunt_id == hunt_id))
        datasets = result.scalars().all()

        hostnames: dict[str, str | None] = {}
        for ds in datasets:
            rows_result = await db.execute(
                select(DatasetRow).where(DatasetRow.dataset_id == ds.id).limit(2000)
            )
            for r in rows_result.scalars().all():
                data = r.normalized_data or r.data
                host = data.get("hostname") or data.get("Fqdn") or data.get("Hostname")
                if host and str(host).strip():
                    h = str(host).strip()
                    if h not in hostnames:
                        hostnames[h] = data.get("fqdn") or data.get("Fqdn")

    logger.info("Discovered %d unique hosts in hunt %s", len(hostnames), hunt_id)

    semaphore = asyncio.Semaphore(settings.HOST_PROFILE_CONCURRENCY)

    async def _bounded(hostname: str, fqdn: str | None):
        async with semaphore:
            await profile_host(hunt_id, hostname, fqdn)

    tasks = [_bounded(h, f) for h, f in hostnames.items()]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Host profiling complete for hunt %s (%d hosts)", hunt_id, len(hostnames))
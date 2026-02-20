"""Auto-triage service - fast LLM analysis of dataset batches via Roadrunner."""

from __future__ import annotations

import json
import logging
import re

import httpx
from sqlalchemy import func, select

from app.config import settings
from app.db.engine import async_session
from app.db.models import Dataset, DatasetRow, TriageResult

logger = logging.getLogger(__name__)

DEFAULT_FAST_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
ROADRUNNER_URL = f"{settings.roadrunner_url}/api/generate"

ARTIFACT_FOCUS = {
    "Windows.System.Pslist": "Look for: suspicious parent-child, LOLBins, unsigned, injection indicators, abnormal paths.",
    "Windows.Network.Netstat": "Look for: C2 beaconing, unusual ports, connections to rare IPs, non-browser high-port listeners.",
    "Windows.System.Services": "Look for: services in temp dirs, misspelled names, unsigned ServiceDll, unusual start modes.",
    "Windows.Forensics.Prefetch": "Look for: recon tools, lateral movement tools, rarely-run executables with high run counts.",
    "Windows.EventLogs.EvtxHunter": "Look for: logon type 10/3 anomalies, service installs, PowerShell script blocks, clearing.",
    "Windows.Sys.Autoruns": "Look for: recently added entries, entries in temp/user dirs, encoded commands, suspicious DLLs.",
    "Windows.Registry.Finder": "Look for: run keys, image file execution options, hidden services, encoded payloads.",
    "Windows.Search.FileFinder": "Look for: files in unusual locations, recently modified system files, known tool names.",
}


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"`(?:json)?\s*\n?(.*?)\n?\s*`", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        brace = text.find("{")
        bracket = text.rfind("}")
        if brace != -1 and bracket != -1 and bracket > brace:
            try:
                return json.loads(text[brace : bracket + 1])
            except json.JSONDecodeError:
                pass
    return {"raw_response": text[:3000]}


async def triage_dataset(dataset_id: str) -> None:
    logger.info("Starting triage for dataset %s", dataset_id)

    async with async_session() as db:
        ds_result = await db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        dataset = ds_result.scalar_one_or_none()
        if not dataset:
            logger.error("Dataset %s not found", dataset_id)
            return

        artifact_type = getattr(dataset, "artifact_type", None) or "Unknown"
        focus = ARTIFACT_FOCUS.get(artifact_type, "Analyze for any suspicious indicators.")

        count_result = await db.execute(
            select(func.count()).where(DatasetRow.dataset_id == dataset_id)
        )
        total_rows = count_result.scalar() or 0

        batch_size = settings.TRIAGE_BATCH_SIZE
        suspicious_count = 0
        offset = 0

        while offset < total_rows:
            if suspicious_count >= settings.TRIAGE_MAX_SUSPICIOUS_ROWS:
                logger.info("Reached suspicious row cap for dataset %s", dataset_id)
                break

            rows_result = await db.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == dataset_id)
                .order_by(DatasetRow.row_number)
                .offset(offset)
                .limit(batch_size)
            )
            rows = rows_result.scalars().all()
            if not rows:
                break

            batch_data = []
            for r in rows:
                data = r.normalized_data or r.data
                compact = {k: str(v)[:200] for k, v in data.items() if v}
                batch_data.append(compact)

            system_prompt = f"""You are a cybersecurity triage analyst. Analyze this batch of {artifact_type} forensic data.
{focus}

Return JSON with:
- risk_score: 0.0 (benign) to 10.0 (critical threat)
- verdict: "clean", "suspicious", "malicious", or "inconclusive"
- findings: list of key observations
- suspicious_indicators: list of specific IOCs or anomalies
- mitre_techniques: list of MITRE ATT&CK IDs if applicable

Be precise. Only flag genuinely suspicious items. Respond with valid JSON only."""

            prompt = f"Rows {offset+1}-{offset+len(rows)} of {total_rows}:\n{json.dumps(batch_data, default=str)[:6000]}"

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        ROADRUNNER_URL,
                        json={
                            "model": DEFAULT_FAST_MODEL,
                            "prompt": prompt,
                            "system": system_prompt,
                            "stream": False,
                            "options": {"temperature": 0.2, "num_predict": 2048},
                        },
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    llm_text = result.get("response", "")

                parsed = _parse_llm_response(llm_text)
                risk = float(parsed.get("risk_score", 0.0))

                triage = TriageResult(
                    dataset_id=dataset_id,
                    row_start=offset,
                    row_end=offset + len(rows) - 1,
                    risk_score=risk,
                    verdict=parsed.get("verdict", "inconclusive"),
                    findings=parsed.get("findings", []),
                    suspicious_indicators=parsed.get("suspicious_indicators", []),
                    mitre_techniques=parsed.get("mitre_techniques", []),
                    model_used=DEFAULT_FAST_MODEL,
                    node_used="roadrunner",
                )
                db.add(triage)
                await db.commit()

                if risk >= settings.TRIAGE_ESCALATION_THRESHOLD:
                    suspicious_count += len(rows)

                logger.debug(
                    "Triage batch %d-%d: risk=%.1f verdict=%s",
                    offset, offset + len(rows) - 1, risk, triage.verdict,
                )

            except Exception as e:
                logger.error("Triage batch %d failed: %s", offset, e)
                triage = TriageResult(
                    dataset_id=dataset_id,
                    row_start=offset,
                    row_end=offset + len(rows) - 1,
                    risk_score=0.0,
                    verdict="error",
                    findings=[f"Error: {e}"],
                    model_used=DEFAULT_FAST_MODEL,
                    node_used="roadrunner",
                )
                db.add(triage)
                await db.commit()

            offset += batch_size

    logger.info("Triage complete for dataset %s", dataset_id)
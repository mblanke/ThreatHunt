"""Report generator - debate-powered hunt report generation using Wile + Roadrunner."""

from __future__ import annotations

import json
import logging
import time

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session
from app.db.models import (
    Dataset, HostProfile, HuntReport, TriageResult,
)
from app.services.triage import _parse_llm_response

logger = logging.getLogger(__name__)

WILE_URL = f"{settings.wile_url}/api/generate"
ROADRUNNER_URL = f"{settings.roadrunner_url}/api/generate"
HEAVY_MODEL = settings.DEFAULT_HEAVY_MODEL
FAST_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"


async def _llm_call(url: str, model: str, system: str, prompt: str, timeout: float = 300.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 8192},
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


async def _gather_evidence(db, hunt_id: str) -> dict:
    ds_result = await db.execute(select(Dataset).where(Dataset.hunt_id == hunt_id))
    datasets = ds_result.scalars().all()

    dataset_summary = []
    all_triage = []
    for ds in datasets:
        ds_info = {
            "name": ds.name,
            "artifact_type": getattr(ds, "artifact_type", "Unknown"),
            "row_count": ds.row_count or 0,
        }
        dataset_summary.append(ds_info)

        triage_result = await db.execute(
            select(TriageResult)
            .where(TriageResult.dataset_id == ds.id)
            .where(TriageResult.risk_score >= 3.0)
            .order_by(TriageResult.risk_score.desc())
            .limit(15)
        )
        for t in triage_result.scalars().all():
            all_triage.append({
                "dataset": ds.name,
                "artifact_type": ds_info["artifact_type"],
                "rows": f"{t.row_start}-{t.row_end}",
                "risk_score": t.risk_score,
                "verdict": t.verdict,
                "findings": t.findings[:5] if t.findings else [],
                "indicators": t.suspicious_indicators[:5] if t.suspicious_indicators else [],
                "mitre": t.mitre_techniques or [],
            })

    profile_result = await db.execute(
        select(HostProfile)
        .where(HostProfile.hunt_id == hunt_id)
        .order_by(HostProfile.risk_score.desc())
    )
    profiles = profile_result.scalars().all()
    host_summaries = []
    for p in profiles:
        host_summaries.append({
            "hostname": p.hostname,
            "risk_score": p.risk_score,
            "risk_level": p.risk_level,
            "findings": p.suspicious_findings[:5] if p.suspicious_findings else [],
            "mitre": p.mitre_techniques or [],
            "timeline": (p.timeline_summary or "")[:300],
        })

    return {
        "datasets": dataset_summary,
        "triage_findings": all_triage[:30],
        "host_profiles": host_summaries,
        "total_datasets": len(datasets),
        "total_rows": sum(d["row_count"] for d in dataset_summary),
        "high_risk_hosts": len([h for h in host_summaries if h["risk_score"] >= 7.0]),
    }


async def generate_report(hunt_id: str) -> None:
    logger.info("Generating report for hunt %s", hunt_id)
    start = time.monotonic()

    async with async_session() as db:
        report = HuntReport(
            hunt_id=hunt_id,
            status="generating",
            models_used=[HEAVY_MODEL, FAST_MODEL],
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        report_id = report.id

        try:
            evidence = await _gather_evidence(db, hunt_id)
            evidence_text = json.dumps(evidence, indent=1, default=str)[:12000]

            # Phase 1: Wile initial analysis
            logger.info("Report phase 1: Wile initial analysis")
            phase1 = await _llm_call(
                WILE_URL, HEAVY_MODEL,
                system=(
                    "You are a senior threat intelligence analyst writing a hunt report.\n"
                    "Analyze all evidence and produce a structured threat assessment.\n"
                    "Include: executive summary, detailed findings per host, MITRE mapping,\n"
                    "IOC table, risk rankings, and actionable recommendations.\n"
                    "Use markdown formatting. Be thorough and specific."
                ),
                prompt=f"Hunt evidence:\n{evidence_text}\n\nProduce your initial threat assessment.",
            )

            # Phase 2: Roadrunner critical review
            logger.info("Report phase 2: Roadrunner critical review")
            phase2 = await _llm_call(
                ROADRUNNER_URL, FAST_MODEL,
                system=(
                    "You are a critical reviewer of threat hunt reports.\n"
                    "Review the initial assessment and identify:\n"
                    "- Missing correlations or overlooked indicators\n"
                    "- False positive risks or overblown findings\n"
                    "- Additional MITRE techniques that should be mapped\n"
                    "- Gaps in recommendations\n"
                    "Be specific and constructive. Respond in markdown."
                ),
                prompt=f"Evidence:\n{evidence_text[:4000]}\n\nInitial Assessment:\n{phase1[:6000]}\n\nProvide your critical review.",
                timeout=120.0,
            )

            # Phase 3: Wile final synthesis
            logger.info("Report phase 3: Wile final synthesis")
            synthesis_prompt = (
                f"Original evidence:\n{evidence_text[:6000]}\n\n"
                f"Initial assessment:\n{phase1[:5000]}\n\n"
                f"Critical review:\n{phase2[:3000]}\n\n"
                "Produce the FINAL hunt report incorporating the review feedback.\n"
                "Return JSON with these keys:\n"
                "- executive_summary: 2-3 paragraph executive summary\n"
                "- findings: list of {title, severity, description, evidence, mitre_ids}\n"
                "- recommendations: list of {priority, action, rationale}\n"
                "- mitre_mapping: dict of technique_id -> {name, description, evidence}\n"
                "- ioc_table: list of {type, value, context, confidence}\n"
                "- host_risk_summary: list of {hostname, risk_score, risk_level, key_findings}\n"
                "Respond with valid JSON only."
            )
            phase3_text = await _llm_call(
                WILE_URL, HEAVY_MODEL,
                system="You are producing the final, definitive threat hunt report. Incorporate all feedback. Respond with valid JSON only.",
                prompt=synthesis_prompt,
            )

            parsed = _parse_llm_response(phase3_text)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            full_report = f"# Threat Hunt Report\n\n{phase1}\n\n---\n## Review Notes\n{phase2}\n\n---\n## Final Synthesis\n{phase3_text}"

            report.status = "complete"
            report.exec_summary = parsed.get("executive_summary", phase1[:2000])
            report.full_report = full_report
            report.findings = parsed.get("findings", [])
            report.recommendations = parsed.get("recommendations", [])
            report.mitre_mapping = parsed.get("mitre_mapping", {})
            report.ioc_table = parsed.get("ioc_table", [])
            report.host_risk_summary = parsed.get("host_risk_summary", [])
            report.generation_time_ms = elapsed_ms
            await db.commit()

            logger.info("Report %s complete in %dms", report_id, elapsed_ms)

        except Exception as e:
            logger.error("Report generation failed for hunt %s: %s", hunt_id, e)
            report.status = "error"
            report.exec_summary = f"Report generation failed: {e}"
            report.generation_time_ms = int((time.monotonic() - start) * 1000)
            await db.commit()
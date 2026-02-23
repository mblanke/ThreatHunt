"""LLM-powered dataset analysis — replaces manual IOC enrichment.

Loads dataset rows server-side, builds a concise summary, and sends it
to Wile (70B heavy) or Roadrunner (fast) for threat analysis.
Supports both single-dataset and hunt-wide analysis.
"""

import asyncio
import json
import logging
import time
from collections import Counter, defaultdict
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.agents.providers_v2 import OllamaProvider
from app.agents.router import TaskType, task_router
from app.services.sans_rag import sans_rag

logger = logging.getLogger(__name__)


# ── Request / Response models ─────────────────────────────────────────


class AnalysisRequest(BaseModel):
    """Request for LLM-powered analysis of a dataset."""
    dataset_id: Optional[str] = None
    hunt_id: Optional[str] = None
    question: str = Field(
        default="Perform a comprehensive threat analysis of this dataset. "
        "Identify anomalies, suspicious patterns, potential IOCs, and recommend "
        "next steps for the analyst.",
        description="Specific question or general analysis request",
    )
    mode: str = Field(default="deep", description="quick | deep")
    focus: Optional[str] = Field(
        None,
        description="Focus area: threats, anomalies, lateral_movement, exfil, persistence, recon",
    )


class AnalysisResult(BaseModel):
    """LLM analysis result."""
    analysis: str = Field(..., description="Full analysis text (markdown)")
    confidence: float = Field(default=0.0, description="0-1 confidence")
    key_findings: list[str] = Field(default_factory=list)
    iocs_identified: list[dict] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    mitre_techniques: list[str] = Field(default_factory=list)
    risk_score: int = Field(default=0, description="0-100 risk score")
    model_used: str = ""
    node_used: str = ""
    latency_ms: int = 0
    rows_analyzed: int = 0
    dataset_summary: str = ""


# ── Analysis prompts ──────────────────────────────────────────────────

ANALYSIS_SYSTEM = """You are an expert threat hunter and incident response analyst.
You are analyzing CSV log data from forensic tools (Velociraptor, Sysmon, etc.).

Your task: Perform deep threat analysis of the data provided and produce actionable findings.

RESPOND WITH VALID JSON ONLY:
{
  "analysis": "Detailed markdown analysis with headers and bullet points",
  "confidence": 0.85,
  "key_findings": ["Finding 1", "Finding 2"],
  "iocs_identified": [{"type": "ip", "value": "1.2.3.4", "context": "C2 traffic"}],
  "recommended_actions": ["Action 1", "Action 2"],
  "mitre_techniques": ["T1059.001 - PowerShell", "T1071 - Application Layer Protocol"],
  "risk_score": 65
}
"""

FOCUS_PROMPTS = {
    "threats": "Focus on identifying active threats, malware indicators, and attack patterns.",
    "anomalies": "Focus on statistical anomalies, outliers, and unusual behavior patterns.",
    "lateral_movement": "Focus on evidence of lateral movement: PsExec, WMI, RDP, SMB, pass-the-hash.",
    "exfil": "Focus on data exfiltration indicators: large transfers, DNS tunneling, unusual destinations.",
    "persistence": "Focus on persistence mechanisms: scheduled tasks, services, registry, startup items.",
    "recon": "Focus on reconnaissance activity: scanning, enumeration, discovery commands.",
}


# ── Data summarizer ───────────────────────────────────────────────────


def summarize_dataset_rows(
    rows: list[dict],
    columns: list[str] | None = None,
    max_sample: int = 20,
    max_chars: int = 6000,
) -> str:
    """Build a concise text summary of dataset rows for LLM consumption.

    Includes:
    - Column headers and types
    - Statistical summary (unique values, top values per column)
    - Sample rows (first N)
    - Detected patterns of interest
    """
    if not rows:
        return "Empty dataset — no rows to analyze."

    cols = columns or list(rows[0].keys())
    n_rows = len(rows)

    parts: list[str] = []
    parts.append(f"## Dataset Summary: {n_rows} rows, {len(cols)} columns")
    parts.append(f"Columns: {', '.join(cols)}")

    # Per-column stats
    parts.append("\n### Column Statistics:")
    for col in cols[:30]:  # limit to first 30 cols
        values = [str(r.get(col, "")) for r in rows if r.get(col) not in (None, "", "N/A")]
        if not values:
            continue
        unique = len(set(values))
        counter = Counter(values)
        top3 = counter.most_common(3)
        top_str = ", ".join(f"{v} ({c}x)" for v, c in top3)
        parts.append(f"- **{col}**: {len(values)} non-null, {unique} unique. Top: {top_str}")

    # Sample rows
    sample = rows[:max_sample]
    parts.append(f"\n### Sample Rows (first {len(sample)}):")
    for i, row in enumerate(sample):
        row_str = " | ".join(f"{k}={v}" for k, v in row.items() if v not in (None, "", "N/A"))
        parts.append(f"{i+1}. {row_str}")

    # Detect interesting patterns
    patterns: list[str] = []
    all_cmds = [str(r.get("command_line", "")).lower() for r in rows if r.get("command_line")]
    sus_cmds = [c for c in all_cmds if any(
        k in c for k in ["powershell -enc", "certutil", "bitsadmin", "mshta",
                          "regsvr32", "invoke-", "mimikatz", "psexec"]
    )]
    if sus_cmds:
        patterns.append(f"⚠️ {len(sus_cmds)} suspicious command lines detected")

    all_ips = [str(r.get("dst_ip", "")) for r in rows if r.get("dst_ip")]
    ext_ips = [ip for ip in all_ips if ip and not ip.startswith(("10.", "192.168.", "172.", "127."))]
    if ext_ips:
        unique_ext = len(set(ext_ips))
        patterns.append(f"🌐 {unique_ext} unique external destination IPs")

    if patterns:
        parts.append("\n### Detected Patterns:")
        for p in patterns:
            parts.append(f"- {p}")

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


# ── LLM analysis engine ──────────────────────────────────────────────


async def run_llm_analysis(
    rows: list[dict],
    request: AnalysisRequest,
    dataset_name: str = "unknown",
) -> AnalysisResult:
    """Run LLM analysis on dataset rows."""
    start = time.monotonic()

    # Build summary
    summary = summarize_dataset_rows(rows)

    # Route to appropriate model
    task_type = TaskType.DEEP_ANALYSIS if request.mode == "deep" else TaskType.QUICK_CHAT
    decision = task_router.route(task_type)

    # Build prompt
    focus_text = FOCUS_PROMPTS.get(request.focus or "", "")
    prompt = f"""Analyze the following forensic dataset from '{dataset_name}'.

{focus_text}

Analyst question: {request.question}

{summary}
"""

    # Enrich with SANS RAG
    try:
        rag_context = await sans_rag.enrich_prompt(
            request.question,
            investigation_context=f"Analyzing {len(rows)} rows from {dataset_name}",
        )
        if rag_context:
            prompt = f"{prompt}\n\n{rag_context}"
    except Exception as e:
        logger.warning(f"SANS RAG enrichment failed: {e}")

    # Call LLM
    provider = task_router.get_provider(decision)
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        raw = await asyncio.wait_for(
            provider.generate(
                prompt=prompt,
                system=ANALYSIS_SYSTEM,
                max_tokens=settings.AGENT_MAX_TOKENS * 2,  # longer for analysis
                temperature=0.3,
            ),
            timeout=300,  # 5 min hard limit
        )
    except asyncio.TimeoutError:
        logger.error("LLM analysis timed out after 300s")
        return AnalysisResult(
            analysis="Analysis timed out after 5 minutes. Try a smaller dataset or 'quick' mode.",
            model_used=decision.model,
            node_used=decision.node,
            latency_ms=int((time.monotonic() - start) * 1000),
            rows_analyzed=len(rows),
            dataset_summary=summary,
        )
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return AnalysisResult(
            analysis=f"Analysis failed: {str(e)}",
            model_used=decision.model,
            node_used=decision.node,
            latency_ms=int((time.monotonic() - start) * 1000),
            rows_analyzed=len(rows),
            dataset_summary=summary,
        )

    elapsed = int((time.monotonic() - start) * 1000)

    # Parse JSON response
    result = _parse_analysis(raw)
    result.model_used = decision.model
    result.node_used = decision.node
    result.latency_ms = elapsed
    result.rows_analyzed = len(rows)
    result.dataset_summary = summary

    return result


def _parse_analysis(raw) -> AnalysisResult:
    """Try to parse LLM output as JSON, fall back to plain text.

    raw may be:
      - A dict from OllamaProvider.generate() with key "response" containing LLM text
      - A plain string from other providers
    """
    # Ollama provider returns {"response": "<llm text>", "model": ..., ...}
    if isinstance(raw, dict):
        text = raw.get("response") or raw.get("analysis") or str(raw)
        logger.info(f"_parse_analysis: extracted text from dict, len={len(text)}, first 200 chars: {text[:200]}")
    else:
        text = str(raw)
        logger.info(f"_parse_analysis: raw is str, len={len(text)}, first 200 chars: {text[:200]}")

    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try direct JSON parse first
    for candidate in _extract_json_candidates(text):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                logger.info(f"_parse_analysis: parsed JSON OK, keys={list(data.keys())}")
                return AnalysisResult(
                    analysis=data.get("analysis", text),
                    confidence=float(data.get("confidence", 0.5)),
                    key_findings=data.get("key_findings", []),
                    iocs_identified=data.get("iocs_identified", []),
                    recommended_actions=data.get("recommended_actions", []),
                    mitre_techniques=data.get("mitre_techniques", []),
                    risk_score=int(data.get("risk_score", 0)),
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"_parse_analysis: JSON parse failed: {e}, candidate len={len(candidate)}, first 100: {candidate[:100]}")
            continue

    # Fallback: plain text
    logger.warning(f"_parse_analysis: all JSON parse attempts failed, falling back to plain text")
    return AnalysisResult(
        analysis=text,
        confidence=0.5,
    )


def _extract_json_candidates(text: str):
    """Yield JSON candidate strings from text, trying progressively more aggressive extraction."""
    import re

    # 1. The whole text as-is
    yield text

    # 2. Find outermost { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        block = text[start:end + 1]
        yield block

        # 3. Try to fix common LLM JSON issues:
        # - trailing commas before ] or }
        fixed = re.sub(r',\s*([}\]])', r'\1', block)
        if fixed != block:
            yield fixed

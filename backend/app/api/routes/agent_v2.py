"""API routes for analyst-assist agent  v2.

Supports quick, deep, and debate modes with streaming.
Conversations are persisted to the database.
"""

import json
import logging
import re
import time
from collections import Counter
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import Conversation, Message, Dataset, KeywordTheme
from app.agents.core_v2 import ThreatHuntAgent, AgentContext, AgentResponse, Perspective
from app.agents.providers_v2 import check_all_nodes
from app.agents.registry import registry
from app.services.sans_rag import sans_rag
from app.services.scanner import KeywordScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Global agent instance
_agent: ThreatHuntAgent | None = None


def get_agent() -> ThreatHuntAgent:
    global _agent
    if _agent is None:
        _agent = ThreatHuntAgent()
    return _agent


#  Request / Response models 


class AssistRequest(BaseModel):
    query: str = Field(..., max_length=4000, description="Analyst question")
    dataset_name: str | None = None
    artifact_type: str | None = None
    host_identifier: str | None = None
    data_summary: str | None = None
    conversation_history: list[dict] | None = None
    active_hypotheses: list[str] | None = None
    annotations_summary: str | None = None
    enrichment_summary: str | None = None
    mode: str = Field(default="quick", description="quick | deep | debate")
    model_override: str | None = None
    conversation_id: str | None = Field(None, description="Persist messages to this conversation")
    hunt_id: str | None = None
    execution_preference: str = Field(default="auto", description="auto | force | off")
    learning_mode: bool = False


class AssistResponseModel(BaseModel):
    guidance: str
    confidence: float
    suggested_pivots: list[str]
    suggested_filters: list[str]
    caveats: str | None = None
    reasoning: str | None = None
    sans_references: list[str] = []
    model_used: str = ""
    node_used: str = ""
    latency_ms: int = 0
    perspectives: list[dict] | None = None
    execution: dict | None = None
    conversation_id: str | None = None


POLICY_THEME_NAMES = {"Adult Content", "Gambling", "Downloads / Piracy"}
POLICY_QUERY_TERMS = {
    "policy", "violating", "violation", "browser history", "web history",
    "domain", "domains", "adult", "gambling", "piracy", "aup",
}
WEB_DATASET_HINTS = {
    "web", "history", "browser", "url", "visited_url", "domain", "title",
}


def _is_policy_domain_query(query: str) -> bool:
    q = (query or "").lower()
    if not q:
        return False
    score = sum(1 for t in POLICY_QUERY_TERMS if t in q)
    return score >= 2 and ("domain" in q or "history" in q or "policy" in q)

def _should_execute_policy_scan(request: AssistRequest) -> bool:
    pref = (request.execution_preference or "auto").strip().lower()
    if pref == "off":
        return False
    if pref == "force":
        return True
    return _is_policy_domain_query(request.query)


def _extract_domain(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    try:
        parsed = urlparse(text)
        if parsed.netloc:
            return parsed.netloc.lower()
    except Exception:
        pass

    m = re.search(r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}", text)
    return m.group(0).lower() if m else None


def _dataset_score(ds: Dataset) -> int:
    score = 0
    name = (ds.name or "").lower()
    cols_l = {c.lower() for c in (ds.column_schema or {}).keys()}
    norm_vals_l = {str(v).lower() for v in (ds.normalized_columns or {}).values()}

    for h in WEB_DATASET_HINTS:
        if h in name:
            score += 2
        if h in cols_l:
            score += 3
        if h in norm_vals_l:
            score += 3

    if "visited_url" in cols_l or "url" in cols_l:
        score += 8
    if "user" in cols_l or "username" in cols_l:
        score += 2
    if "clientid" in cols_l or "fqdn" in cols_l:
        score += 2
    if (ds.row_count or 0) > 0:
        score += 1

    return score


async def _run_policy_domain_execution(request: AssistRequest, db: AsyncSession) -> dict:
    scanner = KeywordScanner(db)

    theme_result = await db.execute(
        select(KeywordTheme).where(
            KeywordTheme.enabled == True,  # noqa: E712
            KeywordTheme.name.in_(list(POLICY_THEME_NAMES)),
        )
    )
    themes = list(theme_result.scalars().all())
    theme_ids = [t.id for t in themes]
    theme_names = [t.name for t in themes] or sorted(POLICY_THEME_NAMES)

    ds_query = select(Dataset).where(Dataset.processing_status.in_(["completed", "ready", "processing"]))
    if request.hunt_id:
        ds_query = ds_query.where(Dataset.hunt_id == request.hunt_id)
    ds_result = await db.execute(ds_query)
    candidates = list(ds_result.scalars().all())

    if request.dataset_name:
        needle = request.dataset_name.lower().strip()
        candidates = [d for d in candidates if needle in (d.name or "").lower()]

    scored = sorted(
        ((d, _dataset_score(d)) for d in candidates),
        key=lambda x: x[1],
        reverse=True,
    )
    selected = [d for d, s in scored if s > 0][:8]
    dataset_ids = [d.id for d in selected]

    if not dataset_ids:
        return {
            "mode": "policy_scan",
            "themes": theme_names,
            "datasets_scanned": 0,
            "dataset_names": [],
            "total_hits": 0,
            "policy_hits": 0,
            "top_user_hosts": [],
            "top_domains": [],
            "sample_hits": [],
            "note": "No suitable browser/web-history datasets found in current scope.",
        }

    result = await scanner.scan(
        dataset_ids=dataset_ids,
        theme_ids=theme_ids or None,
        scan_hunts=False,
        scan_annotations=False,
        scan_messages=False,
    )
    hits = result.get("hits", [])

    user_host_counter = Counter()
    domain_counter = Counter()

    for h in hits:
        user = h.get("username") or "(unknown-user)"
        host = h.get("hostname") or "(unknown-host)"
        user_host_counter[f"{user}|{host}"] += 1

        dom = _extract_domain(h.get("matched_value"))
        if dom:
            domain_counter[dom] += 1

    top_user_hosts = [
        {"user_host": k, "count": v}
        for k, v in user_host_counter.most_common(10)
    ]
    top_domains = [
        {"domain": k, "count": v}
        for k, v in domain_counter.most_common(10)
    ]

    return {
        "mode": "policy_scan",
        "themes": theme_names,
        "datasets_scanned": len(dataset_ids),
        "dataset_names": [d.name for d in selected],
        "total_hits": int(result.get("total_hits", 0)),
        "policy_hits": int(result.get("total_hits", 0)),
        "rows_scanned": int(result.get("rows_scanned", 0)),
        "top_user_hosts": top_user_hosts,
        "top_domains": top_domains,
        "sample_hits": hits[:20],
    }


#  Routes 


@router.post(
    "/assist",
    response_model=AssistResponseModel,
    summary="Get analyst-assist guidance",
    description="Request guidance with auto-routed model selection. "
    "Supports quick (fast), deep (70B), and debate (multi-model) modes.",
)
async def agent_assist(
    request: AssistRequest,
    db: AsyncSession = Depends(get_db),
) -> AssistResponseModel:
    try:
        # Deterministic execution mode for policy-domain investigations.
        if _should_execute_policy_scan(request):
            t0 = time.monotonic()
            exec_payload = await _run_policy_domain_execution(request, db)
            latency_ms = int((time.monotonic() - t0) * 1000)

            policy_hits = exec_payload.get("policy_hits", 0)
            datasets_scanned = exec_payload.get("datasets_scanned", 0)

            if policy_hits > 0:
                guidance = (
                    f"Policy-violation scan complete: {policy_hits} hits across "
                    f"{datasets_scanned} dataset(s). Top user/host pairs and domains are included "
                    f"in execution results for triage."
                )
                confidence = 0.95
                caveats = "Keyword-based matching can include false positives; validate with full URL context."
            else:
                guidance = (
                    f"No policy-violation hits found in current scope "
                    f"({datasets_scanned} dataset(s) scanned)."
                )
                confidence = 0.9
                caveats = exec_payload.get("note") or "Try expanding scope to additional hunts/datasets."

            response = AssistResponseModel(
                guidance=guidance,
                confidence=confidence,
                suggested_pivots=["username", "hostname", "domain", "dataset_name"],
                suggested_filters=[
                    "theme_name in ['Adult Content','Gambling','Downloads / Piracy']",
                    "username != null",
                    "hostname != null",
                ],
                caveats=caveats,
                reasoning=(
                    "Intent matched policy-domain investigation; executed local keyword scan pipeline."
                    if _is_policy_domain_query(request.query)
                    else "Execution mode was forced by user preference; ran policy-domain scan pipeline."
                ),
                sans_references=["SANS FOR508", "SANS SEC504"],
                model_used="execution:keyword_scanner",
                node_used="local",
                latency_ms=latency_ms,
                execution=exec_payload,
            )

            conv_id = request.conversation_id
            if conv_id or request.hunt_id:
                conv_id = await _persist_conversation(
                    db,
                    conv_id,
                    request,
                    AgentResponse(
                        guidance=response.guidance,
                        confidence=response.confidence,
                        suggested_pivots=response.suggested_pivots,
                        suggested_filters=response.suggested_filters,
                        caveats=response.caveats,
                        reasoning=response.reasoning,
                        sans_references=response.sans_references,
                        model_used=response.model_used,
                        node_used=response.node_used,
                        latency_ms=response.latency_ms,
                    ),
                )
                response.conversation_id = conv_id

            return response

        agent = get_agent()
        context = AgentContext(
            query=request.query,
            dataset_name=request.dataset_name,
            artifact_type=request.artifact_type,
            host_identifier=request.host_identifier,
            data_summary=request.data_summary,
            conversation_history=request.conversation_history or [],
            active_hypotheses=request.active_hypotheses or [],
            annotations_summary=request.annotations_summary,
            enrichment_summary=request.enrichment_summary,
            mode=request.mode,
            model_override=request.model_override,
            learning_mode=request.learning_mode,
        )

        response = await agent.assist(context)

        # Persist conversation
        conv_id = request.conversation_id
        if conv_id or request.hunt_id:
            conv_id = await _persist_conversation(
                db, conv_id, request, response
            )

        return AssistResponseModel(
            guidance=response.guidance,
            confidence=response.confidence,
            suggested_pivots=response.suggested_pivots,
            suggested_filters=response.suggested_filters,
            caveats=response.caveats,
            reasoning=response.reasoning,
            sans_references=response.sans_references,
            model_used=response.model_used,
            node_used=response.node_used,
            latency_ms=response.latency_ms,
            perspectives=[
                {
                    "role": p.role,
                    "content": p.content,
                    "model_used": p.model_used,
                    "node_used": p.node_used,
                    "latency_ms": p.latency_ms,
                }
                for p in response.perspectives
            ] if response.perspectives else None,
            execution=None,
            conversation_id=conv_id,
        )

    except Exception as e:
        logger.exception(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post(
    "/assist/stream",
    summary="Stream agent response",
    description="Stream tokens via SSE for real-time display.",
)
async def agent_assist_stream(request: AssistRequest):
    agent = get_agent()
    context = AgentContext(
        query=request.query,
        dataset_name=request.dataset_name,
        artifact_type=request.artifact_type,
        host_identifier=request.host_identifier,
        data_summary=request.data_summary,
        conversation_history=request.conversation_history or [],
        mode="quick",  # streaming only supports quick mode
    )

    async def _stream():
        async for token in agent.assist_stream(context):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/health",
    summary="Check agent and node health",
    description="Returns availability of all LLM nodes and the cluster.",
)
async def agent_health() -> dict:
    nodes = await check_all_nodes()
    rag_health = await sans_rag.health_check()
    return {
        "status": "healthy",
        "nodes": nodes,
        "rag": rag_health,
        "default_models": {
            "fast": settings.DEFAULT_FAST_MODEL,
            "heavy": settings.DEFAULT_HEAVY_MODEL,
            "code": settings.DEFAULT_CODE_MODEL,
            "vision": settings.DEFAULT_VISION_MODEL,
            "embedding": settings.DEFAULT_EMBEDDING_MODEL,
        },
        "config": {
            "max_tokens": settings.AGENT_MAX_TOKENS,
            "temperature": settings.AGENT_TEMPERATURE,
        },
    }


@router.get(
    "/models",
    summary="List all available models",
    description="Returns the full model registry with capabilities and node assignments.",
)
async def list_models():
    return {
        "models": registry.to_dict(),
        "total": len(registry.models),
    }


#  Conversation persistence 


async def _persist_conversation(
    db: AsyncSession,
    conversation_id: str | None,
    request: AssistRequest,
    response: AgentResponse,
) -> str:
    """Save user message and agent response to the database."""
    if conversation_id:
        # Find existing conversation
        from sqlalchemy import select
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            conv = Conversation(id=conversation_id, hunt_id=request.hunt_id)
            db.add(conv)
    else:
        conv = Conversation(
            title=request.query[:100],
            hunt_id=request.hunt_id,
        )
        db.add(conv)
        await db.flush()

    # User message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=request.query,
    )
    db.add(user_msg)

    # Agent message
    agent_msg = Message(
        conversation_id=conv.id,
        role="agent",
        content=response.guidance,
        model_used=response.model_used,
        node_used=response.node_used,
        latency_ms=response.latency_ms,
        response_meta={
            "confidence": response.confidence,
            "pivots": response.suggested_pivots,
            "filters": response.suggested_filters,
            "sans_refs": response.sans_references,
        },
    )
    db.add(agent_msg)
    await db.flush()

    return conv.id


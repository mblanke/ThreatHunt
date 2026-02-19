"""API routes for analyst-assist agent — v2.

Supports quick, deep, and debate modes with streaming.
Conversations are persisted to the database.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import Conversation, Message
from app.agents.core_v2 import ThreatHuntAgent, AgentContext, AgentResponse, Perspective
from app.agents.providers_v2 import check_all_nodes
from app.agents.registry import registry
from app.services.sans_rag import sans_rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Global agent instance
_agent: ThreatHuntAgent | None = None


def get_agent() -> ThreatHuntAgent:
    global _agent
    if _agent is None:
        _agent = ThreatHuntAgent()
    return _agent


# ── Request / Response models ─────────────────────────────────────────


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
    conversation_id: str | None = None


# ── Routes ────────────────────────────────────────────────────────────


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


# ── Conversation persistence ──────────────────────────────────────────


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

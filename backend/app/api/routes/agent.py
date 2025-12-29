"""API routes for analyst-assist agent."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.core import ThreatHuntAgent, AgentContext, AgentResponse
from app.agents.config import AgentConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Global agent instance (lazy-loaded)
_agent: ThreatHuntAgent | None = None


def get_agent() -> ThreatHuntAgent:
    """Get or create the agent instance."""
    global _agent
    if _agent is None:
        if not AgentConfig.is_agent_enabled():
            raise HTTPException(
                status_code=503,
                detail="Analyst-assist agent is not configured. "
                "Please configure an LLM provider.",
            )
        _agent = ThreatHuntAgent()
    return _agent


class AssistRequest(BaseModel):
    """Request for agent assistance."""

    query: str = Field(
        ..., description="Analyst question or request for guidance"
    )
    dataset_name: str | None = Field(
        None, description="Name of CSV dataset being analyzed"
    )
    artifact_type: str | None = Field(
        None, description="Type of artifact (e.g., FileList, ProcessList, NetworkConnections)"
    )
    host_identifier: str | None = Field(
        None, description="Host name, IP address, or identifier"
    )
    data_summary: str | None = Field(
        None, description="Brief summary or context about the uploaded data"
    )
    conversation_history: list[dict] | None = Field(
        None, description="Previous messages for context"
    )


class AssistResponse(BaseModel):
    """Response with agent guidance."""

    guidance: str
    confidence: float
    suggested_pivots: list[str]
    suggested_filters: list[str]
    caveats: str | None = None
    reasoning: str | None = None


@router.post(
    "/assist",
    response_model=AssistResponse,
    summary="Get analyst-assist guidance",
    description="Request guidance on CSV artifact data, analytical pivots, and hypotheses. "
    "Agent provides advisory guidance only - no execution.",
)
async def agent_assist(request: AssistRequest) -> AssistResponse:
    """Provide analyst-assist guidance on artifact data.

    The agent will:
    - Explain and interpret the provided data context
    - Suggest analytical pivots the analyst might explore
    - Suggest data filters or queries that might be useful
    - Highlight assumptions, limitations, and caveats

    The agent will NOT:
    - Execute any tools or actions
    - Escalate findings to alerts
    - Modify any data or schema
    - Make autonomous decisions

    Args:
        request: Assistance request with query and context

    Returns:
        Guidance response with suggestions and reasoning

    Raises:
        HTTPException: If agent is not configured (503) or request fails
    """
    try:
        agent = get_agent()

        # Build context
        context = AgentContext(
            query=request.query,
            dataset_name=request.dataset_name,
            artifact_type=request.artifact_type,
            host_identifier=request.host_identifier,
            data_summary=request.data_summary,
            conversation_history=request.conversation_history or [],
        )

        # Get guidance
        response = await agent.assist(context)

        logger.info(
            f"Agent assisted analyst with query: {request.query[:50]}... "
            f"(host: {request.host_identifier}, artifact: {request.artifact_type})"
        )

        return AssistResponse(
            guidance=response.guidance,
            confidence=response.confidence,
            suggested_pivots=response.suggested_pivots,
            suggested_filters=response.suggested_filters,
            caveats=response.caveats,
            reasoning=response.reasoning,
        )

    except RuntimeError as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Agent unavailable: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error in agent_assist: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error generating guidance. Please try again.",
        )


@router.get(
    "/health",
    summary="Check agent health",
    description="Check if agent is configured and ready to assist.",
)
async def agent_health() -> dict:
    """Check agent availability and configuration.

    Returns:
        Health status with configuration details
    """
    try:
        agent = get_agent()
        provider_type = agent.provider.__class__.__name__ if agent.provider else "None"
        return {
            "status": "healthy",
            "provider": provider_type,
            "max_tokens": AgentConfig.MAX_RESPONSE_TOKENS,
            "reasoning_enabled": AgentConfig.ENABLE_REASONING,
        }
    except HTTPException:
        return {
            "status": "unavailable",
            "reason": "No LLM provider configured",
            "configured_providers": {
                "local": bool(AgentConfig.LOCAL_MODEL_PATH),
                "networked": bool(AgentConfig.NETWORKED_ENDPOINT),
                "online": bool(AgentConfig.ONLINE_API_KEY),
            },
        }

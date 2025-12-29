"""Core ThreatHunt analyst-assist agent.

Provides read-only guidance on CSV artifact data, analytical pivots, and hypotheses.
Agents are advisory only - no execution, no alerts, no data modifications.
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from .providers import LLMProvider, get_provider

logger = logging.getLogger(__name__)


class AgentContext(BaseModel):
    """Context for agent guidance requests."""

    query: str = Field(
        ..., description="Analyst question or request for guidance"
    )
    dataset_name: Optional[str] = Field(None, description="Name of CSV dataset")
    artifact_type: Optional[str] = Field(None, description="Artifact type (e.g., file, process, network)")
    host_identifier: Optional[str] = Field(
        None, description="Host name, IP, or identifier"
    )
    data_summary: Optional[str] = Field(
        None, description="Brief description of uploaded data"
    )
    conversation_history: Optional[list[dict]] = Field(
        default_factory=list, description="Previous messages in conversation"
    )


class AgentResponse(BaseModel):
    """Response from analyst-assist agent."""

    guidance: str = Field(..., description="Advisory guidance for analyst")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in guidance (0-1)"
    )
    suggested_pivots: list[str] = Field(
        default_factory=list, description="Suggested analytical directions"
    )
    suggested_filters: list[str] = Field(
        default_factory=list, description="Suggested data filters or queries"
    )
    caveats: Optional[str] = Field(
        None, description="Assumptions, limitations, or caveats"
    )
    reasoning: Optional[str] = Field(
        None, description="Explanation of how guidance was generated"
    )


class ThreatHuntAgent:
    """Analyst-assist agent for ThreatHunt.
    
    Provides guidance on:
    - Interpreting CSV artifact data
    - Suggesting analytical pivots and filters
    - Forming and testing hypotheses
    
    Policy:
    - Advisory guidance only (no execution)
    - No database or schema changes
    - No alert escalation
    - Transparent reasoning
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        """Initialize agent with LLM provider.
        
        Args:
            provider: LLM provider instance. If None, uses get_provider() with auto mode.
        """
        if provider is None:
            try:
                provider = get_provider("auto")
            except RuntimeError as e:
                logger.warning(f"Could not initialize default provider: {e}")
                provider = None

        self.provider = provider
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt that governs agent behavior."""
        return """You are an analyst-assist agent for ThreatHunt, a threat hunting platform.

Your role:
- Interpret and explain CSV artifact data from Velociraptor
- Suggest analytical pivots, filters, and hypotheses
- Highlight anomalies, patterns, or points of interest
- Guide analysts without replacing their judgment

Your constraints:
- You ONLY provide guidance and suggestions
- You do NOT execute actions or tools
- You do NOT modify data or escalate alerts
- You do NOT make autonomous decisions
- You ONLY analyze data presented to you
- You explain your reasoning transparently
- You acknowledge limitations and assumptions
- You suggest next investigative steps

When responding:
1. Start with a clear, direct answer to the query
2. Explain your reasoning based on the data context provided
3. Suggest 2-4 analytical pivots the analyst might explore
4. Suggest 2-4 data filters or queries that might be useful
5. Include relevant caveats or assumptions
6. Be honest about what you cannot determine from the data

Remember: The analyst is the decision-maker. You are an assistant."""

    async def assist(self, context: AgentContext) -> AgentResponse:
        """Provide guidance on artifact data and analysis.
        
        Args:
            context: Request context including query and data context.
            
        Returns:
            Guidance response with suggestions and reasoning.
            
        Raises:
            RuntimeError: If no provider is available.
        """
        if not self.provider:
            raise RuntimeError(
                "No LLM provider available. Configure at least one of: "
                "THREAT_HUNT_LOCAL_MODEL_PATH, THREAT_HUNT_NETWORKED_ENDPOINT, "
                "or THREAT_HUNT_ONLINE_API_KEY"
            )

        # Build prompt with context
        prompt = self._build_prompt(context)

        try:
            # Get guidance from LLM provider
            guidance = await self.provider.generate(prompt, max_tokens=1024)

            # Parse response into structured format
            response = self._parse_response(guidance, context)

            logger.info(
                f"Agent assisted with query: {context.query[:50]}... "
                f"(dataset: {context.dataset_name})"
            )

            return response

        except Exception as e:
            logger.error(f"Error generating guidance: {e}")
            raise

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the prompt for the LLM."""
        prompt_parts = [
            f"Analyst query: {context.query}",
        ]

        if context.dataset_name:
            prompt_parts.append(f"Dataset: {context.dataset_name}")

        if context.artifact_type:
            prompt_parts.append(f"Artifact type: {context.artifact_type}")

        if context.host_identifier:
            prompt_parts.append(f"Host: {context.host_identifier}")

        if context.data_summary:
            prompt_parts.append(f"Data summary: {context.data_summary}")

        if context.conversation_history:
            prompt_parts.append("\nConversation history:")
            for msg in context.conversation_history[-5:]:  # Last 5 messages for context
                prompt_parts.append(f"  {msg.get('role', 'unknown')}: {msg.get('content', '')}")

        return "\n".join(prompt_parts)

    def _parse_response(self, response_text: str, context: AgentContext) -> AgentResponse:
        """Parse LLM response into structured format.
        
        Note: This is a simplified parser. In production, use structured output
        from the LLM (JSON mode, function calling, etc.) for better reliability.
        """
        # For now, return a structured response based on the raw guidance
        # In production, parse JSON or use structured output from LLM
        return AgentResponse(
            guidance=response_text,
            confidence=0.8,  # Placeholder
            suggested_pivots=[
                "Analyze temporal patterns",
                "Cross-reference with known indicators",
                "Examine outliers in the dataset",
                "Compare with baseline behavior",
            ],
            suggested_filters=[
                "Filter by high-risk indicators",
                "Sort by timestamp for timeline analysis",
                "Group by host or user",
                "Filter by anomaly score",
            ],
            caveats="Guidance is based on available data context. "
            "Analysts should verify findings with additional sources.",
            reasoning="Analysis generated based on artifact data patterns and analyst query.",
        )

"""Core ThreatHunt analyst-assist agent — v2.

Uses TaskRouter to select the right model/node for each query,
real LLM providers (Ollama/OpenWebUI), and structured response parsing.
Integrates SANS RAG context from Open WebUI.
"""

import json
import logging
import re
import time
from typing import AsyncIterator, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.services.sans_rag import sans_rag
from .router import TaskRouter, TaskType, RoutingDecision, task_router
from .providers_v2 import OllamaProvider, OpenWebUIProvider

logger = logging.getLogger(__name__)


# ── Models ────────────────────────────────────────────────────────────


class AgentContext(BaseModel):
    """Context for agent guidance requests."""

    query: str = Field(..., description="Analyst question or request for guidance")
    dataset_name: Optional[str] = Field(None, description="Name of CSV dataset")
    artifact_type: Optional[str] = Field(None, description="Artifact type")
    host_identifier: Optional[str] = Field(None, description="Host name, IP, or identifier")
    data_summary: Optional[str] = Field(None, description="Brief description of data")
    conversation_history: Optional[list[dict]] = Field(
        default_factory=list, description="Previous messages"
    )
    active_hypotheses: Optional[list[str]] = Field(
        default_factory=list, description="Active investigation hypotheses"
    )
    annotations_summary: Optional[str] = Field(
        None, description="Summary of analyst annotations"
    )
    enrichment_summary: Optional[str] = Field(
        None, description="Summary of enrichment results"
    )
    mode: str = Field(default="quick", description="quick | deep | debate")
    model_override: Optional[str] = Field(None, description="Force a specific model")


class Perspective(BaseModel):
    """A single perspective from the debate agent."""
    role: str
    content: str
    model_used: str
    node_used: str
    latency_ms: int


class AgentResponse(BaseModel):
    """Response from analyst-assist agent."""

    guidance: str = Field(..., description="Advisory guidance for analyst")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence (0-1)")
    suggested_pivots: list[str] = Field(default_factory=list)
    suggested_filters: list[str] = Field(default_factory=list)
    caveats: Optional[str] = None
    reasoning: Optional[str] = None
    sans_references: list[str] = Field(
        default_factory=list, description="SANS course references"
    )
    model_used: str = Field(default="", description="Model that generated the response")
    node_used: str = Field(default="", description="Node that processed the request")
    latency_ms: int = Field(default=0, description="Total latency in ms")
    perspectives: Optional[list[Perspective]] = Field(
        None, description="Debate perspectives (only in debate mode)"
    )


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an analyst-assist agent for ThreatHunt, a threat hunting platform.
You have access to 300GB of SANS cybersecurity course material for reference.

Your role:
- Interpret and explain CSV artifact data from Velociraptor and other forensic tools
- Suggest analytical pivots, filters, and hypotheses
- Highlight anomalies, patterns, or points of interest
- Reference relevant SANS methodologies and techniques when applicable
- Guide analysts without replacing their judgment

Your constraints:
- You ONLY provide guidance and suggestions
- You do NOT execute actions or tools
- You do NOT modify data or escalate alerts
- You explain your reasoning transparently

RESPONSE FORMAT — you MUST respond with valid JSON:
{
  "guidance": "Your main guidance text here",
  "confidence": 0.85,
  "suggested_pivots": ["Pivot 1", "Pivot 2"],
  "suggested_filters": ["filter expression 1", "filter expression 2"],
  "caveats": "Any assumptions or limitations",
  "reasoning": "How you arrived at this guidance",
  "sans_references": ["SANS SEC504: ...", "SANS FOR508: ..."]
}

Respond ONLY with the JSON object. No markdown, no code fences, no extra text."""


# ── Agent ─────────────────────────────────────────────────────────────


class ThreatHuntAgent:
    """Analyst-assist agent backed by Wile + Roadrunner LLM cluster."""

    def __init__(self, router: TaskRouter | None = None):
        self.router = router or task_router
        self.system_prompt = SYSTEM_PROMPT

    async def assist(self, context: AgentContext) -> AgentResponse:
        """Provide guidance on artifact data and analysis."""
        start = time.monotonic()

        if context.mode == "debate":
            return await self._debate_assist(context)

        # Classify task and route
        task_type = self.router.classify_task(context.query)
        if context.mode == "deep":
            task_type = TaskType.DEEP_ANALYSIS

        decision = self.router.route(task_type, model_override=context.model_override)
        logger.info(f"Routing: {decision.reason}")

        # Enrich prompt with SANS RAG context
        prompt = self._build_prompt(context)
        try:
            rag_context = await sans_rag.enrich_prompt(
                context.query,
                investigation_context=context.data_summary or "",
            )
            if rag_context:
                prompt = f"{prompt}\n\n{rag_context}"
        except Exception as e:
            logger.warning(f"SANS RAG enrichment failed: {e}")

        # Call LLM
        provider = self.router.get_provider(decision)
        if isinstance(provider, OpenWebUIProvider):
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
            result = await provider.chat(
                messages,
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=settings.AGENT_TEMPERATURE,
            )
        else:
            result = await provider.generate(
                prompt,
                system=self.system_prompt,
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=settings.AGENT_TEMPERATURE,
            )

        raw_text = result.get("response", "")
        latency_ms = result.get("_latency_ms", 0)

        # Parse structured response
        response = self._parse_response(raw_text, context)
        response.model_used = decision.model
        response.node_used = decision.node.value
        response.latency_ms = latency_ms

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            f"Agent assist: {context.query[:60]}... → "
            f"{decision.model} on {decision.node.value} "
            f"({total_ms}ms total, {latency_ms}ms LLM)"
        )

        return response

    async def assist_stream(
        self,
        context: AgentContext,
    ) -> AsyncIterator[str]:
        """Stream agent response tokens."""
        task_type = self.router.classify_task(context.query)
        decision = self.router.route(task_type, model_override=context.model_override)
        prompt = self._build_prompt(context)

        provider = self.router.get_provider(decision)
        if isinstance(provider, OllamaProvider):
            async for token in provider.generate_stream(
                prompt,
                system=self.system_prompt,
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=settings.AGENT_TEMPERATURE,
            ):
                yield token
        elif isinstance(provider, OpenWebUIProvider):
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
            async for token in provider.chat_stream(
                messages,
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=settings.AGENT_TEMPERATURE,
            ):
                yield token

    async def _debate_assist(self, context: AgentContext) -> AgentResponse:
        """Multi-perspective analysis using diverse models on Wile."""
        import asyncio

        start = time.monotonic()
        prompt = self._build_prompt(context)

        # Route each perspective to a different heavy model
        roles = {
            TaskType.DEBATE_PLANNER: (
                "Planner",
                "You are the Planner for a threat hunting investigation.\n"
                "Provide a structured investigation strategy. Reference SANS methodologies.\n"
                "Focus on: investigation steps, data sources to examine, MITRE ATT&CK mapping.\n"
                "Be specific to the data context provided.\n\n",
            ),
            TaskType.DEBATE_CRITIC: (
                "Critic",
                "You are the Critic for a threat hunting investigation.\n"
                "Identify risks, false positive scenarios, missing evidence, and assumptions.\n"
                "Reference SANS training on common analyst mistakes.\n"
                "Challenge the obvious interpretation.\n\n",
            ),
            TaskType.DEBATE_PRAGMATIST: (
                "Pragmatist",
                "You are the Pragmatist for a threat hunting investigation.\n"
                "Suggest the most actionable, efficient next steps.\n"
                "Reference SANS incident response playbooks.\n"
                "Focus on: quick wins, triage priorities, what to escalate.\n\n",
            ),
        }

        async def _call_perspective(task_type: TaskType, role_name: str, prefix: str):
            decision = self.router.route(task_type)
            provider = self.router.get_provider(decision)
            full_prompt = prefix + prompt

            if isinstance(provider, OpenWebUIProvider):
                result = await provider.generate(
                    full_prompt,
                    system=f"You are the {role_name}. Provide analysis only. No execution.",
                    max_tokens=settings.AGENT_MAX_TOKENS,
                    temperature=0.4,
                )
            else:
                result = await provider.generate(
                    full_prompt,
                    system=f"You are the {role_name}. Provide analysis only. No execution.",
                    max_tokens=settings.AGENT_MAX_TOKENS,
                    temperature=0.4,
                )

            return Perspective(
                role=role_name,
                content=result.get("response", ""),
                model_used=decision.model,
                node_used=decision.node.value,
                latency_ms=result.get("_latency_ms", 0),
            )

        # Run perspectives in parallel
        perspective_tasks = [
            _call_perspective(tt, name, prefix)
            for tt, (name, prefix) in roles.items()
        ]
        perspectives = await asyncio.gather(*perspective_tasks)

        # Judge merges the perspectives
        judge_prompt = (
            "You are the Judge. Merge these three threat hunting perspectives into "
            "ONE final advisory answer.\n\n"
            "Rules:\n"
            "- Advisory only — no execution\n"
            "- Clearly list risks and assumptions\n"
            "- Highlight where perspectives agree and disagree\n"
            "- Provide a unified recommendation\n"
            "- Reference SANS methodologies where relevant\n\n"
        )
        for p in perspectives:
            judge_prompt += f"=== {p.role} (via {p.model_used}) ===\n{p.content}\n\n"

        judge_prompt += (
            f"\nOriginal analyst query:\n{context.query}\n\n"
            "Respond with the merged analysis in this JSON format:\n"
            '{"guidance": "...", "confidence": 0.85, "suggested_pivots": [...], '
            '"suggested_filters": [...], "caveats": "...", "reasoning": "...", '
            '"sans_references": [...]}'
        )

        judge_decision = self.router.route(TaskType.DEBATE_JUDGE)
        judge_provider = self.router.get_provider(judge_decision)

        if isinstance(judge_provider, OpenWebUIProvider):
            judge_result = await judge_provider.generate(
                judge_prompt,
                system="You are the Judge. Merge perspectives into a final advisory answer. Respond with JSON only.",
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=0.2,
            )
        else:
            judge_result = await judge_provider.generate(
                judge_prompt,
                system="You are the Judge. Merge perspectives into a final advisory answer. Respond with JSON only.",
                max_tokens=settings.AGENT_MAX_TOKENS,
                temperature=0.2,
            )

        raw_text = judge_result.get("response", "")
        response = self._parse_response(raw_text, context)
        response.model_used = judge_decision.model
        response.node_used = judge_decision.node.value
        response.latency_ms = int((time.monotonic() - start) * 1000)
        response.perspectives = list(perspectives)

        return response

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the prompt with all available context."""
        parts = [f"Analyst query: {context.query}"]

        if context.dataset_name:
            parts.append(f"Dataset: {context.dataset_name}")
        if context.artifact_type:
            parts.append(f"Artifact type: {context.artifact_type}")
        if context.host_identifier:
            parts.append(f"Host: {context.host_identifier}")
        if context.data_summary:
            parts.append(f"Data summary: {context.data_summary}")
        if context.active_hypotheses:
            parts.append(f"Active hypotheses: {'; '.join(context.active_hypotheses)}")
        if context.annotations_summary:
            parts.append(f"Analyst annotations: {context.annotations_summary}")
        if context.enrichment_summary:
            parts.append(f"Enrichment data: {context.enrichment_summary}")
        if context.conversation_history:
            parts.append("\nRecent conversation:")
            for msg in context.conversation_history[-settings.AGENT_HISTORY_LENGTH:]:
                parts.append(f"  {msg.get('role', 'unknown')}: {msg.get('content', '')[:500]}")

        return "\n".join(parts)

    def _parse_response(self, raw: str, context: AgentContext) -> AgentResponse:
        """Parse LLM output into structured AgentResponse.

        Tries JSON extraction first, falls back to raw text with defaults.
        """
        parsed = self._try_parse_json(raw)
        if parsed:
            return AgentResponse(
                guidance=parsed.get("guidance", raw),
                confidence=min(max(float(parsed.get("confidence", 0.7)), 0.0), 1.0),
                suggested_pivots=parsed.get("suggested_pivots", [])[:6],
                suggested_filters=parsed.get("suggested_filters", [])[:6],
                caveats=parsed.get("caveats"),
                reasoning=parsed.get("reasoning"),
                sans_references=parsed.get("sans_references", []),
            )

        # Fallback: use raw text as guidance
        return AgentResponse(
            guidance=raw.strip() or "No guidance generated. Please try rephrasing your question.",
            confidence=0.5,
            suggested_pivots=[],
            suggested_filters=[],
            caveats="Response was not in structured format. Pivots and filters may be embedded in the guidance text.",
            reasoning=None,
            sans_references=[],
        )

    def _try_parse_json(self, text: str) -> dict | None:
        """Try to extract JSON from LLM output."""
        # Direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Extract from code fences
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1) if match.lastindex else match.group(0))
                except (json.JSONDecodeError, IndexError):
                    continue

        return None

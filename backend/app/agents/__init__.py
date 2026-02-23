"""Analyst-assist agent module for ThreatHunt.

Provides read-only guidance on CSV artifact data, analytical pivots, and hypotheses.
Agents are advisory only and do not execute actions or modify data.
"""

from .core_v2 import ThreatHuntAgent, AgentContext, AgentResponse, Perspective
from .providers_v2 import OllamaProvider, OpenWebUIProvider, EmbeddingProvider

__all__ = [
    "ThreatHuntAgent",
    "AgentContext",
    "AgentResponse",
    "Perspective",
    "OllamaProvider",
    "OpenWebUIProvider",
    "EmbeddingProvider",
]

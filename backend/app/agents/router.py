"""Task router — auto-selects the right model + node for each task type.

Routes based on task characteristics:
- Quick chat → fast models via cluster
- Deep analysis → 70B+ models on Wile
- Code/script analysis → code models (32b on Wile, 7b for quick)
- Vision/image → vision models on Roadrunner
- Embedding → embedding models on either node
"""

import logging
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from .registry import Capability, Tier, Node, ModelEntry, registry
from .providers_v2 import OllamaProvider, OpenWebUIProvider, EmbeddingProvider

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    QUICK_CHAT = "quick_chat"
    DEEP_ANALYSIS = "deep_analysis"
    CODE_ANALYSIS = "code_analysis"
    VISION = "vision"
    EMBEDDING = "embedding"
    DEBATE_PLANNER = "debate_planner"
    DEBATE_CRITIC = "debate_critic"
    DEBATE_PRAGMATIST = "debate_pragmatist"
    DEBATE_JUDGE = "debate_judge"


@dataclass
class RoutingDecision:
    """Result of the routing decision."""
    model: str
    node: Node
    task_type: TaskType
    provider_type: str  # "ollama" or "openwebui"
    reason: str


class TaskRouter:
    """Routes tasks to the appropriate model and node."""

    # Default routing rules: task_type → (capability, preferred_tier, preferred_node)
    ROUTING_RULES: dict[TaskType, tuple[Capability, Tier | None, Node | None]] = {
        TaskType.QUICK_CHAT: (Capability.CHAT, Tier.FAST, None),
        TaskType.DEEP_ANALYSIS: (Capability.CHAT, Tier.HEAVY, Node.WILE),
        TaskType.CODE_ANALYSIS: (Capability.CODE, Tier.MEDIUM, Node.WILE),
        TaskType.VISION: (Capability.VISION, None, Node.ROADRUNNER),
        TaskType.EMBEDDING: (Capability.EMBEDDING, Tier.FAST, None),
        TaskType.DEBATE_PLANNER: (Capability.CHAT, Tier.HEAVY, Node.WILE),
        TaskType.DEBATE_CRITIC: (Capability.CHAT, Tier.HEAVY, Node.WILE),
        TaskType.DEBATE_PRAGMATIST: (Capability.CHAT, Tier.HEAVY, Node.WILE),
        TaskType.DEBATE_JUDGE: (Capability.CHAT, Tier.MEDIUM, Node.WILE),
    }

    # Specific model overrides for debate roles (use diverse models for diversity of thought)
    DEBATE_MODEL_OVERRIDES: dict[TaskType, str] = {
        TaskType.DEBATE_PLANNER: "llama3.1:70b-instruct-q4_K_M",
        TaskType.DEBATE_CRITIC: "qwen2:72b-instruct",
        TaskType.DEBATE_PRAGMATIST: "mixtral:8x22b-instruct",
        TaskType.DEBATE_JUDGE: "gemma2:27b",
    }

    def __init__(self):
        self.registry = registry

    def route(self, task_type: TaskType, model_override: str | None = None) -> RoutingDecision:
        """Decide which model and node to use for a task."""

        # Explicit model override
        if model_override:
            entries = self.registry.find()
            for entry in entries:
                if entry.name == model_override:
                    return RoutingDecision(
                        model=model_override,
                        node=entry.node,
                        task_type=task_type,
                        provider_type="ollama",
                        reason=f"Explicit model override: {model_override}",
                    )
            # Model not in registry — try via cluster
            return RoutingDecision(
                model=model_override,
                node=Node.CLUSTER,
                task_type=task_type,
                provider_type="openwebui",
                reason=f"Override model {model_override} not in registry, routing to cluster",
            )

        # Debate model overrides
        if task_type in self.DEBATE_MODEL_OVERRIDES:
            model_name = self.DEBATE_MODEL_OVERRIDES[task_type]
            entries = self.registry.find()
            for entry in entries:
                if entry.name == model_name:
                    return RoutingDecision(
                        model=model_name,
                        node=entry.node,
                        task_type=task_type,
                        provider_type="ollama",
                        reason=f"Debate role {task_type.value} → {model_name} on {entry.node.value}",
                    )

        # Standard routing
        cap, tier, node = self.ROUTING_RULES.get(
            task_type,
            (Capability.CHAT, Tier.FAST, None),
        )

        entry = self.registry.get_best(cap, prefer_tier=tier, prefer_node=node)
        if entry:
            return RoutingDecision(
                model=entry.name,
                node=entry.node,
                task_type=task_type,
                provider_type="ollama",
                reason=f"Auto-routed {task_type.value}: {cap.value}/{tier.value if tier else 'any'} → {entry.name} on {entry.node.value}",
            )

        # Fallback to cluster
        default_model = settings.DEFAULT_FAST_MODEL
        return RoutingDecision(
            model=default_model,
            node=Node.CLUSTER,
            task_type=task_type,
            provider_type="openwebui",
            reason=f"No registry match, falling back to cluster with {default_model}",
        )

    def get_provider(self, decision: RoutingDecision):
        """Create the appropriate provider for a routing decision."""
        if decision.provider_type == "openwebui":
            return OpenWebUIProvider(model=decision.model)
        else:
            return OllamaProvider(model=decision.model, node=decision.node)

    def get_embedding_provider(self, model: str | None = None, node: Node | None = None) -> EmbeddingProvider:
        """Get an embedding provider."""
        return EmbeddingProvider(
            model=model or settings.DEFAULT_EMBEDDING_MODEL,
            node=node or Node.ROADRUNNER,
        )

    def classify_task(self, query: str, has_image: bool = False) -> TaskType:
        """Heuristic classification of query into task type.

        In practice this could be enhanced by a classifier model, but
        keyword heuristics work well for routing.
        """
        if has_image:
            return TaskType.VISION

        q = query.lower()

        # Code/script indicators
        code_indicators = [
            "deobfuscate", "decode", "powershell", "script", "base64",
            "command line", "cmdline", "commandline", "obfuscated",
            "malware", "shellcode", "vbs", "vbscript", "batch",
            "python script", "code review", "reverse engineer",
        ]
        if any(ind in q for ind in code_indicators):
            return TaskType.CODE_ANALYSIS

        # Deep analysis indicators
        deep_indicators = [
            "deep analysis", "detailed", "comprehensive", "thorough",
            "investigate", "root cause", "advanced", "explain in detail",
            "full analysis", "forensic",
        ]
        if any(ind in q for ind in deep_indicators):
            return TaskType.DEEP_ANALYSIS

        return TaskType.QUICK_CHAT


# Singleton
task_router = TaskRouter()

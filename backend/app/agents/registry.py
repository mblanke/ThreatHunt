"""Model registry — inventory of all Ollama models across Wile and Roadrunner.

Each model is tagged with capabilities (chat, code, vision, embedding) and
performance tier (fast, medium, heavy) for the TaskRouter.
"""

from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    CHAT = "chat"
    CODE = "code"
    VISION = "vision"
    EMBEDDING = "embedding"


class Tier(str, Enum):
    FAST = "fast"        # < 15B params — quick responses
    MEDIUM = "medium"    # 15–40B params — balanced
    HEAVY = "heavy"      # 40B+ params — deep analysis


class Node(str, Enum):
    WILE = "wile"
    ROADRUNNER = "roadrunner"
    CLUSTER = "cluster"  # Open WebUI balances across both


@dataclass
class ModelEntry:
    name: str
    node: Node
    capabilities: list[Capability]
    tier: Tier
    param_size: str = ""  # e.g. "7b", "70b"
    notes: str = ""


# ── Roadrunner (100.110.190.11) ──────────────────────────────────────

ROADRUNNER_MODELS: list[ModelEntry] = [
    # General / chat
    ModelEntry("llama3.1:latest", Node.ROADRUNNER, [Capability.CHAT], Tier.FAST, "8b"),
    ModelEntry("qwen2.5:14b-instruct", Node.ROADRUNNER, [Capability.CHAT], Tier.FAST, "14b"),
    ModelEntry("mistral:7b-instruct", Node.ROADRUNNER, [Capability.CHAT], Tier.FAST, "7b"),
    ModelEntry("mistral:7b", Node.ROADRUNNER, [Capability.CHAT], Tier.FAST, "7b"),
    ModelEntry("qwen2.5:7b", Node.ROADRUNNER, [Capability.CHAT], Tier.FAST, "7b"),
    ModelEntry("phi3:medium", Node.ROADRUNNER, [Capability.CHAT], Tier.MEDIUM, "14b"),
    # Code
    ModelEntry("qwen2.5-coder:7b", Node.ROADRUNNER, [Capability.CODE], Tier.FAST, "7b"),
    ModelEntry("qwen2.5-coder:latest", Node.ROADRUNNER, [Capability.CODE], Tier.FAST, "7b"),
    ModelEntry("codestral:latest", Node.ROADRUNNER, [Capability.CODE], Tier.MEDIUM, "22b"),
    ModelEntry("codellama:13b", Node.ROADRUNNER, [Capability.CODE], Tier.FAST, "13b"),
    # Vision
    ModelEntry("llama3.2-vision:11b", Node.ROADRUNNER, [Capability.VISION], Tier.FAST, "11b"),
    ModelEntry("minicpm-v:latest", Node.ROADRUNNER, [Capability.VISION], Tier.FAST, "8b"),
    ModelEntry("llava:13b", Node.ROADRUNNER, [Capability.VISION], Tier.FAST, "13b"),
    # Embeddings
    ModelEntry("bge-m3:latest", Node.ROADRUNNER, [Capability.EMBEDDING], Tier.FAST, "0.6b"),
    ModelEntry("nomic-embed-text:latest", Node.ROADRUNNER, [Capability.EMBEDDING], Tier.FAST, "0.1b"),
    # Heavy
    ModelEntry("llama3.1:70b-instruct-q4_K_M", Node.ROADRUNNER, [Capability.CHAT], Tier.HEAVY, "70b"),
]

# ── Wile (100.110.190.12) ────────────────────────────────────────────

WILE_MODELS: list[ModelEntry] = [
    # General / chat
    ModelEntry("llama3.1:latest", Node.WILE, [Capability.CHAT], Tier.FAST, "8b"),
    ModelEntry("llama3:latest", Node.WILE, [Capability.CHAT], Tier.FAST, "8b"),
    ModelEntry("gemma2:27b", Node.WILE, [Capability.CHAT], Tier.MEDIUM, "27b"),
    # Code
    ModelEntry("qwen2.5-coder:7b", Node.WILE, [Capability.CODE], Tier.FAST, "7b"),
    ModelEntry("qwen2.5-coder:latest", Node.WILE, [Capability.CODE], Tier.FAST, "7b"),
    ModelEntry("qwen2.5-coder:32b", Node.WILE, [Capability.CODE], Tier.MEDIUM, "32b"),
    ModelEntry("deepseek-coder:33b", Node.WILE, [Capability.CODE], Tier.MEDIUM, "33b"),
    ModelEntry("codestral:latest", Node.WILE, [Capability.CODE], Tier.MEDIUM, "22b"),
    # Vision
    ModelEntry("llava:13b", Node.WILE, [Capability.VISION], Tier.FAST, "13b"),
    # Embeddings
    ModelEntry("bge-m3:latest", Node.WILE, [Capability.EMBEDDING], Tier.FAST, "0.6b"),
    # Heavy
    ModelEntry("llama3.1:70b", Node.WILE, [Capability.CHAT], Tier.HEAVY, "70b"),
    ModelEntry("llama3.1:70b-instruct-q4_K_M", Node.WILE, [Capability.CHAT], Tier.HEAVY, "70b"),
    ModelEntry("llama3.1:70b-instruct-q5_K_M", Node.WILE, [Capability.CHAT], Tier.HEAVY, "70b"),
    ModelEntry("mixtral:8x22b-instruct", Node.WILE, [Capability.CHAT], Tier.HEAVY, "141b"),
    ModelEntry("qwen2:72b-instruct", Node.WILE, [Capability.CHAT], Tier.HEAVY, "72b"),
]

ALL_MODELS = ROADRUNNER_MODELS + WILE_MODELS


class ModelRegistry:
    """Registry of all available models and their capabilities."""

    def __init__(self, models: list[ModelEntry] | None = None):
        self.models = models or ALL_MODELS
        self._by_name: dict[str, list[ModelEntry]] = {}
        self._by_capability: dict[Capability, list[ModelEntry]] = {}
        self._by_node: dict[Node, list[ModelEntry]] = {}
        self._index()

    def _index(self):
        for m in self.models:
            self._by_name.setdefault(m.name, []).append(m)
            for cap in m.capabilities:
                self._by_capability.setdefault(cap, []).append(m)
            self._by_node.setdefault(m.node, []).append(m)

    def find(
        self,
        capability: Capability | None = None,
        tier: Tier | None = None,
        node: Node | None = None,
    ) -> list[ModelEntry]:
        """Find models matching all given criteria."""
        results = list(self.models)
        if capability:
            results = [m for m in results if capability in m.capabilities]
        if tier:
            results = [m for m in results if m.tier == tier]
        if node:
            results = [m for m in results if m.node == node]
        return results

    def get_best(
        self,
        capability: Capability,
        prefer_tier: Tier | None = None,
        prefer_node: Node | None = None,
    ) -> ModelEntry | None:
        """Get the best model for a capability, with optional preference."""
        candidates = self.find(capability=capability, tier=prefer_tier, node=prefer_node)
        if not candidates:
            candidates = self.find(capability=capability, tier=prefer_tier)
        if not candidates:
            candidates = self.find(capability=capability)
        return candidates[0] if candidates else None

    def list_nodes(self) -> list[Node]:
        return list(self._by_node.keys())

    def list_models_on_node(self, node: Node) -> list[ModelEntry]:
        return self._by_node.get(node, [])

    def to_dict(self) -> list[dict]:
        return [
            {
                "name": m.name,
                "node": m.node.value,
                "capabilities": [c.value for c in m.capabilities],
                "tier": m.tier.value,
                "param_size": m.param_size,
            }
            for m in self.models
        ]


# Singleton
registry = ModelRegistry()

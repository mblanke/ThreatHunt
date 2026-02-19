"""Tests for model registry and task router."""

import pytest
from app.agents.registry import (
    ModelRegistry, ModelEntry, Capability, Tier, Node,
    registry, ROADRUNNER_MODELS, WILE_MODELS,
)
from app.agents.router import TaskRouter, TaskType, task_router


class TestModelRegistry:
    """Tests for the model registry."""

    def test_registry_has_models(self):
        assert len(registry.models) > 0
        assert len(ROADRUNNER_MODELS) > 0
        assert len(WILE_MODELS) > 0

    def test_find_by_capability(self):
        chat_models = registry.find(capability=Capability.CHAT)
        assert len(chat_models) > 0
        for m in chat_models:
            assert Capability.CHAT in m.capabilities

    def test_find_code_models(self):
        code_models = registry.find(capability=Capability.CODE)
        assert len(code_models) > 0

    def test_find_vision_models(self):
        vision_models = registry.find(capability=Capability.VISION)
        assert len(vision_models) > 0

    def test_find_embedding_models(self):
        embed_models = registry.find(capability=Capability.EMBEDDING)
        assert len(embed_models) > 0

    def test_find_by_node(self):
        wile_models = registry.find(node=Node.WILE)
        rr_models = registry.find(node=Node.ROADRUNNER)
        assert len(wile_models) > 0
        assert len(rr_models) > 0

    def test_find_heavy_models(self):
        heavy = registry.find(tier=Tier.HEAVY)
        assert len(heavy) > 0
        for m in heavy:
            assert m.tier == Tier.HEAVY

    def test_get_best(self):
        best = registry.get_best(Capability.CHAT, prefer_tier=Tier.FAST)
        assert best is not None
        assert Capability.CHAT in best.capabilities

    def test_get_best_vision_on_roadrunner(self):
        best = registry.get_best(Capability.VISION, prefer_node=Node.ROADRUNNER)
        assert best is not None
        assert Capability.VISION in best.capabilities

    def test_to_dict(self):
        result = registry.to_dict()
        assert isinstance(result, list)
        assert len(result) > 0
        assert "name" in result[0]
        assert "capabilities" in result[0]


class TestTaskRouter:
    """Tests for the task router."""

    def test_route_quick_chat(self):
        decision = task_router.route(TaskType.QUICK_CHAT)
        assert decision.model
        assert decision.node

    def test_route_deep_analysis(self):
        decision = task_router.route(TaskType.DEEP_ANALYSIS)
        assert decision.model
        # Deep should route to heavy model
        assert decision.task_type == TaskType.DEEP_ANALYSIS

    def test_route_code_analysis(self):
        decision = task_router.route(TaskType.CODE_ANALYSIS)
        assert decision.model
        assert "coder" in decision.model.lower() or "code" in decision.model.lower()

    def test_route_vision(self):
        decision = task_router.route(TaskType.VISION)
        assert decision.model
        assert decision.node == Node.ROADRUNNER

    def test_route_with_model_override(self):
        decision = task_router.route(TaskType.QUICK_CHAT, model_override="llama3.1:latest")
        assert decision.model == "llama3.1:latest"

    def test_route_unknown_model_to_cluster(self):
        decision = task_router.route(TaskType.QUICK_CHAT, model_override="nonexistent-model:99b")
        assert decision.node == Node.CLUSTER
        assert decision.provider_type == "openwebui"

    def test_classify_code_task(self):
        assert task_router.classify_task("deobfuscate this powershell script") == TaskType.CODE_ANALYSIS
        assert task_router.classify_task("decode this base64 payload") == TaskType.CODE_ANALYSIS

    def test_classify_deep_task(self):
        assert task_router.classify_task("detailed forensic analysis of this process tree") == TaskType.DEEP_ANALYSIS

    def test_classify_vision_task(self):
        assert task_router.classify_task("analyze this screenshot", has_image=True) == TaskType.VISION

    def test_classify_quick_task(self):
        assert task_router.classify_task("what does this process do?") == TaskType.QUICK_CHAT

    def test_debate_model_overrides(self):
        for task_type in [TaskType.DEBATE_PLANNER, TaskType.DEBATE_CRITIC, TaskType.DEBATE_PRAGMATIST, TaskType.DEBATE_JUDGE]:
            decision = task_router.route(task_type)
            assert decision.model
            assert decision.task_type == task_type

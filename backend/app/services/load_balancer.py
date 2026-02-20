"""Smart load balancer for Wile & Roadrunner LLM nodes.

Tracks active jobs per node, health status, and routes new work
to the least-busy healthy node.  Periodically pings both nodes
to maintain an up-to-date health map.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class NodeId(str, Enum):
    WILE = "wile"
    ROADRUNNER = "roadrunner"


class WorkloadTier(str, Enum):
    """What kind of workload is this?"""
    HEAVY = "heavy"      # 70B models, deep analysis, reports
    FAST = "fast"        # 7-14B models, triage, quick queries
    EMBEDDING = "embed"  # bge-m3 embeddings
    ANY = "any"


@dataclass
class NodeStatus:
    node_id: NodeId
    url: str
    healthy: bool = True
    last_check: float = 0.0
    active_jobs: int = 0
    total_completed: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    _latencies: list[float] = field(default_factory=list)

    def record_completion(self, latency_ms: float):
        self.active_jobs = max(0, self.active_jobs - 1)
        self.total_completed += 1
        self._latencies.append(latency_ms)
        # Rolling average of last 50
        if len(self._latencies) > 50:
            self._latencies = self._latencies[-50:]
        self.avg_latency_ms = sum(self._latencies) / len(self._latencies)

    def record_error(self):
        self.active_jobs = max(0, self.active_jobs - 1)
        self.total_errors += 1

    def record_start(self):
        self.active_jobs += 1


class LoadBalancer:
    """Routes LLM work to the least-busy healthy node.

    Node capabilities:
    - Wile: Heavy models (70B), code models (32B)
    - Roadrunner: Fast models (7-14B), embeddings (bge-m3), vision
    """

    # Which nodes can handle which tiers
    TIER_NODES = {
        WorkloadTier.HEAVY: [NodeId.WILE],
        WorkloadTier.FAST: [NodeId.ROADRUNNER, NodeId.WILE],
        WorkloadTier.EMBEDDING: [NodeId.ROADRUNNER],
        WorkloadTier.ANY: [NodeId.ROADRUNNER, NodeId.WILE],
    }

    def __init__(self):
        self._nodes: dict[NodeId, NodeStatus] = {
            NodeId.WILE: NodeStatus(
                node_id=NodeId.WILE,
                url=f"http://{settings.WILE_HOST}:{settings.WILE_OLLAMA_PORT}",
            ),
            NodeId.ROADRUNNER: NodeStatus(
                node_id=NodeId.ROADRUNNER,
                url=f"http://{settings.ROADRUNNER_HOST}:{settings.ROADRUNNER_OLLAMA_PORT}",
            ),
        }
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None

    async def start_health_loop(self, interval: float = 30.0):
        """Start background health-check loop."""
        if self._health_task and not self._health_task.done():
            return
        self._health_task = asyncio.create_task(self._health_loop(interval))
        logger.info("Load balancer health loop started (%.0fs interval)", interval)

    async def stop_health_loop(self):
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

    async def _health_loop(self, interval: float):
        while True:
            try:
                await self.check_health()
            except Exception as e:
                logger.warning(f"Health check error: {e}")
            await asyncio.sleep(interval)

    async def check_health(self):
        """Ping both nodes and update status."""
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            for nid, status in self._nodes.items():
                try:
                    resp = await client.get(f"{status.url}/api/tags")
                    status.healthy = resp.status_code == 200
                except Exception:
                    status.healthy = False
                status.last_check = time.time()
                logger.debug(
                    f"Health: {nid.value} = {'OK' if status.healthy else 'DOWN'} "
                    f"(active={status.active_jobs})"
                )

    def select_node(self, tier: WorkloadTier = WorkloadTier.ANY) -> NodeId:
        """Select the best node for a workload tier.

        Strategy: among healthy nodes that support the tier,
        pick the one with fewest active jobs.
        Falls back to any node if none healthy.
        """
        candidates = self.TIER_NODES.get(tier, [NodeId.ROADRUNNER, NodeId.WILE])

        # Filter to healthy candidates
        healthy = [
            nid for nid in candidates
            if self._nodes[nid].healthy
        ]

        if not healthy:
            logger.warning(f"No healthy nodes for tier {tier.value}, using first candidate")
            healthy = candidates

        # Pick least busy
        best = min(healthy, key=lambda nid: self._nodes[nid].active_jobs)
        return best

    def acquire(self, tier: WorkloadTier = WorkloadTier.ANY) -> NodeId:
        """Select node and mark a job started."""
        node = self.select_node(tier)
        self._nodes[node].record_start()
        logger.info(
            f"LB: dispatched {tier.value} -> {node.value} "
            f"(active={self._nodes[node].active_jobs})"
        )
        return node

    def release(self, node: NodeId, latency_ms: float = 0, error: bool = False):
        """Mark a job completed on a node."""
        status = self._nodes.get(node)
        if not status:
            return
        if error:
            status.record_error()
        else:
            status.record_completion(latency_ms)

    def get_status(self) -> dict:
        """Get current load balancer status."""
        return {
            nid.value: {
                "healthy": s.healthy,
                "active_jobs": s.active_jobs,
                "total_completed": s.total_completed,
                "total_errors": s.total_errors,
                "avg_latency_ms": round(s.avg_latency_ms, 1),
                "last_check": s.last_check,
            }
            for nid, s in self._nodes.items()
        }


# Singleton
lb = LoadBalancer()
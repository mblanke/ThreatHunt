"""
Job Scheduler

Manages job distribution across GPU nodes based on availability and load.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio


class NodeStatus(Enum):
    """Status of GPU node"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class GPUNode:
    """Represents a GPU compute node"""
    node_id: str
    hostname: str
    port: int
    vram_total_gb: int
    vram_used_gb: int
    compute_utilization: float  # 0.0 to 1.0
    status: NodeStatus
    models_loaded: List[str]
    
    @property
    def vram_available_gb(self) -> int:
        """Calculate available VRAM"""
        return self.vram_total_gb - self.vram_used_gb
    
    @property
    def is_available(self) -> bool:
        """Check if node is available for work"""
        return self.status == NodeStatus.AVAILABLE and self.compute_utilization < 0.9


@dataclass
class Job:
    """Represents an LLM job"""
    job_id: str
    model: str
    priority: int
    estimated_vram_gb: int
    requires_parallel: bool
    requires_chaining: bool
    payload: Dict[str, Any]


class JobScheduler:
    """
    Job Scheduler - Manages distribution of LLM jobs across GPU nodes
    
    Decides:
    - Which GB10 device is available
    - GPU load (VRAM, compute utilization)
    - Whether to parallelize across both nodes
    - Whether job requires serial reasoning (chained)
    """
    
    def __init__(self):
        """Initialize job scheduler"""
        self.nodes: Dict[str, GPUNode] = {}
        self.job_queue: List[Job] = []
        self._initialize_nodes()
    
    def _initialize_nodes(self):
        """Initialize GPU node configuration"""
        # GB10 Node 1
        self.nodes["gb10-node-1"] = GPUNode(
            node_id="gb10-node-1",
            hostname="gb10-node-1",
            port=8001,
            vram_total_gb=80,
            vram_used_gb=0,
            compute_utilization=0.0,
            status=NodeStatus.AVAILABLE,
            models_loaded=["deepseek", "qwen72"]
        )
        
        # GB10 Node 2
        self.nodes["gb10-node-2"] = GPUNode(
            node_id="gb10-node-2",
            hostname="gb10-node-2",
            port=8001,
            vram_total_gb=80,
            vram_used_gb=0,
            compute_utilization=0.0,
            status=NodeStatus.AVAILABLE,
            models_loaded=["phi4", "qwen-coder", "llama31", "granite-guardian"]
        )
    
    def get_available_nodes(self) -> List[GPUNode]:
        """Get list of available nodes"""
        return [node for node in self.nodes.values() if node.is_available]
    
    def find_best_node(self, job: Job) -> Optional[GPUNode]:
        """
        Find best node for a job based on availability and requirements
        
        Args:
            job: Job to schedule
        
        Returns:
            Best GPU node or None if unavailable
        """
        available_nodes = self.get_available_nodes()
        
        # Filter nodes that have required model loaded
        suitable_nodes = [
            node for node in available_nodes
            if job.model in node.models_loaded
            and node.vram_available_gb >= job.estimated_vram_gb
        ]
        
        if not suitable_nodes:
            return None
        
        # Sort by compute utilization (prefer less loaded nodes)
        suitable_nodes.sort(key=lambda n: n.compute_utilization)
        
        return suitable_nodes[0]
    
    def should_parallelize(self, job: Job) -> bool:
        """
        Determine if job should be parallelized across multiple nodes
        
        Args:
            job: Job to evaluate
        
        Returns:
            True if should parallelize
        """
        available_nodes = self.get_available_nodes()
        
        # Need at least 2 nodes for parallelization
        if len(available_nodes) < 2:
            return False
        
        # Job explicitly requires parallel execution
        if job.requires_parallel:
            return True
        
        # High priority jobs with multiple available nodes
        if job.priority >= 1 and len(available_nodes) >= 2:
            return True
        
        return False
    
    def get_parallel_nodes(self, job: Job) -> List[GPUNode]:
        """
        Get nodes for parallel execution
        
        Args:
            job: Job to parallelize
        
        Returns:
            List of nodes to use
        """
        available_nodes = self.get_available_nodes()
        
        # Filter nodes with required model and sufficient VRAM
        suitable_nodes = [
            node for node in available_nodes
            if job.model in node.models_loaded
            and node.vram_available_gb >= job.estimated_vram_gb
        ]
        
        # Return up to 2 nodes for parallel execution
        return suitable_nodes[:2]
    
    async def schedule_job(self, job: Job) -> Dict[str, Any]:
        """
        Schedule a job for execution
        
        Args:
            job: Job to schedule
        
        Returns:
            Scheduling decision with node assignments
        """
        # Check if job should be parallelized
        if self.should_parallelize(job):
            nodes = self.get_parallel_nodes(job)
            if len(nodes) >= 2:
                return {
                    "job_id": job.job_id,
                    "execution_mode": "parallel",
                    "nodes": [
                        {"node_id": node.node_id, "endpoint": f"http://{node.hostname}:{node.port}/{job.model}"}
                        for node in nodes
                    ],
                    "estimated_time": "distributed"
                }
        
        # Serial execution on single node
        node = self.find_best_node(job)
        
        if not node:
            # Add to queue if no nodes available
            self.job_queue.append(job)
            return {
                "job_id": job.job_id,
                "execution_mode": "queued",
                "status": "waiting_for_resources",
                "queue_position": len(self.job_queue)
            }
        
        return {
            "job_id": job.job_id,
            "execution_mode": "serial" if job.requires_chaining else "single",
            "node": {
                "node_id": node.node_id,
                "endpoint": f"http://{node.hostname}:{node.port}/{job.model}"
            },
            "vram_allocated_gb": job.estimated_vram_gb,
            "estimated_time": "standard"
        }
    
    def update_node_status(
        self,
        node_id: str,
        vram_used_gb: Optional[int] = None,
        compute_utilization: Optional[float] = None,
        status: Optional[NodeStatus] = None
    ):
        """
        Update node status metrics
        
        Args:
            node_id: Node to update
            vram_used_gb: Current VRAM usage
            compute_utilization: Current compute utilization (0.0-1.0)
            status: Node status
        """
        if node_id not in self.nodes:
            return
        
        node = self.nodes[node_id]
        
        if vram_used_gb is not None:
            node.vram_used_gb = vram_used_gb
        
        if compute_utilization is not None:
            node.compute_utilization = compute_utilization
        
        if status is not None:
            node.status = status


def get_job_scheduler() -> JobScheduler:
    """
    Factory function to create job scheduler
    
    Returns:
        Configured JobScheduler instance
    """
    return JobScheduler()

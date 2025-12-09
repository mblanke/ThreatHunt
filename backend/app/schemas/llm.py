from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class LLMRequestSchema(BaseModel):
    """Schema for LLM processing request"""
    prompt: str
    task_hints: Optional[List[str]] = []
    requires_parallel: bool = False
    requires_chaining: bool = False
    batch_size: int = 1
    operations: Optional[List[str]] = []
    parameters: Optional[Dict[str, Any]] = None


class RoutingDecision(BaseModel):
    """Schema for routing decision"""
    task_type: str
    model: str
    endpoint: str
    priority: int
    description: str
    requires_parallel: bool
    requires_chaining: bool


class NodeInfo(BaseModel):
    """Schema for GPU node information"""
    node_id: str
    hostname: str
    vram_total_gb: int
    vram_used_gb: int
    vram_available_gb: int
    compute_utilization: float
    status: str
    models_loaded: List[str]


class SchedulingDecision(BaseModel):
    """Schema for job scheduling decision"""
    job_id: str
    execution_mode: str
    nodes: Optional[List[Dict[str, str]]] = None
    node: Optional[Dict[str, str]] = None
    status: Optional[str] = None
    queue_position: Optional[int] = None


class LLMResponseSchema(BaseModel):
    """Schema for LLM response"""
    job_id: str
    status: str
    routing: Optional[RoutingDecision] = None
    scheduling: Optional[SchedulingDecision] = None
    result: Any
    execution_mode: str


class ModelInfo(BaseModel):
    """Schema for model information"""
    model_name: str
    node_id: str
    endpoint_url: str
    is_available: bool


class MergedResult(BaseModel):
    """Schema for merged result"""
    strategy: str
    result: Any
    confidence: Optional[float] = None
    num_models: Optional[int] = None
    all_results: Optional[List[Dict[str, Any]]] = None

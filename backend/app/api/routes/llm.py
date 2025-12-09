from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_role
from app.core.llm_router import get_llm_router, TaskType
from app.core.job_scheduler import get_job_scheduler, Job, NodeStatus
from app.core.llm_pool import get_llm_pool
from app.core.merger_agent import get_merger_agent, MergeStrategy
from app.models.user import User

router = APIRouter()


class LLMRequest(BaseModel):
    """Request for LLM processing"""
    prompt: str
    task_hints: Optional[List[str]] = []
    requires_parallel: bool = False
    requires_chaining: bool = False
    batch_size: int = 1
    operations: Optional[List[str]] = []
    parameters: Optional[Dict[str, Any]] = None


class LLMResponse(BaseModel):
    """Response from LLM processing"""
    job_id: str
    result: Any
    execution_mode: str
    models_used: List[str]
    strategy: Optional[str] = None


class NodeStatusUpdate(BaseModel):
    """Update node status"""
    node_id: str
    vram_used_gb: Optional[int] = None
    compute_utilization: Optional[float] = None
    status: Optional[str] = None


@router.post("/process", response_model=Dict[str, Any])
async def process_llm_request(
    request: LLMRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Process an LLM request through the distributed routing system
    
    The request flows through:
    1. Router Agent - classifies and routes to appropriate model
    2. Job Scheduler - determines execution strategy
    3. LLM Pool - executes on appropriate endpoints
    4. Merger Agent - combines results if multiple models used
    """
    # Step 1: Route the request
    router_agent = get_llm_router()
    routing_decision = router_agent.route_request(request.dict())
    
    # Step 2: Schedule the job
    scheduler = get_job_scheduler()
    job = Job(
        job_id=f"job_{current_user.id}_{hash(request.prompt) % 10000}",
        model=routing_decision["model"],
        priority=routing_decision["priority"],
        estimated_vram_gb=10,  # Estimate based on model
        requires_parallel=request.requires_parallel,
        requires_chaining=request.requires_chaining,
        payload=request.dict()
    )
    
    scheduling_decision = await scheduler.schedule_job(job)
    
    # Step 3: Execute on LLM pool
    pool = get_llm_pool()
    
    if scheduling_decision["execution_mode"] == "parallel":
        # Execute on multiple nodes
        model_names = [routing_decision["model"]] * len(scheduling_decision["nodes"])
        results = await pool.call_multiple_models(
            model_names,
            request.prompt,
            request.parameters
        )
        
        # Step 4: Merge results
        merger = get_merger_agent()
        final_result = merger.merge_results(
            results["results"],
            strategy=MergeStrategy.CONSENSUS
        )
        
        return {
            "job_id": job.job_id,
            "status": "completed",
            "routing": routing_decision,
            "scheduling": scheduling_decision,
            "result": final_result,
            "execution_mode": "parallel"
        }
    
    elif scheduling_decision["execution_mode"] == "queued":
        return {
            "job_id": job.job_id,
            "status": "queued",
            "queue_position": scheduling_decision["queue_position"],
            "message": "Job queued - no nodes available"
        }
    
    else:
        # Single node execution
        result = await pool.call_model(
            routing_decision["model"],
            request.prompt,
            request.parameters
        )
        
        return {
            "job_id": job.job_id,
            "status": "completed",
            "routing": routing_decision,
            "scheduling": scheduling_decision,
            "result": result,
            "execution_mode": scheduling_decision["execution_mode"]
        }


@router.get("/models")
async def list_available_models(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all available LLM models in the pool
    """
    pool = get_llm_pool()
    models = pool.list_available_models()
    
    return {
        "models": models,
        "total": len(models)
    }


@router.get("/nodes")
async def list_gpu_nodes(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all GPU nodes and their status
    """
    scheduler = get_job_scheduler()
    nodes = scheduler.get_available_nodes()
    
    return {
        "nodes": [
            {
                "node_id": node.node_id,
                "hostname": node.hostname,
                "vram_total_gb": node.vram_total_gb,
                "vram_used_gb": node.vram_used_gb,
                "vram_available_gb": node.vram_available_gb,
                "compute_utilization": node.compute_utilization,
                "status": node.status.value,
                "models_loaded": node.models_loaded
            }
            for node in scheduler.nodes.values()
        ],
        "available_count": len(nodes)
    }


@router.post("/nodes/status")
async def update_node_status(
    update: NodeStatusUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Update GPU node status (admin only)
    """
    scheduler = get_job_scheduler()
    
    status_enum = None
    if update.status:
        try:
            status_enum = NodeStatus[update.status.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {update.status}"
            )
    
    scheduler.update_node_status(
        update.node_id,
        vram_used_gb=update.vram_used_gb,
        compute_utilization=update.compute_utilization,
        status=status_enum
    )
    
    return {"message": "Node status updated"}


@router.get("/routing/rules")
async def get_routing_rules(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current routing rules for task classification
    """
    router_agent = get_llm_router()
    
    return {
        "routing_rules": {
            task_type.value: {
                "model": rule["model"],
                "endpoint": rule["endpoint"],
                "priority": rule["priority"],
                "description": rule["description"]
            }
            for task_type, rule in router_agent.routing_rules.items()
        }
    }


@router.post("/test-classification")
async def test_classification(
    request: LLMRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Test task classification without executing
    """
    router_agent = get_llm_router()
    task_type = router_agent.classify_request(request.dict())
    routing_decision = router_agent.route_request(request.dict())
    
    return {
        "task_type": task_type.value,
        "routing_decision": routing_decision,
        "should_parallelize": router_agent.should_parallelize(request.dict()),
        "requires_chaining": router_agent.requires_serial_chaining(request.dict())
    }

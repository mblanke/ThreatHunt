# Phase 5: Distributed LLM Routing Architecture

## Overview

Phase 5 introduces a sophisticated distributed Large Language Model (LLM) routing system that intelligently classifies tasks and routes them to specialized models across multiple GPU nodes (GB10 devices). This architecture enables efficient utilization of computational resources and optimal model selection based on task requirements.

## Architecture Components

The system consists of four containerized components that work together to provide intelligent, scalable LLM processing:

### 1. Router Agent (LLM Classifier + Policy Engine)

**Module**: `app/core/llm_router.py`

The Router Agent is responsible for:
- **Request Classification**: Analyzes incoming requests to determine the task type
- **Model Selection**: Routes requests to the most appropriate specialized model
- **Policy Enforcement**: Applies routing rules based on configured policies

**Task Types & Model Routing:**

| Task Type | Model | Use Case |
|-----------|-------|----------|
| `general_reasoning` | DeepSeek | Complex analysis and reasoning |
| `multilingual` | Qwen72 / Aya | Translation and multilingual tasks |
| `structured_parsing` | Phi-4 | Structured data extraction |
| `rule_generation` | Qwen-Coder | Code and rule generation |
| `adversarial_reasoning` | LLaMA 3.1 | Threat and adversarial analysis |
| `classification` | Granite Guardian | Pure classification tasks |

**Classification Logic:**
```python
from app.core.llm_router import get_llm_router

router = get_llm_router()
routing_decision = router.route_request({
    "prompt": "Analyze this threat...",
    "task_hints": ["threat", "adversary"]
})
# Routes to LLaMA 3.1 for adversarial reasoning
```

### 2. Job Scheduler (GPU Load Balancer)

**Module**: `app/core/job_scheduler.py`

The Job Scheduler manages:
- **Node Selection**: Determines which GB10 device is available
- **Resource Monitoring**: Tracks GPU VRAM and compute utilization
- **Parallelization Decisions**: Determines if jobs should be distributed
- **Serial Chaining**: Handles multi-step reasoning workflows

**GPU Node Configuration:**

**GB10 Node 1** (`gb10-node-1:8001`)
- **Total VRAM**: 80 GB
- **Models Loaded**: DeepSeek, Qwen72
- **Primary Use**: General reasoning and multilingual tasks

**GB10 Node 2** (`gb10-node-2:8001`)
- **Total VRAM**: 80 GB
- **Models Loaded**: Phi-4, Qwen-Coder, LLaMA 3.1, Granite Guardian
- **Primary Use**: Specialized tasks (parsing, coding, classification, threat analysis)

**Scheduling Strategies:**

1. **Single Node Execution**
   - Default for simple requests
   - Selected based on lowest compute utilization
   - Requires sufficient VRAM for model

2. **Parallel Execution**
   - Distributes work across multiple nodes
   - Used for batch processing or high-priority jobs
   - Automatic load balancing

3. **Serial Chaining**
   - Multi-step dependent operations
   - Sequential execution with context passing
   - Used for complex reasoning workflows

4. **Queued Execution**
   - When all nodes are at capacity
   - Priority-based queue management
   - Automatic dispatch when resources available

**Example Usage:**
```python
from app.core.job_scheduler import get_job_scheduler, Job

scheduler = get_job_scheduler()
job = Job(
    job_id="threat_analysis_001",
    model="llama31",
    priority=1,
    estimated_vram_gb=10,
    requires_parallel=False,
    requires_chaining=False,
    payload={"prompt": "..."}
)

scheduling_decision = await scheduler.schedule_job(job)
# Returns node assignment and execution mode
```

### 3. LLM Pool (OpenAI-Compatible Endpoints)

**Module**: `app/core/llm_pool.py`

The LLM Pool provides:
- **Unified Interface**: OpenAI-compatible API for all models
- **Endpoint Management**: Tracks availability and health
- **Parallel Execution**: Simultaneous multi-model requests
- **Error Handling**: Graceful fallback on failures

**Available Endpoints:**

| Model | Endpoint | Node | Specialization |
|-------|----------|------|----------------|
| DeepSeek | `http://gb10-node-1:8001/deepseek` | Node 1 | General reasoning |
| Qwen72 | `http://gb10-node-1:8001/qwen72` | Node 1 | Multilingual |
| Phi-4 | `http://gb10-node-2:8001/phi4` | Node 2 | Structured parsing |
| Qwen-Coder | `http://gb10-node-2:8001/qwen-coder` | Node 2 | Code generation |
| LLaMA 3.1 | `http://gb10-node-2:8001/llama31` | Node 2 | Adversarial reasoning |
| Granite Guardian | `http://gb10-node-2:8001/granite-guardian` | Node 2 | Classification |

**Example Usage:**
```python
from app.core.llm_pool import get_llm_pool

pool = get_llm_pool()

# Single model call
result = await pool.call_model(
    model_name="llama31",
    prompt="Analyze this threat pattern...",
    parameters={"temperature": 0.7, "max_tokens": 2048}
)

# Multiple models in parallel
results = await pool.call_multiple_models(
    model_names=["llama31", "deepseek"],
    prompt="Complex threat analysis...",
    parameters={"temperature": 0.7}
)
```

### 4. Merger Agent (Result Synthesizer)

**Module**: `app/core/merger_agent.py`

The Merger Agent provides:
- **Result Combination**: Intelligently merges outputs from multiple models
- **Strategy Selection**: Multiple merging strategies for different use cases
- **Quality Assessment**: Evaluates and ranks responses
- **Consensus Building**: Determines agreement across models

**Merging Strategies:**

1. **Consensus** (`MergeStrategy.CONSENSUS`)
   - Takes majority vote for classifications
   - Selects most common response
   - Best for: Classification tasks, binary decisions

2. **Weighted** (`MergeStrategy.WEIGHTED`)
   - Weights results by confidence scores
   - Selects highest confidence response
   - Best for: When models provide confidence scores

3. **Concatenate** (`MergeStrategy.CONCATENATE`)
   - Combines all responses sequentially
   - Preserves all information
   - Best for: Comprehensive analysis requiring multiple perspectives

4. **Best Quality** (`MergeStrategy.BEST_QUALITY`)
   - Selects highest quality response based on metrics
   - Considers length, completeness, formatting
   - Best for: Text generation, detailed explanations

5. **Ensemble** (`MergeStrategy.ENSEMBLE`)
   - Synthesizes insights from all models
   - Creates comprehensive summary
   - Best for: Complex analysis requiring synthesis

**Example Usage:**
```python
from app.core.merger_agent import get_merger_agent, MergeStrategy

merger = get_merger_agent()

# Multiple model results
results = [
    {"model": "llama31", "response": "...", "confidence": 0.9},
    {"model": "deepseek", "response": "...", "confidence": 0.85}
]

# Merge with consensus strategy
merged = merger.merge_results(results, strategy=MergeStrategy.CONSENSUS)
```

## API Endpoints

### Process LLM Request
```http
POST /api/llm/process
```

Processes a request through the complete routing system.

**Request Body:**
```json
{
  "prompt": "Analyze this threat pattern for indicators of compromise",
  "task_hints": ["threat", "adversary"],
  "requires_parallel": false,
  "requires_chaining": false,
  "parameters": {
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

**Response:**
```json
{
  "job_id": "job_123_4567",
  "status": "completed",
  "routing": {
    "task_type": "adversarial_reasoning",
    "model": "llama31",
    "endpoint": "llama31",
    "priority": 1
  },
  "scheduling": {
    "job_id": "job_123_4567",
    "execution_mode": "single",
    "node": {
      "node_id": "gb10-node-2",
      "endpoint": "http://gb10-node-2:8001/llama31"
    }
  },
  "result": {
    "choices": [...]
  },
  "execution_mode": "single"
}
```

### List Available Models
```http
GET /api/llm/models
```

Returns all available LLM models in the pool.

**Response:**
```json
{
  "models": [
    {
      "model_name": "deepseek",
      "node_id": "gb10-node-1",
      "endpoint_url": "http://gb10-node-1:8001/deepseek",
      "is_available": true
    },
    ...
  ],
  "total": 6
}
```

### List GPU Nodes
```http
GET /api/llm/nodes
```

Returns status of all GPU nodes.

**Response:**
```json
{
  "nodes": [
    {
      "node_id": "gb10-node-1",
      "hostname": "gb10-node-1",
      "vram_total_gb": 80,
      "vram_used_gb": 25,
      "vram_available_gb": 55,
      "compute_utilization": 0.35,
      "status": "available",
      "models_loaded": ["deepseek", "qwen72"]
    },
    ...
  ],
  "available_count": 2
}
```

### Update Node Status (Admin Only)
```http
POST /api/llm/nodes/status
```

Updates GPU node status metrics.

**Request Body:**
```json
{
  "node_id": "gb10-node-1",
  "vram_used_gb": 30,
  "compute_utilization": 0.45,
  "status": "available"
}
```

### Get Routing Rules
```http
GET /api/llm/routing/rules
```

Returns current routing rules for task classification.

### Test Classification
```http
POST /api/llm/test-classification
```

Tests task classification without executing the request.

## Usage Examples

### Example 1: Threat Analysis with Adversarial Reasoning

```python
import httpx

async def analyze_threat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/llm/process",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": "Analyze this suspicious PowerShell script for malicious intent...",
                "task_hints": ["threat", "adversary", "malicious"],
                "parameters": {"temperature": 0.3}  # Lower temp for analysis
            }
        )
        result = response.json()
        print(f"Model used: {result['routing']['model']}")
        print(f"Analysis: {result['result']}")
```

### Example 2: Code Generation for YARA Rules

```python
async def generate_yara_rule():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/llm/process",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": "Generate a YARA rule to detect this malware family...",
                "task_hints": ["code", "rule", "generate"],
                "parameters": {"temperature": 0.5}
            }
        )
        result = response.json()
        # Routes to Qwen-Coder automatically
        print(f"Generated rule: {result['result']}")
```

### Example 3: Parallel Processing for Batch Analysis

```python
async def batch_analysis():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/llm/process",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": "Analyze these 50 log entries for anomalies...",
                "task_hints": ["classify", "anomaly"],
                "requires_parallel": True,
                "batch_size": 50
            }
        )
        result = response.json()
        # Automatically parallelized across both nodes
        print(f"Execution mode: {result['execution_mode']}")
```

### Example 4: Serial Chaining for Multi-Step Analysis

```python
async def chained_analysis():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/llm/process",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "prompt": "First extract IOCs, then classify threats, finally generate response plan",
                "task_hints": ["parse", "classify", "generate"],
                "requires_chaining": True,
                "operations": ["extract", "classify", "generate"]
            }
        )
        result = response.json()
        # Executed serially with context passing
        print(f"Chain result: {result['result']}")
```

## Integration with Existing Features

### Integration with Threat Intelligence (Phase 4)

The distributed LLM system enhances threat intelligence analysis:

```python
from app.core.threat_intel import get_threat_analyzer
from app.core.llm_pool import get_llm_pool

async def enhanced_threat_analysis(host_id):
    # Step 1: Traditional ML analysis
    analyzer = get_threat_analyzer()
    ml_result = analyzer.analyze_host(host_data)
    
    # Step 2: LLM-based deep analysis if score is concerning
    if ml_result["score"] > 0.6:
        pool = get_llm_pool()
        llm_result = await pool.call_model(
            "llama31",
            f"Deep analysis of threat with score {ml_result['score']}: {host_data}",
            {"temperature": 0.3}
        )
        
        return {
            "ml_analysis": ml_result,
            "llm_analysis": llm_result,
            "recommendation": "quarantine" if ml_result["score"] > 0.8 else "investigate"
        }
```

### Integration with Automated Playbooks (Phase 4)

LLM routing can trigger automated responses:

```python
from app.core.playbook_engine import get_playbook_engine

async def llm_triggered_playbook(threat_analysis):
    if threat_analysis["result"]["severity"] == "critical":
        engine = get_playbook_engine()
        await engine.execute_playbook(
            playbook={
                "actions": [
                    {"type": "isolate_host", "params": {"host_id": host_id}},
                    {"type": "send_notification", "params": {"message": "Critical threat detected"}},
                    {"type": "create_case", "params": {"title": "Auto-generated from LLM analysis"}}
                ]
            },
            context=threat_analysis
        )
```

## Deployment

### Docker Compose Configuration

Add LLM node services to `docker-compose.yml`:

```yaml
services:
  # Existing services...
  
  llm-node-1:
    image: vllm/vllm-openai:latest
    ports:
      - "8001:8001"
    environment:
      - NVIDIA_VISIBLE_DEVICES=0,1
    volumes:
      - ./models:/models
    command: >
      --model /models/deepseek
      --host 0.0.0.0
      --port 8001
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]
  
  llm-node-2:
    image: vllm/vllm-openai:latest
    ports:
      - "8002:8001"
    environment:
      - NVIDIA_VISIBLE_DEVICES=2,3
    volumes:
      - ./models:/models
    command: >
      --model /models/phi4
      --host 0.0.0.0
      --port 8001
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]
```

### Environment Variables

Add to `.env`:

```bash
# Phase 5: LLM Configuration
LLM_NODE_1_URL=http://gb10-node-1:8001
LLM_NODE_2_URL=http://gb10-node-2:8001
LLM_ENABLE_PARALLEL=true
LLM_MAX_PARALLEL_JOBS=4
LLM_DEFAULT_TIMEOUT=60
```

## Performance Considerations

### Resource Allocation

- **DeepSeek**: ~40GB VRAM (high priority)
- **Qwen72**: ~35GB VRAM (medium priority)
- **Phi-4**: ~15GB VRAM (fast inference)
- **Qwen-Coder**: ~20GB VRAM
- **LLaMA 3.1**: ~25GB VRAM
- **Granite Guardian**: ~10GB VRAM (classification only)

### Load Balancing

The scheduler automatically:
- Monitors VRAM usage on each node
- Tracks compute utilization (0.0-1.0)
- Routes requests to less loaded nodes
- Queues jobs when capacity is reached

### Optimization Tips

1. **Use task_hints**: Helps router select optimal model faster
2. **Enable parallelization**: For batch jobs over 10 items
3. **Monitor node status**: Use `/api/llm/nodes` endpoint
4. **Set appropriate temperatures**: Lower (0.3) for analysis, higher (0.7) for generation
5. **Leverage caching**: Repeated prompts hit cache layer

## Security

- All LLM endpoints require authentication
- Admin-only node status updates
- Tenant isolation maintained
- Audit logging for all LLM requests
- Rate limiting per user/tenant

## Future Enhancements

- [ ] Model fine-tuning pipeline
- [ ] Custom model deployment
- [ ] Advanced caching layer
- [ ] Multi-region deployment
- [ ] Real-time model swapping
- [ ] Automated model selection via meta-learning
- [ ] Integration with external model APIs (OpenAI, Anthropic)
- [ ] Cost tracking and optimization

## Conclusion

Phase 5 provides a production-ready distributed LLM routing architecture that intelligently manages computational resources while optimizing for task-specific model selection. The system integrates seamlessly with existing threat hunting capabilities to provide enhanced analysis and automated decision-making.

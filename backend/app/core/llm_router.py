"""
LLM Router Agent

Routes requests to appropriate LLM models based on task classification.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import httpx


class TaskType(Enum):
    """Types of tasks for LLM routing"""
    GENERAL_REASONING = "general_reasoning"  # DeepSeek
    MULTILINGUAL = "multilingual"  # Qwen / Aya
    STRUCTURED_PARSING = "structured_parsing"  # Phi-4
    RULE_GENERATION = "rule_generation"  # Qwen-Coder
    ADVERSARIAL_REASONING = "adversarial_reasoning"  # LLaMA 3.1
    CLASSIFICATION = "classification"  # Granite Guardian


class LLMRouterAgent:
    """
    Router Agent - Interprets incoming requests and routes to appropriate LLM
    
    This agent classifies the incoming request and determines which specialized
    LLM should handle it based on the task type.
    """
    
    def __init__(self, policy_config: Optional[Dict[str, Any]] = None):
        """
        Initialize router agent
        
        Args:
            policy_config: Optional routing policy configuration
        """
        self.policy_config = policy_config or {}
        self.routing_rules = self._initialize_routing_rules()
    
    def _initialize_routing_rules(self) -> Dict[TaskType, Dict[str, Any]]:
        """Initialize routing rules for each task type"""
        return {
            TaskType.GENERAL_REASONING: {
                "model": "deepseek",
                "endpoint": "deepseek",
                "priority": 1,
                "description": "General reasoning and complex analysis"
            },
            TaskType.MULTILINGUAL: {
                "model": "qwen72",
                "endpoint": "qwen72",
                "priority": 2,
                "description": "Multilingual translation and analysis"
            },
            TaskType.STRUCTURED_PARSING: {
                "model": "phi4",
                "endpoint": "phi4",
                "priority": 3,
                "description": "Structured data parsing and extraction"
            },
            TaskType.RULE_GENERATION: {
                "model": "qwen-coder",
                "endpoint": "qwen-coder",
                "priority": 2,
                "description": "Code and rule generation"
            },
            TaskType.ADVERSARIAL_REASONING: {
                "model": "llama31",
                "endpoint": "llama31",
                "priority": 1,
                "description": "Adversarial threat analysis"
            },
            TaskType.CLASSIFICATION: {
                "model": "granite-guardian",
                "endpoint": "granite-guardian",
                "priority": 4,
                "description": "Pure classification tasks"
            }
        }
    
    def classify_request(self, request: Dict[str, Any]) -> TaskType:
        """
        Classify incoming request to determine task type
        
        Args:
            request: Request containing prompt and metadata
        
        Returns:
            Classified task type
        """
        prompt = request.get("prompt", "").lower()
        task_hints = request.get("task_hints", [])
        
        # Classification logic based on keywords and hints
        if any(hint in task_hints for hint in ["translate", "multilingual", "language"]):
            return TaskType.MULTILINGUAL
        
        if any(hint in task_hints for hint in ["parse", "extract", "structure"]):
            return TaskType.STRUCTURED_PARSING
        
        if any(hint in task_hints for hint in ["code", "rule", "generate", "script"]):
            return TaskType.RULE_GENERATION
        
        if any(hint in task_hints for hint in ["threat", "adversary", "attack", "malicious"]):
            return TaskType.ADVERSARIAL_REASONING
        
        if any(hint in task_hints for hint in ["classify", "categorize", "label"]):
            return TaskType.CLASSIFICATION
        
        # Default to general reasoning
        return TaskType.GENERAL_REASONING
    
    def route_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route request to appropriate LLM endpoint
        
        Args:
            request: Request to route
        
        Returns:
            Routing decision with endpoint and model info
        """
        task_type = self.classify_request(request)
        routing_rule = self.routing_rules[task_type]
        
        return {
            "task_type": task_type.value,
            "model": routing_rule["model"],
            "endpoint": routing_rule["endpoint"],
            "priority": routing_rule["priority"],
            "description": routing_rule["description"],
            "requires_parallel": request.get("requires_parallel", False),
            "requires_chaining": request.get("requires_chaining", False)
        }
    
    def should_parallelize(self, request: Dict[str, Any]) -> bool:
        """
        Determine if request should be parallelized across multiple nodes
        
        Args:
            request: Request to evaluate
        
        Returns:
            True if should be parallelized
        """
        # Large batch requests
        if request.get("batch_size", 1) > 10:
            return True
        
        # Explicit parallel flag
        if request.get("requires_parallel", False):
            return True
        
        return False
    
    def requires_serial_chaining(self, request: Dict[str, Any]) -> bool:
        """
        Determine if request requires serial reasoning (chained operations)
        
        Args:
            request: Request to evaluate
        
        Returns:
            True if requires chaining
        """
        # Complex multi-step reasoning
        if request.get("requires_chaining", False):
            return True
        
        # Multiple dependent operations
        if len(request.get("operations", [])) > 1:
            return True
        
        return False


def get_llm_router(policy_config: Optional[Dict[str, Any]] = None) -> LLMRouterAgent:
    """
    Factory function to create LLM router agent
    
    Args:
        policy_config: Optional routing policy configuration
    
    Returns:
        Configured LLMRouterAgent instance
    """
    return LLMRouterAgent(policy_config)

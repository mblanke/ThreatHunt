"""
LLM Pool Manager

Manages pool of LLM endpoints with OpenAI-compatible interface.
"""

from typing import Dict, Any, List, Optional
import httpx
from dataclasses import dataclass


@dataclass
class LLMEndpoint:
    """Represents an LLM endpoint"""
    model_name: str
    node_id: str
    base_url: str
    is_available: bool = True
    
    @property
    def endpoint_url(self) -> str:
        """Get full endpoint URL"""
        return f"{self.base_url}/{self.model_name}"


class LLMPoolManager:
    """
    Pool of LLM Endpoints
    
    Each model is exposed via an OpenAI-compatible endpoint:
    - http://gb10-node-1:8001/deepseek
    - http://gb10-node-1:8001/qwen72
    - http://gb10-node-2:8001/phi4
    - http://gb10-node-2:8001/qwen-coder
    - http://gb10-node-2:8001/llama31
    - http://gb10-node-2:8001/granite-guardian
    """
    
    def __init__(self):
        """Initialize LLM pool"""
        self.endpoints: Dict[str, LLMEndpoint] = {}
        self._initialize_endpoints()
    
    def _initialize_endpoints(self):
        """Initialize all LLM endpoints"""
        # GB10 Node 1 endpoints
        self.endpoints["deepseek"] = LLMEndpoint(
            model_name="deepseek",
            node_id="gb10-node-1",
            base_url="http://gb10-node-1:8001"
        )
        
        self.endpoints["qwen72"] = LLMEndpoint(
            model_name="qwen72",
            node_id="gb10-node-1",
            base_url="http://gb10-node-1:8001"
        )
        
        # GB10 Node 2 endpoints
        self.endpoints["phi4"] = LLMEndpoint(
            model_name="phi4",
            node_id="gb10-node-2",
            base_url="http://gb10-node-2:8001"
        )
        
        self.endpoints["qwen-coder"] = LLMEndpoint(
            model_name="qwen-coder",
            node_id="gb10-node-2",
            base_url="http://gb10-node-2:8001"
        )
        
        self.endpoints["llama31"] = LLMEndpoint(
            model_name="llama31",
            node_id="gb10-node-2",
            base_url="http://gb10-node-2:8001"
        )
        
        self.endpoints["granite-guardian"] = LLMEndpoint(
            model_name="granite-guardian",
            node_id="gb10-node-2",
            base_url="http://gb10-node-2:8001"
        )
    
    def get_endpoint(self, model_name: str) -> Optional[LLMEndpoint]:
        """
        Get endpoint for a specific model
        
        Args:
            model_name: Name of the model
        
        Returns:
            LLMEndpoint or None if not found
        """
        return self.endpoints.get(model_name)
    
    async def call_model(
        self,
        model_name: str,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call an LLM model via its endpoint
        
        Args:
            model_name: Name of the model
            prompt: Input prompt
            parameters: Optional model parameters
        
        Returns:
            Model response
        """
        endpoint = self.get_endpoint(model_name)
        
        if not endpoint:
            return {
                "error": f"Model {model_name} not found",
                "available_models": list(self.endpoints.keys())
            }
        
        if not endpoint.is_available:
            return {
                "error": f"Endpoint {model_name} is currently unavailable",
                "status": "offline"
            }
        
        # Prepare OpenAI-compatible request
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": parameters.get("temperature", 0.7) if parameters else 0.7,
            "max_tokens": parameters.get("max_tokens", 2048) if parameters else 2048
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{endpoint.endpoint_url}/v1/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            return {
                "error": f"Failed to call {model_name}",
                "details": str(e),
                "endpoint": endpoint.endpoint_url
            }
    
    async def call_multiple_models(
        self,
        model_names: List[str],
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call multiple models in parallel
        
        Args:
            model_names: List of model names
            prompt: Input prompt
            parameters: Optional model parameters
        
        Returns:
            Combined results from all models
        """
        import asyncio
        
        tasks = [
            self.call_model(model, prompt, parameters)
            for model in model_names
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "models": model_names,
            "results": [
                {"model": model, "response": result}
                for model, result in zip(model_names, results)
            ]
        }
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """
        List all available models
        
        Returns:
            List of model information
        """
        return [
            {
                "model_name": endpoint.model_name,
                "node_id": endpoint.node_id,
                "endpoint_url": endpoint.endpoint_url,
                "is_available": endpoint.is_available
            }
            for endpoint in self.endpoints.values()
        ]


def get_llm_pool() -> LLMPoolManager:
    """
    Factory function to create LLM pool manager
    
    Returns:
        Configured LLMPoolManager instance
    """
    return LLMPoolManager()

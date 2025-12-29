"""Pluggable LLM provider interface for analyst-assist agents.

Supports three provider types:
- Local: On-device or on-prem models
- Networked: Shared internal inference services
- Online: External hosted APIs
"""

import os
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate a response from the LLM.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider backend is available."""
        pass


class LocalProvider(LLMProvider):
    """Local LLM provider (on-device or on-prem models)."""

    def __init__(self, model_path: Optional[str] = None):
        """Initialize local provider.
        
        Args:
            model_path: Path to local model. If None, uses THREAT_HUNT_LOCAL_MODEL_PATH env var.
        """
        self.model_path = model_path or os.getenv("THREAT_HUNT_LOCAL_MODEL_PATH")
        self.model = None

    def is_available(self) -> bool:
        """Check if local model is available."""
        if not self.model_path:
            return False
        # In production, would verify model file exists and can be loaded
        return os.path.exists(str(self.model_path))

    async def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate response using local model.
        
        Note: This is a placeholder. In production, integrate with:
        - llama-cpp-python for GGML models
        - Ollama API
        - vLLM
        - Other local inference engines
        """
        if not self.is_available():
            raise RuntimeError("Local model not available")

        # Placeholder implementation
        return f"[Local model response to: {prompt[:50]}...]"


class NetworkedProvider(LLMProvider):
    """Networked LLM provider (shared internal inference services)."""

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "default",
    ):
        """Initialize networked provider.
        
        Args:
            api_endpoint: URL to inference service. Defaults to env var THREAT_HUNT_NETWORKED_ENDPOINT.
            api_key: API key for service. Defaults to env var THREAT_HUNT_NETWORKED_KEY.
            model_name: Model name/ID on the service.
        """
        self.api_endpoint = api_endpoint or os.getenv("THREAT_HUNT_NETWORKED_ENDPOINT")
        self.api_key = api_key or os.getenv("THREAT_HUNT_NETWORKED_KEY")
        self.model_name = model_name

    def is_available(self) -> bool:
        """Check if networked service is available."""
        return bool(self.api_endpoint)

    async def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate response using networked service.
        
        Note: This is a placeholder. In production, integrate with:
        - Internal inference service API
        - LLM inference container cluster
        - Enterprise inference gateway
        """
        if not self.is_available():
            raise RuntimeError("Networked service not available")

        # Placeholder implementation
        return f"[Networked response from {self.model_name}: {prompt[:50]}...]"


class OnlineProvider(LLMProvider):
    """Online LLM provider (external hosted APIs)."""

    def __init__(
        self,
        api_provider: str = "openai",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """Initialize online provider.
        
        Args:
            api_provider: Provider name (openai, anthropic, google, etc.)
            api_key: API key. Defaults to env var THREAT_HUNT_ONLINE_API_KEY.
            model_name: Model name. Defaults to env var THREAT_HUNT_ONLINE_MODEL.
        """
        self.api_provider = api_provider
        self.api_key = api_key or os.getenv("THREAT_HUNT_ONLINE_API_KEY")
        self.model_name = model_name or os.getenv(
            "THREAT_HUNT_ONLINE_MODEL", f"{api_provider}-default"
        )

    def is_available(self) -> bool:
        """Check if online API is available."""
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate response using online API.
        
        Note: This is a placeholder. In production, integrate with:
        - OpenAI API (GPT-3.5, GPT-4, etc.)
        - Anthropic Claude API
        - Google Gemini API
        - Other hosted LLM services
        """
        if not self.is_available():
            raise RuntimeError("Online API not available or API key not set")

        # Placeholder implementation
        return f"[Online {self.api_provider} response: {prompt[:50]}...]"


def get_provider(provider_type: str = "auto") -> LLMProvider:
    """Get an LLM provider based on configuration.
    
    Args:
        provider_type: Type of provider to use: 'local', 'networked', 'online', or 'auto'.
                      'auto' attempts to use the first available provider in order:
                      local -> networked -> online.
    
    Returns:
        Configured LLM provider instance.
        
    Raises:
        RuntimeError: If no provider is available.
    """
    # Explicit provider selection
    if provider_type == "local":
        provider = LocalProvider()
    elif provider_type == "networked":
        provider = NetworkedProvider()
    elif provider_type == "online":
        provider = OnlineProvider()
    elif provider_type == "auto":
        # Try providers in order of preference
        for Provider in [LocalProvider, NetworkedProvider, OnlineProvider]:
            provider = Provider()
            if provider.is_available():
                return provider
        raise RuntimeError(
            "No LLM provider available. Configure at least one of: "
            "THREAT_HUNT_LOCAL_MODEL_PATH, THREAT_HUNT_NETWORKED_ENDPOINT, "
            "or THREAT_HUNT_ONLINE_API_KEY"
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

    if not provider.is_available():
        raise RuntimeError(f"{provider_type} provider not available")

    return provider

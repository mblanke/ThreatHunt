"""Configuration for agent settings."""

import os
from typing import Literal


class AgentConfig:
    """Configuration for analyst-assist agents."""

    # Provider type: 'local', 'networked', 'online', or 'auto'
    PROVIDER_TYPE: Literal["local", "networked", "online", "auto"] = os.getenv(
        "THREAT_HUNT_AGENT_PROVIDER", "auto"
    )

    # Local provider settings
    LOCAL_MODEL_PATH: str | None = os.getenv("THREAT_HUNT_LOCAL_MODEL_PATH")

    # Networked provider settings
    NETWORKED_ENDPOINT: str | None = os.getenv("THREAT_HUNT_NETWORKED_ENDPOINT")
    NETWORKED_API_KEY: str | None = os.getenv("THREAT_HUNT_NETWORKED_KEY")

    # Online provider settings
    ONLINE_API_PROVIDER: str = os.getenv("THREAT_HUNT_ONLINE_PROVIDER", "openai")
    ONLINE_API_KEY: str | None = os.getenv("THREAT_HUNT_ONLINE_API_KEY")
    ONLINE_MODEL: str | None = os.getenv("THREAT_HUNT_ONLINE_MODEL")

    # Agent behavior settings
    MAX_RESPONSE_TOKENS: int = int(
        os.getenv("THREAT_HUNT_AGENT_MAX_TOKENS", "1024")
    )
    ENABLE_REASONING: bool = os.getenv(
        "THREAT_HUNT_AGENT_REASONING", "true"
    ).lower() in ("true", "1", "yes")
    CONVERSATION_HISTORY_LENGTH: int = int(
        os.getenv("THREAT_HUNT_AGENT_HISTORY_LENGTH", "10")
    )

    # Privacy settings
    FILTER_SENSITIVE_DATA: bool = os.getenv(
        "THREAT_HUNT_AGENT_FILTER_SENSITIVE", "true"
    ).lower() in ("true", "1", "yes")

    @classmethod
    def is_agent_enabled(cls) -> bool:
        """Check if agent is enabled and properly configured."""
        # Agent is disabled if no provider can be used
        if cls.PROVIDER_TYPE == "auto":
            return bool(
                cls.LOCAL_MODEL_PATH
                or cls.NETWORKED_ENDPOINT
                or cls.ONLINE_API_KEY
            )
        elif cls.PROVIDER_TYPE == "local":
            return bool(cls.LOCAL_MODEL_PATH)
        elif cls.PROVIDER_TYPE == "networked":
            return bool(cls.NETWORKED_ENDPOINT)
        elif cls.PROVIDER_TYPE == "online":
            return bool(cls.ONLINE_API_KEY)
        return False

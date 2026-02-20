"""Application configuration — single source of truth for all settings.

Loads from environment variables with sensible defaults for local dev.
"""

import os
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import Field


class AppConfig(BaseSettings):
    """Central configuration for the entire ThreatHunt application."""

    # ── General ────────────────────────────────────────────────────────
    APP_NAME: str = "ThreatHunt"
    APP_VERSION: str = "0.4.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./threathunt.db",
        description="Async SQLAlchemy database URL. "
        "Use sqlite+aiosqlite:///./threathunt.db for local dev, "
        "postgresql+asyncpg://user:pass@host/db for production.",
    )

    # ── CORS ───────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins",
    )

    # ── File uploads ───────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = Field(default=500, description="Max CSV upload in MB")
    UPLOAD_DIR: str = Field(default="./uploads", description="Directory for uploaded files")

    # ── LLM Cluster — Wile & Roadrunner ────────────────────────────────
    OPENWEBUI_URL: str = Field(
        default="https://ai.guapo613.beer",
        description="Open WebUI cluster endpoint (OpenAI-compatible API)",
    )
    OPENWEBUI_API_KEY: str = Field(
        default="",
        description="API key for Open WebUI (if required)",
    )
    WILE_HOST: str = Field(
        default="100.110.190.12",
        description="Tailscale IP for Wile (heavy models)",
    )
    WILE_OLLAMA_PORT: int = Field(default=11434, description="Ollama port on Wile")
    ROADRUNNER_HOST: str = Field(
        default="100.110.190.11",
        description="Tailscale IP for Roadrunner (fast models + vision)",
    )
    ROADRUNNER_OLLAMA_PORT: int = Field(
        default=11434, description="Ollama port on Roadrunner"
    )

    # ── LLM Routing defaults ──────────────────────────────────────────
    DEFAULT_FAST_MODEL: str = Field(
        default="llama3.1:latest",
        description="Default model for quick chat / simple queries",
    )
    DEFAULT_HEAVY_MODEL: str = Field(
        default="llama3.1:70b-instruct-q4_K_M",
        description="Default model for deep analysis / debate",
    )
    DEFAULT_CODE_MODEL: str = Field(
        default="qwen2.5-coder:32b",
        description="Default model for code / script analysis",
    )
    DEFAULT_VISION_MODEL: str = Field(
        default="llama3.2-vision:11b",
        description="Default model for image / screenshot analysis",
    )
    DEFAULT_EMBEDDING_MODEL: str = Field(
        default="bge-m3:latest",
        description="Default embedding model",
    )

    # ── Agent behaviour ───────────────────────────────────────────────
    AGENT_MAX_TOKENS: int = Field(default=2048, description="Max tokens per agent response")
    AGENT_TEMPERATURE: float = Field(default=0.3, description="LLM temperature for guidance")
    AGENT_HISTORY_LENGTH: int = Field(default=10, description="Messages to keep in context")
    FILTER_SENSITIVE_DATA: bool = Field(default=True, description="Redact sensitive patterns")

    # ── Enrichment API keys ───────────────────────────────────────────
    VIRUSTOTAL_API_KEY: str = Field(default="", description="VirusTotal API key")
    ABUSEIPDB_API_KEY: str = Field(default="", description="AbuseIPDB API key")
    SHODAN_API_KEY: str = Field(default="", description="Shodan API key")

    # ── Auth ──────────────────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET",
        description="Secret for JWT signing",
    )
    JWT_ACCESS_TOKEN_MINUTES: int = Field(default=60, description="Access token lifetime")
    JWT_REFRESH_TOKEN_DAYS: int = Field(default=7, description="Refresh token lifetime")

    model_config = {"env_prefix": "TH_", "env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def wile_url(self) -> str:
        return f"http://{self.WILE_HOST}:{self.WILE_OLLAMA_PORT}"

    @property
    def roadrunner_url(self) -> str:
        return f"http://{self.ROADRUNNER_HOST}:{self.ROADRUNNER_OLLAMA_PORT}"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = AppConfig()

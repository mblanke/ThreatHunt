"""Application configuration - single source of truth for all settings.

Loads from environment variables with sensible defaults for local dev.
"""

import os
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import Field


class AppConfig(BaseSettings):
    """Central configuration for the entire ThreatHunt application."""

    # -- General --------------------------------------------------------
    APP_NAME: str = "ThreatHunt"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # -- Database -------------------------------------------------------
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./threathunt.db",
        description="Async SQLAlchemy database URL. "
        "Use sqlite+aiosqlite:///./threathunt.db for local dev, "
        "postgresql+asyncpg://user:pass@host/db for production.",
    )

    # -- CORS -----------------------------------------------------------
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins",
    )

    # -- File uploads ---------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = Field(default=500, description="Max CSV upload in MB")
    UPLOAD_DIR: str = Field(default="./uploads", description="Directory for uploaded files")

    # -- LLM Cluster - Wile & Roadrunner --------------------------------
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

    # -- LLM Routing defaults ------------------------------------------
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

    # -- Agent behaviour ------------------------------------------------
    AGENT_MAX_TOKENS: int = Field(default=2048, description="Max tokens per agent response")
    AGENT_TEMPERATURE: float = Field(default=0.3, description="LLM temperature for guidance")
    AGENT_HISTORY_LENGTH: int = Field(default=10, description="Messages to keep in context")
    FILTER_SENSITIVE_DATA: bool = Field(default=True, description="Redact sensitive patterns")

    # -- Enrichment API keys --------------------------------------------
    VIRUSTOTAL_API_KEY: str = Field(default="", description="VirusTotal API key")
    ABUSEIPDB_API_KEY: str = Field(default="", description="AbuseIPDB API key")
    SHODAN_API_KEY: str = Field(default="", description="Shodan API key")

    # -- Auth -----------------------------------------------------------
    JWT_SECRET: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET",
        description="Secret for JWT signing",
    )
    JWT_ACCESS_TOKEN_MINUTES: int = Field(default=60, description="Access token lifetime")
    JWT_REFRESH_TOKEN_DAYS: int = Field(default=7, description="Refresh token lifetime")

    # -- Triage settings ------------------------------------------------
    TRIAGE_BATCH_SIZE: int = Field(default=25, description="Rows per triage LLM batch")
    TRIAGE_MAX_SUSPICIOUS_ROWS: int = Field(
        default=200, description="Stop triage after this many suspicious rows"
    )
    TRIAGE_ESCALATION_THRESHOLD: float = Field(
        default=5.0, description="Risk score threshold for escalation counting"
    )

    # -- Host profiler settings -----------------------------------------
    HOST_PROFILE_CONCURRENCY: int = Field(
        default=3, description="Max concurrent host profile LLM calls"
    )

    # -- Scanner settings -----------------------------------------------
    SCANNER_BATCH_SIZE: int = Field(default=500, description="Rows per scanner batch")
    SCANNER_MAX_ROWS_PER_SCAN: int = Field(
        default=120000,
        description="Global row budget for a single AUP scan request (0 = unlimited)",
    )

    # -- Job queue settings ----------------------------------------------
    JOB_QUEUE_MAX_BACKLOG: int = Field(
        default=2000, description="Soft cap for queued background jobs"
    )
    JOB_QUEUE_RETAIN_COMPLETED: int = Field(
        default=3000, description="Maximum completed/failed jobs to retain in memory"
    )
    JOB_QUEUE_CLEANUP_INTERVAL_SECONDS: int = Field(
        default=60, description="How often to run in-memory job cleanup"
    )
    JOB_QUEUE_CLEANUP_MAX_AGE_SECONDS: int = Field(
        default=3600, description="Age threshold for in-memory completed job cleanup"
    )

    # -- Startup throttling ------------------------------------------------
    STARTUP_WARMUP_MAX_HUNTS: int = Field(
        default=5, description="Max hunts to warm inventory cache for at startup"
    )
    STARTUP_REPROCESS_MAX_DATASETS: int = Field(
        default=25, description="Max unprocessed datasets to enqueue at startup"
    )
    STARTUP_RECONCILE_STALE_TASKS: bool = Field(
        default=True,
        description="Mark stale queued/running processing tasks as failed on startup",
    )

    # -- Network API scale guards -----------------------------------------
    NETWORK_SUBGRAPH_MAX_HOSTS: int = Field(
        default=400, description="Hard cap for hosts returned by network subgraph endpoint"
    )
    NETWORK_SUBGRAPH_MAX_EDGES: int = Field(
        default=3000, description="Hard cap for edges returned by network subgraph endpoint"
    )
    NETWORK_INVENTORY_MAX_ROWS_PER_DATASET: int = Field(
        default=5000,
        description="Row budget per dataset when building host inventory (0 = unlimited)",
    )
    NETWORK_INVENTORY_MAX_TOTAL_ROWS: int = Field(
        default=120000,
        description="Global row budget across all datasets for host inventory build (0 = unlimited)",
    )
    NETWORK_INVENTORY_MAX_CONNECTIONS: int = Field(
        default=120000,
        description="Max unique connection tuples retained during host inventory build",
    )

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


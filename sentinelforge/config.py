from pathlib import Path
from typing import List, Optional
import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_SERVER_NOOP_TELEMETRY"] = "1"

from pydantic import Field
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    """Application settings and configuration with environment overrides."""

    app_name: str = "SentinelForge"
    app_version: str = "0.1.0"
    app_mode: str = Field(default_factory=lambda: os.getenv("APP_MODE", "local"))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    allowed_origins: List[str] = ["*"]

    workspace_root: Path = Field(
        default_factory=lambda: Path(os.getenv("WORKSPACE_ROOT", ".sentinelforge/workspace")).resolve()
    )
    chroma_persist_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CHROMA_PERSIST_DIR", ".sentinelforge/chroma_db")).resolve()
    )

    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
    chunk_size: int = Field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500")))
    chunk_overlap: int = Field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "50")))

    sandbox_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "10")))
    sandbox_max_memory_mb: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_MAX_MEMORY_MB", "256")))
    sandbox_max_output_bytes: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_MAX_OUTPUT_BYTES", "51200")))
    sandbox_allow_network: bool = Field(default_factory=lambda: os.getenv("SANDBOX_ALLOW_NETWORK", "false").lower() == "true")

    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"))
    groq_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", None))
    groq_model: str = Field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))

    def ensure_directories(self) -> None:
        """Create necessary workspace and data directories if they do not exist."""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()


"""Application settings.

Every value can be overridden with an ``STAI_``-prefixed environment variable or
a ``.env`` file at the project root (see ``.env.example``). Model names are
env-configurable on purpose: the demo may run on unknown cloud hardware, so
swapping e.g. the guardrail classifier for a bigger model is one env var, no
code change.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STAI_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Ollama models ---
    agent_model: str = "llama3.1:8b"          # must support native tool calling
    # Few-shot classifier. Keep separately configurable for demo hardware.
    # scored 14/15 on the topic battery where llama3.2:1b scored 8/15
    # (over-blocked benefits jargon); set STAI_GUARDRAIL_MODEL=llama3.2:1b
    # if latency matters more than accuracy on the demo hardware.
    guardrail_model: str = "qwen2.5:3b-instruct"
    embed_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    agent_temperature: float = 0.0
    agent_seed: int = 20260810

    # --- paths ---
    chroma_dir: Path = _DATA / "chroma"
    db_path: Path = _DATA / "stai.db"

    # --- RAG ---
    retriever_k: int = 4

    # --- privacy-safe external calendar ---
    nager_enabled: bool = True
    nager_timeout_seconds: float = 3.0

    # --- local certificate validation ---
    certificate_max_bytes: int = 10 * 1024 * 1024
    certificate_max_pdf_pages: int = 3
    certificate_max_pixels: int = 25_000_000
    certificate_timeout_seconds: int = 30
    certificate_ocr_confidence: float = 0.80

    # Browser origins allowed to call the explicitly demo-only REST API.
    cors_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]

    # --- observability (see src/stai/observability.py) ---
    obs_log_path: Path = _DATA / "observability.jsonl"

    # --- log shipping to a remote MLflow relay (see src/stai/log_shipper.py) ---
    # Unset by default: shipping is a no-op until a relay URL is configured.
    log_server_url: str | None = None
    log_shared_secret: SecretStr | None = None
    log_ship_interval_seconds: int = 300


settings = Settings()

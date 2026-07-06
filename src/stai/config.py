"""Application settings.

Every value can be overridden with an ``STAI_``-prefixed environment variable or
a ``.env`` file at the project root (see ``.env.example``). Model names are
env-configurable on purpose: the demo may run on unknown cloud hardware, so
swapping e.g. the guardrail classifier for a bigger model is one env var, no
code change.
"""

from __future__ import annotations

from pathlib import Path

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
    # Few-shot classifier for input guardrail + pulse sentiment. qwen2.5:3b
    # scored 14/15 on the topic battery where llama3.2:1b scored 8/15
    # (over-blocked benefits jargon); set STAI_GUARDRAIL_MODEL=llama3.2:1b
    # if latency matters more than accuracy on the demo hardware.
    guardrail_model: str = "qwen2.5:3b-instruct"
    embed_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    agent_temperature: float = 0.2

    # --- paths ---
    hr_docs_dir: Path = _DATA / "hr_docs"
    chroma_dir: Path = _DATA / "chroma"
    db_path: Path = _DATA / "stai.db"
    org_file: Path = _DATA / "org.json"
    employees_file: Path = _DATA / "employees.json"
    plans_file: Path = _DATA / "plans.json"

    # --- RAG ---
    collection_name: str = "stai_hr_docs"
    chunk_size: int = 800
    chunk_overlap: int = 100
    retriever_k: int = 4

    # --- pulse check-ins ---
    pulse_cadence_days: int = 7


settings = Settings()

"""Single hardware-configurable construction seam for local Ollama clients."""

from __future__ import annotations

from typing import Any

from stai.config import settings


def build_chat_model(
    *,
    model: str,
    temperature: float = 0,
    json_mode: bool = False,
    seed: int | None = None,
    top_k: int | None = None,
    **model_kwargs: Any,
):
    """Build a local chat model under the configured hardware policy."""
    from langchain_ollama import ChatOllama

    kwargs: dict[str, Any] = {
        "model": model,
        "base_url": settings.ollama_base_url,
        "temperature": temperature,
        **model_kwargs,
    }
    if settings.ollama_num_gpu is not None:
        kwargs["num_gpu"] = settings.ollama_num_gpu
    if json_mode:
        kwargs["format"] = "json"
    if seed is not None:
        kwargs["seed"] = seed
    if top_k is not None:
        kwargs["top_k"] = top_k
    return ChatOllama(**kwargs)


def build_embeddings():
    """Build the local embedding client under the same hardware policy."""
    from langchain_ollama import OllamaEmbeddings

    kwargs: dict[str, Any] = {
        "model": settings.embed_model,
        "base_url": settings.ollama_base_url,
    }
    if settings.ollama_num_gpu is not None:
        kwargs["num_gpu"] = settings.ollama_num_gpu
    return OllamaEmbeddings(**kwargs)

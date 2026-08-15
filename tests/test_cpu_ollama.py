"""Hardware-configurable Ollama construction contracts."""

from __future__ import annotations


def test_all_ollama_clients_honor_explicit_cpu_only_configuration(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeChatOllama:
        def __init__(self, **kwargs):
            calls.append(("chat", kwargs))

    class FakeOllamaEmbeddings:
        def __init__(self, **kwargs):
            calls.append(("embedding", kwargs))

    monkeypatch.setattr("langchain_ollama.ChatOllama", FakeChatOllama)
    monkeypatch.setattr("langchain_ollama.OllamaEmbeddings", FakeOllamaEmbeddings)
    monkeypatch.setattr("stai.config.settings.ollama_num_gpu", 0)

    from stai.ollama_runtime import build_chat_model, build_embeddings

    build_chat_model(model="test-chat", json_mode=True, seed=7)
    build_embeddings()

    assert calls
    assert {kind for kind, _ in calls} == {"chat", "embedding"}
    assert all(kwargs["num_gpu"] == 0 for _, kwargs in calls)


def test_default_runtime_policy_preserves_current_models_and_auto_acceleration() -> None:
    from stai.config import Settings

    local_settings = Settings(_env_file=None)
    assert local_settings.ollama_num_gpu is None
    assert local_settings.agent_model == "llama3.1:8b"
    assert local_settings.finalizer_model is None
    assert local_settings.judge_model == "qwen2.5:7b-instruct"


def test_local_judge_uses_the_fixed_evaluation_seed(monkeypatch) -> None:
    captured = {}

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("stai.ollama_runtime.build_chat_model", fake_builder)

    from stai.config import settings
    from stai.llm_judge import build_local_judge

    build_local_judge()
    assert captured["seed"] == settings.agent_seed
    assert captured["top_k"] == 1

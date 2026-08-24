"""
Tests for llm_client.build_client() and the LLM_PROVIDER toggle in config.py.

Follow-up flagged by QA (vault/decisions/2026-08-13-qa-ai-migration-fase1.md,
Medium finding #1): the toggle logic itself — the single most important piece
of the Ollama->gateway migration — had zero dedicated coverage. The 239
pre-existing tests only ever exercise the "ollama" branch, since LLM_PROVIDER
isn't set in the default test environment.

config.py reads os.environ at *import* time, so each case here sets the env
vars first and then reloads both config and llm_client — importing them fresh
isn't enough on its own, Python caches modules in sys.modules.
"""

import importlib

import pytest

_ENV_KEYS = (
    "LLM_PROVIDER", "NETZSCH_GATEWAY_KEY", "OLLAMA_BASE_URL", "GATEWAY_BASE_URL",
    "EXTRACTION_MODEL", "ANALYSIS_MODEL",
)


def _reload_with_env(monkeypatch, **env):
    """Set env vars, then reload config.py and llm_client.py so the
    module-level reads pick up the new values."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import config
    importlib.reload(config)
    import llm_client
    importlib.reload(llm_client)
    return llm_client, config


@pytest.fixture(autouse=True)
def _restore_clean_module_state(monkeypatch):
    """
    config.py/llm_client.py cache their env-derived values at import time, and
    importlib.reload() mutates the module objects in sys.modules in place —
    so without this, whichever test in this file ran last would leak its
    LLM_PROVIDER/model values into every other test file that does
    `from config import ...` afterward. monkeypatch only undoes the env vars,
    not the already-reloaded module state, so an explicit clean reload after
    each test (env vars guaranteed clear at that point) is required.
    """
    yield
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    import config
    importlib.reload(config)
    import llm_client
    importlib.reload(llm_client)


def test_build_client_ollama_default(monkeypatch):
    """No LLM_PROVIDER set -> defaults to ollama, no key required."""
    llm_client, config = _reload_with_env(monkeypatch)

    assert config.LLM_PROVIDER == "ollama"
    client = llm_client.build_client()
    assert str(client.base_url).rstrip("/") == config.OLLAMA_BASE_URL.rstrip("/")


def test_build_client_gateway_with_key(monkeypatch):
    """LLM_PROVIDER=gateway + key set -> gateway base_url, no error."""
    llm_client, config = _reload_with_env(
        monkeypatch, LLM_PROVIDER="gateway", NETZSCH_GATEWAY_KEY="fake-test-key"
    )

    assert config.LLM_PROVIDER == "gateway"
    client = llm_client.build_client()
    assert str(client.base_url).rstrip("/") == config.GATEWAY_BASE_URL.rstrip("/")
    assert client.api_key == "fake-test-key"


def test_build_client_gateway_without_key_raises(monkeypatch):
    """LLM_PROVIDER=gateway without a key -> fail loud, not silent fallback."""
    llm_client, config = _reload_with_env(monkeypatch, LLM_PROVIDER="gateway")

    assert config.GATEWAY_API_KEY == ""
    with pytest.raises(RuntimeError, match="NETZSCH_GATEWAY_KEY"):
        llm_client.build_client()


def test_extraction_model_resolution(monkeypatch):
    """EXTRACTION_MODEL follows the provider when not explicitly overridden."""
    _, config_ollama = _reload_with_env(monkeypatch)
    assert config_ollama.EXTRACTION_MODEL == "llama3.2:3b"

    _, config_gateway = _reload_with_env(
        monkeypatch, LLM_PROVIDER="gateway", NETZSCH_GATEWAY_KEY="fake-test-key"
    )
    assert config_gateway.EXTRACTION_MODEL == "claude-haiku-4-5"


def test_analysis_model_resolution(monkeypatch):
    """ANALYSIS_MODEL follows the provider (sonnet on gateway, same as
    EXTRACTION_MODEL on ollama) when not explicitly overridden."""
    _, config_ollama = _reload_with_env(monkeypatch)
    assert config_ollama.ANALYSIS_MODEL == config_ollama.EXTRACTION_MODEL

    _, config_gateway = _reload_with_env(
        monkeypatch, LLM_PROVIDER="gateway", NETZSCH_GATEWAY_KEY="fake-test-key"
    )
    assert config_gateway.ANALYSIS_MODEL == "claude-sonnet-5"


def test_explicit_model_env_override_wins(monkeypatch):
    """An explicit EXTRACTION_MODEL/ANALYSIS_MODEL env var beats the
    provider-based default, on either provider."""
    _, config_custom = _reload_with_env(
        monkeypatch,
        LLM_PROVIDER="gateway",
        NETZSCH_GATEWAY_KEY="fake-test-key",
        EXTRACTION_MODEL="custom-model-x",
        ANALYSIS_MODEL="custom-model-y",
    )
    assert config_custom.EXTRACTION_MODEL == "custom-model-x"
    assert config_custom.ANALYSIS_MODEL == "custom-model-y"

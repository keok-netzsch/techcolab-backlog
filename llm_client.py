"""
llm_client.py — shared OpenAI-compatible client builder.

Backend picked by LLM_PROVIDER (config.py / env var):
  - "ollama"  (default): local Ollama, no API key needed.
  - "gateway": NETZSCH LiteLLM gateway, authenticated with NETZSCH_GATEWAY_KEY
    (the same infrastructure the `claude-api` CLI entry point uses).
"""

from openai import OpenAI

from config import GATEWAY_API_KEY, GATEWAY_BASE_URL, LLM_PROVIDER, OLLAMA_BASE_URL


def build_client() -> OpenAI:
    if LLM_PROVIDER == "gateway":
        if not GATEWAY_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER=gateway but NETZSCH_GATEWAY_KEY is not set. "
                "Set it as a user environment variable, or set LLM_PROVIDER=ollama to fall back."
            )
        return OpenAI(base_url=GATEWAY_BASE_URL, api_key=GATEWAY_API_KEY)
    return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

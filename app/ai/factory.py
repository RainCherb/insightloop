"""Factory that builds the right LLM client based on settings."""

from __future__ import annotations

from functools import lru_cache

from app.ai.anthropic_client import AnthropicClient
from app.ai.base import LLMClient, LLMError
from app.ai.mock_client import MockClient
from app.ai.ollama_client import OllamaClient
from app.ai.openai_client import OpenAIClient
from app.config import Settings, get_settings


def build_llm_client(settings: Settings | None = None) -> LLMClient:
    """Construct the LLM client configured by `LLM_PROVIDER`."""
    cfg = settings or get_settings()
    name = cfg.llm_provider.lower()

    if name == "openai":
        if not cfg.openai_api_key:
            raise LLMError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is empty. "
                "Set the key in .env or switch to LLM_PROVIDER=mock."
            )
        return OpenAIClient(api_key=cfg.openai_api_key, model=cfg.openai_model)

    if name == "anthropic":
        if not cfg.anthropic_api_key:
            raise LLMError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty. "
                "Set the key in .env or switch to LLM_PROVIDER=mock."
            )
        return AnthropicClient(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model)

    if name == "ollama":
        return OllamaClient(base_url=cfg.ollama_base_url, model=cfg.ollama_model)

    if name == "mock":
        return MockClient()

    raise LLMError(f"Unknown LLM provider: {name!r}")


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return a cached LLM client (built once per process)."""
    return build_llm_client()

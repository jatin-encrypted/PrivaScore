"""LLM clients. Use make_client(settings) to get one; switching provider is a config change."""
from .base import LLMClient, LLMError, LLMResponse, LLMSettings, ProviderOverloaded, QuotaExhausted


def make_client(settings: LLMSettings, session=None) -> LLMClient:
    if settings.provider == "mock":
        from .mock import MockClient
        return MockClient(settings)
    if settings.provider == "gemini":
        from .gemini import GeminiClient
        return GeminiClient(settings, session)
    if settings.provider == "groq":
        from .groq import GroqClient
        return GroqClient(settings, session)
    raise ValueError(f"unknown provider {settings.provider!r}")


__all__ = ["LLMClient", "LLMError", "LLMResponse", "LLMSettings", "ProviderOverloaded", "QuotaExhausted", "make_client"]

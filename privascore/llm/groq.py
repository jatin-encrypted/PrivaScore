"""Groq via its OpenAI-compatible chat completions API, JSON object mode.

Groq serves open models (not Gemini), so answers can differ: evaluate on the gold set with the
provider you will actually demo. Model names and free-tier limits were NOT verified when this
was written; set the model in privascore.toml and run `python -m privascore.llm.smoke` once.
"""
import os

from .base import LLMClient, LLMError, LLMResponse

DEFAULT_BASE = "https://api.groq.com/openai/v1"
DEFAULT_KEY_ENV = "GROQ_API_KEY"


class GroqClient(LLMClient):
    provider = "groq"

    def __init__(self, settings, session=None):
        super().__init__(settings)
        self.session = session
        self.key_env = settings.api_key_env or DEFAULT_KEY_ENV
        self.api_key = os.environ.get(self.key_env, "")
        if not self.api_key:
            raise LLMError(f"groq: set the {self.key_env} environment variable")

    def build_request(self, system: str, user: str):
        url = f"{(self.settings.base_url or DEFAULT_BASE).rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.settings.temperature,
            "max_completion_tokens": self.settings.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        return url, headers, body

    def complete_json(self, system: str, user: str) -> LLMResponse:
        url, headers, body = self.build_request(system, user)
        data = self._post(url, headers, body, self.session)
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("groq: no choices returned")
        text = (choices[0].get("message") or {}).get("content") or ""
        if not text.strip():
            raise LLMError(f"groq: empty answer (finish_reason={choices[0].get('finish_reason')})")
        return LLMResponse(text, self.provider, self.settings.model, data.get("usage", {}), data)

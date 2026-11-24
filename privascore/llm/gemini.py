"""Google Gemini via the public REST API (generateContent), JSON output mode.

Model availability and free-tier limits change often and were NOT verified when this was
written; set the model in privascore.toml and run `python -m privascore.llm.smoke` once.
"""
import os

from .base import LLMClient, LLMError, LLMResponse

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_KEY_ENV = "GEMINI_API_KEY"


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, settings, session=None):
        super().__init__(settings)
        self.session = session
        self.key_env = settings.api_key_env or DEFAULT_KEY_ENV
        self.api_key = os.environ.get(self.key_env, "")
        if not self.api_key:
            raise LLMError(f"gemini: set the {self.key_env} environment variable")

    def build_request(self, system: str, user: str):
        url = f"{(self.settings.base_url or DEFAULT_BASE).rstrip('/')}/models/{self.settings.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.settings.temperature,
                "maxOutputTokens": self.settings.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        return url, headers, body

    def complete_json(self, system: str, user: str) -> LLMResponse:
        url, headers, body = self.build_request(system, user)
        data = self._post(url, headers, body, self.session)
        cands = data.get("candidates") or []
        if not cands:
            block = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMError(f"gemini: no candidates returned (blockReason={block})")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise LLMError(f"gemini: empty answer (finishReason={cands[0].get('finishReason')})")
        return LLMResponse(text, self.provider, self.settings.model, data.get("usageMetadata", {}), data)

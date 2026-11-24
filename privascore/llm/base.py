"""Provider-agnostic LLM interface.

Every client turns (system prompt, user prompt) into one JSON-mode text completion. Nothing
else in PrivaScore knows which provider is used, so switching Gemini <-> Groq is a config change.
No tools / function calling are ever enabled: policy text is untrusted input.
"""
import re
import time
from dataclasses import dataclass, field

import requests


class LLMError(RuntimeError):
    """A call failed after all HTTP retries, or the provider returned no usable text."""


class QuotaExhausted(LLMError):
    """Rate limit / daily quota reached. The whole run should stop (not mark flags rejected)."""


class ProviderOverloaded(QuotaExhausted):
    """Provider kept answering 503 "high demand". Stop the run (an outage is not a wrong answer),
    instead of retrying until the free daily quota is used up."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


@dataclass
class LLMSettings:
    provider: str
    model: str
    temperature: float = 0.0
    max_output_tokens: int = 1024
    timeout_seconds: float = 60.0
    min_interval_seconds: float = 0.0   # spacing between calls, to stay under free-tier rate limits
    max_http_retries: int = 3           # on 5xx / timeouts / network errors, with backoff
    rate_limit_wait_seconds: float = 65.0  # on HTTP 429: wait this long, then retry
    max_rate_limit_waits: int = 2       # still 429 after this many waits -> stop the run cleanly
    overload_waits: tuple = (20.0, 60.0)  # on HTTP 503: wait these many seconds between attempts, then stop
    api_key_env: str = ""               # env var holding the key; provider default if empty
    base_url: str = ""                  # provider default if empty


class LLMClient:
    provider = "base"

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self._last_call = 0.0

    def complete_json(self, system: str, user: str) -> LLMResponse:
        raise NotImplementedError

    # ---- helpers shared by HTTP clients

    def _throttle(self):
        wait = self.settings.min_interval_seconds - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _post(self, url: str, headers: dict, body: dict, session=None) -> dict:
        """POST with retries on rate limits / server errors. Never logs the API key.

        HTTP 429:
          - a daily quota message ("PerDay" / "per day" / "daily") -> QuotaExhausted at once
          - otherwise wait rate_limit_wait_seconds (65 s) and retry, up to max_rate_limit_waits
            times; if it is still 429 -> QuotaExhausted. The run then stops cleanly; finished
            answers are cached, so re-running later continues where it stopped.
        """
        http = session or requests
        last = None
        rl_waits = 0
        overload_waits_used = 0
        attempt = 0
        while True:
            self._throttle()
            try:
                r = http.post(url, headers=headers, json=body, timeout=self.settings.timeout_seconds)
            except requests.RequestException as e:
                last = f"network error: {e.__class__.__name__}"
            else:
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code == 429:
                    body_text = r.text or ""
                    quota = re.findall(r'"quota(?:Id|Value|Metric)"\s*:\s*"?([^",}]+)', body_text)
                    if quota:
                        last = f"HTTP 429 quota {'; '.join(dict.fromkeys(q.strip() for q in quota))}"
                    if re.search(r"per ?day|daily", body_text, re.IGNORECASE):
                        raise QuotaExhausted(f"{self.provider}: daily quota reached ({last})")
                    if rl_waits >= self.settings.max_rate_limit_waits:
                        raise QuotaExhausted(f"{self.provider}: still rate-limited after {rl_waits} waits ({last})")
                    rl_waits += 1
                    time.sleep(self.settings.rate_limit_wait_seconds)
                    continue
                if r.status_code == 503:
                    if overload_waits_used >= len(self.settings.overload_waits):
                        raise ProviderOverloaded(f"{self.provider}: still overloaded after "
                                                 f"{overload_waits_used + 1} attempts ({last})")
                    time.sleep(self.settings.overload_waits[overload_waits_used])
                    overload_waits_used += 1
                    continue
                if r.status_code not in (408, 500, 502, 504):
                    raise LLMError(f"{self.provider}: {last}")
            # network error / timeout / 408 / 5xx: exponential backoff, limited attempts
            attempt += 1
            if attempt > self.settings.max_http_retries:
                raise LLMError(f"{self.provider}: gave up after {attempt} attempts ({last})")
            time.sleep(min(2 ** (attempt - 1) * 2, 30))

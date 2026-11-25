"""Backend configuration from PRIVASCORE_* environment variables (and the repo-root .env).

GEMINI_API_KEY is deliberately NOT a field here: privascore reads it from the environment
itself, so it can never leak through a Settings repr or a /meta response.
"""
from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from privascore.flags import REPO_ROOT


def _csv(v):
    """pydantic-settings parses list fields as JSON by default; we want plain comma-separated."""
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRIVASCORE_", env_file=REPO_ROOT / ".env",
                                      extra="ignore", case_sensitive=False)

    env: Literal["dev", "prod"] = "dev"

    llm_provider: str = ""          # empty -> whatever privascore.toml says
    llm_model: str = ""

    bert: Literal["on", "off"] = "on"
    bert_required: bool = True
    bert_sanity: Literal["on", "off"] = "off"

    min_chars: int = 1000
    max_chars: int = 200_000
    max_body_bytes: int = 1_000_000
    max_concurrent: int = 1

    cors_origins: list[str] = ["http://localhost:5173"]

    llm_max_rate_limit_waits: int = 0
    llm_overload_waits: list[float] = [10.0]
    llm_max_http_retries: int = 1

    examples: Literal["on", "off"] = "on"
    examples_run: str = "gemini36_batch_v1.1"   # runs/<name>/, must match the saved metrics

    _split = field_validator("cors_origins", "llm_overload_waits", mode="before")(_csv)

    @property
    def bert_enabled(self) -> bool:
        return self.bert == "on"

"""Configuration: privascore.toml (local, not committed) or privascore.example.toml.

API keys are never stored in the config file: only the NAME of the environment variable.
"""
import os
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from .flags import REPO_ROOT
from .llm.base import LLMSettings

DEFAULT_CONFIG = REPO_ROOT / "privascore.toml"
EXAMPLE_CONFIG = REPO_ROOT / "privascore.example.toml"
DOTENV = REPO_ROOT / ".env"

_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_dotenv(path: Path = DOTENV) -> list:
    """Read KEY=value lines from .env into os.environ. Variables already set in the shell win.
    Returns the names loaded (never the values). Blank values are skipped."""
    if not Path(path).exists():
        return []
    loaded = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        else:
            val = val.split(" #", 1)[0].strip()   # allow trailing comments on unquoted values
        if val and key not in os.environ:
            os.environ[key] = val
            loaded.append(key)
    return loaded


@dataclass
class ExtractorSettings:
    max_candidates: int = 20          # top-ranked search hits sent per flag
    include_next_sentence: bool = True  # also send the sentence after each hit (exceptions, opt-outs)
    max_context_sentences: int = 40   # hard cap on sentences per prompt
    max_answer_retries: int = 1       # re-ask with the validation errors if the answer fails checks
    skip_llm_when_no_candidates: bool = True  # no search hits -> Absent without an LLM call
    cache_dir: str = ".cache/llm"     # every LLM reply is cached by prompt hash (relative to repo root)
    min_quote_words: int = 4
    batch_max_output_tokens: int = 16384   # batch answers cover up to 16 flags (plus any hidden thinking)


@dataclass
class Config:
    llm: LLMSettings
    extractor: ExtractorSettings
    source: str


def _pick(cls, d: dict):
    names = {f.name for f in fields(cls)}
    unknown = set(d) - names
    if unknown:
        raise ValueError(f"unknown {cls.__name__} keys in config: {sorted(unknown)}")
    return {k: v for k, v in d.items() if k in names}


def load_config(path: Path | str | None = None, provider: str | None = None, model: str | None = None) -> Config:
    """Load the config. `provider` overrides [llm] provider (its [llm.<provider>] section is used).
    Also loads API keys from .env in the repo root (shell variables take precedence)."""
    load_dotenv()
    p = Path(path) if path else (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else EXAMPLE_CONFIG)
    with open(p, "rb") as fh:
        doc = tomllib.load(fh)
    llm = dict(doc.get("llm", {}))
    if provider:
        llm["provider"] = provider
    provider = llm.get("provider", "")
    if provider not in ("mock", "gemini", "groq"):
        raise ValueError(f"[llm] provider must be mock, gemini or groq, got {provider!r}")
    section = dict(llm.get(provider, {})) if provider != "mock" else {"model": "mock"}
    flat = {k: v for k, v in llm.items() if not isinstance(v, dict)}
    flat.update(section)
    if model:
        flat["model"] = model
    if not flat.get("model"):
        raise ValueError(f"[llm.{provider}] model is required (check your provider console for a current model)")
    return Config(LLMSettings(**_pick(LLMSettings, flat)), ExtractorSettings(**_pick(ExtractorSettings, doc.get("extractor", {}))),
                  str(p))

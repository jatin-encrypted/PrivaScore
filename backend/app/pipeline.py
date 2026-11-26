"""The only place the backend touches privascore. Everything here is configuration or a thin wrapper."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
import time
from dataclasses import dataclass
from typing import NamedTuple

from privascore.config import load_config
from privascore.extractor import Extractor, load_rules
from privascore.flags import load_flags
from privascore.llm import LLMClient, LLMError, QuotaExhausted, make_client
from privascore.metrics import policy_metrics

from .settings import Settings

log = logging.getLogger("privascore.api")


class InMemoryExtractor(Extractor):
    """Identical extraction, but never reads or writes the on-disk LLM reply cache (.cache/llm/).

    Extractor._call(system, user) -> (reply_text, cached) is the only method that touches the
    cache, so overriding it is enough: no file is ever read or created.
    """

    def _call(self, system, user):
        resp = self.client.complete_json(system, user)
        self.stats["llm_calls"] += 1
        return resp.text, False


@dataclass
class RawAnalysis:
    extraction: dict      # Extractor.extract_policy_batch() output
    metrics: dict         # privascore.metrics.policy_metrics() output
    llm_calls: int
    timings_ms: dict
    # The provider and model that actually produced `extraction`. A live analysis can fall back
    # to the second model, and a saved example came from its stored run, so neither is
    # necessarily the model this server was configured with. None means the configured one.
    provider: str | None = None
    model: str | None = None


class Model(NamedTuple):
    name: str
    client: LLMClient


class PipelineService:
    """Built once in the FastAPI lifespan. Holds the LLM client (shared, so its min_interval
    throttle is global), the flag set, the prompt rules and the BERT model."""

    def __init__(self, settings: Settings):
        cfg = load_config(provider=settings.llm_provider or None, model=settings.llm_model or None)
        # Same as `python -m privascore.extract --batch`: one batch answer covers up to 16 flags.
        # Without this, replies get truncated and every flag ends up "rejected".
        cfg.llm.max_output_tokens = max(cfg.llm.max_output_tokens, cfg.extractor.batch_max_output_tokens)
        # Interactive use: fail fast instead of sleeping 65 s per rate-limit wait (the CLI default).
        cfg.llm.max_rate_limit_waits = settings.llm_max_rate_limit_waits
        cfg.llm.overload_waits = tuple(settings.llm_overload_waits)
        cfg.llm.max_http_retries = settings.llm_max_http_retries
        self.cfg = cfg
        self.provider, self.model = cfg.llm.provider, cfg.llm.model
        self.client = make_client(cfg.llm)       # raises LLMError if the API key is missing
        # The model to switch to when the main one hits its usage limit or is overloaded. Same
        # provider and key, so only the model name changes. Gemini counts usage limits per
        # model, so the second model still has its own allowance when the first is used up.
        self.models = [Model(self.model, self.client)]
        fallback = settings.llm_fallback_model.strip()
        self.fallback_model = fallback if fallback and fallback != self.model else None
        if self.fallback_model:
            self.models.append(Model(self.fallback_model,
                                     make_client(dataclasses.replace(cfg.llm, model=self.fallback_model))))
        # model name -> time.monotonic() until which it is skipped. Remembering the limit means
        # later requests go straight to the model that works instead of paying for a refusal
        # first. After the cooldown the main model is tried again.
        self.fallback_cooldown_s = settings.llm_fallback_cooldown_s
        self._limited_until: dict[str, float] = {}
        self._limited_lock = threading.Lock()
        self.flagset = load_flags()
        self.rules = load_rules()                # per-flag ED/CD/EE definitions, shown in the UI
        self.bert = None
        self.bert_status = "disabled"
        if settings.bert_enabled:
            try:
                from privascore.bert import OPP115Bert   # imports torch; only when BERT is on
                self.bert = OPP115Bert()
                self.bert_status = "loaded"
            except Exception as e:               # checkpoint missing, torch missing, ...
                if settings.bert_required:
                    raise RuntimeError(
                        f"BERT checkpoint could not be loaded ({type(e).__name__}). See section 4 of "
                        "_local/team.md, or set PRIVASCORE_BERT_REQUIRED=false."
                    ) from None
                self.bert_status = "unavailable"

    # --- blocking helpers, run in worker threads

    def _metrics(self, text: str):
        t = time.perf_counter()
        m = policy_metrics(text, self.bert)
        return m, round((time.perf_counter() - t) * 1000)

    # --- which model to use

    def _model_order(self) -> list[Model]:
        """The models to try, in order. A model that recently hit its limit goes last rather
        than being dropped: if every model is limited, it is still worth one try, because a
        per-minute limit may have cleared."""
        now = time.monotonic()
        with self._limited_lock:
            limited = {m for m, until in self._limited_until.items() if until > now}
        return sorted(self.models, key=lambda m: m.name in limited)   # stable: main model first

    def _set_limited(self, name: str, limited: bool) -> None:
        with self._limited_lock:
            if limited:
                self._limited_until[name] = time.monotonic() + self.fallback_cooldown_s
            else:
                self._limited_until.pop(name, None)

    @property
    def active_model(self) -> str:
        """The model the next analysis will try first."""
        return self._model_order()[0].name

    def _extract(self, text: str, scope: str, company_name: str | None):
        """Runs the whole extraction with one model. If that model hits its usage limit or is
        overloaded (QuotaExhausted, which includes ProviderOverloaded), the WHOLE extraction is
        run again with the next model, so one result never mixes the answers of two models.
        Any other LLMError is handled inside the extractor (those flags become "rejected"), so
        it does not trigger a switch."""
        t = time.perf_counter()
        completed = 0
        last_exc: QuotaExhausted | None = None
        for model in self._model_order():
            ex = InMemoryExtractor(model.client, self.flagset, self.cfg.extractor)   # cheap; one per attempt
            try:
                res = ex.extract_policy_batch(text, policy_id="input", scope=scope,
                                              policy_name=(company_name or "").strip().lower())
            except QuotaExhausted as exc:
                completed += ex.stats["llm_calls"]
                self._set_limited(model.name, True)
                log.warning("model_unavailable model=%s error=%s", model.name, type(exc).__name__)
                last_exc = exc
                continue
            except LLMError as exc:
                exc.completed_llm_calls = completed + ex.stats["llm_calls"]
                raise
            self._set_limited(model.name, False)
            calls = completed + ex.stats["llm_calls"]
            return res, model.name, calls, round((time.perf_counter() - t) * 1000)
        # Every model refused. How many provider calls COMPLETED before that, across all of them:
        # the counter is incremented only once a call returns, so this is exactly the number the
        # provider billed, and the route refunds the request's budget charge only when it is
        # zero. A batch extraction retries once, so a 503 can arrive after a first call that did
        # succeed.
        last_exc.completed_llm_calls = completed
        raise last_exc

    # --- async entry point used by the route

    async def analyse(self, text: str, scope: str, company_name: str | None) -> RawAnalysis:
        t = time.perf_counter()
        (metrics, m_ms), (extraction, model, calls, e_ms) = await asyncio.gather(
            asyncio.to_thread(self._metrics, text),
            asyncio.to_thread(self._extract, text, scope, company_name),
        )
        total = round((time.perf_counter() - t) * 1000)
        return RawAnalysis(extraction, metrics, calls,
                           {"metrics": m_ms, "extraction": e_ms, "total": total},
                           provider=self.provider, model=model)


def utf16_offsets(text: str):
    """Python indexes code points; JavaScript indexes UTF-16 code units. Returns a function
    mapping a Python offset to a JS offset. Identity when the text has no astral characters."""
    if not any(ord(c) > 0xFFFF for c in text):
        return lambda i: i
    prefix = [0] * (len(text) + 1)
    for k, c in enumerate(text):
        prefix[k + 1] = prefix[k] + (2 if ord(c) > 0xFFFF else 1)
    return prefix.__getitem__

"""Saved gold-set analyses, served without an LLM call (_local/team.md section 11, P1).

Three files on disk describe each example, and all three carry a sha256 of the policy text:

    gold_set/policies/manifest.json      the text file, display name, cohort, scope, source URL
    runs/<run>/<key>.json                the extractor + scoring output for that text
    runs/policy_metrics/...json          readability, vagueness and the BERT profile

An example is only offered when all three hashes agree with the bytes actually on disk. That is
not ceremony: the evidence offsets in the saved analysis index into that exact string, so stale
text would silently highlight the wrong words. A mismatch drops the example and logs its key.

Nothing here is recomputed, so an example costs no Gemini call and no BERT pass. It is rendered
through the same presenter as a live analysis, with source="example".
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from privascore.flags import REPO_ROOT

from .pipeline import RawAnalysis
from .presenter import present
from .schemas import EvaluateResponse, ExampleSummary

log = logging.getLogger(__name__)

GOLD_DIR = REPO_ROOT / "gold_set"
RUNS_DIR = REPO_ROOT / "runs"
METRICS_FILE = RUNS_DIR / "policy_metrics" / "policy_metrics.json"


@dataclass(frozen=True)
class Example:
    """One verified example. `text` and `response` are built on first request, then kept."""
    policy_id: str          # "P06", the public id
    key: str                # "P06_zoom", the on-disk key
    company_name: str       # "Zoom", for display
    cohort: str
    scope: str
    source_url: str
    text_path: Path
    analysis: dict
    metrics: dict

    @cached_property
    def text(self) -> str:
        return self.text_path.read_text(encoding="utf-8")

    def summary(self) -> ExampleSummary:
        sc = self.analysis["scores"]
        return ExampleSummary(
            policy_id=self.policy_id, company_name=self.company_name, cohort=self.cohort,
            scope=self.scope, source_url=self.source_url,
            chars=len(self.text),        # characters, matching Policy.chars, not file bytes
            sentences=self.analysis["n_sentences"],
            risk_index=sc["risk_index"], risk_index_display=sc["risk_index_display"],
            disclosure_quality=sc["disclosure_quality"],
            disclosure_quality_display=sc["disclosure_quality_display"],
            n_not_stated=sc["n_not_stated"], complete=sc["complete"],
        )


class ExampleLibrary:
    """Built once in the lifespan. Holds verified metadata for every example; the rendered
    responses are cached lazily, because each one is a few hundred kB of JSON."""

    def __init__(self, run_name: str):
        self.run_name = run_name
        self.examples: dict[str, Example] = {}
        self.run_meta: dict = {}
        self._rendered: dict[str, EvaluateResponse] = {}
        self._load()

    @property
    def available(self) -> bool:
        return bool(self.examples)

    def _load(self) -> None:
        run_dir = RUNS_DIR / self.run_name
        manifest_file = GOLD_DIR / "policies" / "manifest.json"
        if not (run_dir.is_dir() and manifest_file.is_file() and METRICS_FILE.is_file()):
            log.warning("examples disabled: run %r, manifest or metrics file missing", self.run_name)
            return

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))["policies"]
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        # Which model produced these labels, and when. The UI shows it, because an example was
        # not analysed by whatever model this server is running now.
        self.run_meta = {"run": run["run_name"], "provider": run["provider"],
                         "model": run["model"], "analysed_at": run["created_utc"]}
        skipped = []

        for key, entry in manifest.items():
            try:
                self._add(key, entry, run_dir, metrics)
            except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
                skipped.append(f"{key}: {exc}")

        if skipped:
            log.warning("examples skipped (%d): %s", len(skipped), "; ".join(skipped))
        log.info("examples loaded: %d from run %r", len(self.examples), self.run_name)

    def _add(self, key: str, entry: dict, run_dir: Path, metrics: dict) -> None:
        policy_id = entry["id"]
        text_path = GOLD_DIR / entry["text_file"]
        expected = entry["text_sha256"]

        digest = hashlib.sha256(text_path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError("text file does not match its manifest hash")

        analysis = json.loads((run_dir / f"{key}.json").read_text(encoding="utf-8"))
        if analysis["text_sha256"] != expected:
            raise ValueError("saved analysis was run on different text")

        m = metrics[policy_id]
        if m["text_sha256"] != expected:
            raise ValueError("saved metrics were computed on different text")

        self.examples[policy_id] = Example(
            policy_id=policy_id, key=key, company_name=_display_name(entry["name"]),
            cohort=entry.get("cohort", ""), scope=analysis["scope"],
            source_url=entry.get("final_url") or entry.get("url", ""),
            text_path=text_path, analysis=analysis,
            metrics={k: v for k, v in m.items()
                     if k in ("readability", "vagueness", "bert_profile")},
        )

    def summaries(self) -> list[ExampleSummary]:
        return [e.summary() for e in sorted(self.examples.values(), key=lambda e: e.policy_id)]

    def render(self, policy_id: str, pipeline) -> EvaluateResponse:
        """The full analysis, shaped exactly like a live one. Cached after the first call."""
        if policy_id not in self._rendered:
            ex = self.examples[policy_id]
            raw = RawAnalysis(extraction=ex.analysis, metrics=ex.metrics, llm_calls=0,
                              timings_ms={})
            # document_text is sent ONLY for examples. A live caller already has the text it
            # pasted; an example viewer does not, and the source panel needs it to show quotes
            # in place.
            self._rendered[policy_id] = present(ex.text, raw, pipeline, source="example",
                                                company_name=ex.company_name,
                                                document_text=ex.text)
        return self._rendered[policy_id]


# The manifest stores lowercase slugs ("openai"); these are the names to show instead. A slug
# with no entry is title-cased, which is right for "spotify" and "notion".
DISPLAY_NAMES = {
    "openai": "OpenAI", "deepseek": "DeepSeek", "xai": "xAI", "phonepe": "PhonePe",
}


def _display_name(slug: str) -> str:
    return DISPLAY_NAMES.get(slug, slug.title())

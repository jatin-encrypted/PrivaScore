"""Request and response models (_local/team.md sections 6.6 and 6.7).

These exist so that /openapi.json is a real contract and the frontend can generate its types
from it (`openapi-typescript`). They are also the privacy boundary: the response is built field
by field in presenter.py, so an internal key cannot reach the client by accident.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scope = Literal["all_users", "consumer"]
State = Literal["ED", "CD", "EE", "NS", "UN"]
Status = Literal["verified", "verified_partial", "absent_unverifiable", "no_candidates",
                 "not_applicable", "rejected"]


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str                                    # length is checked in the handler, not here
    company_name: str | None = Field(None, max_length=120)
    scope: Scope = "all_users"


class Policy(BaseModel):
    company_name: str | None
    scope: Scope
    chars: int
    sentences: int
    paragraphs: int
    text_sha256: str


class Scores(BaseModel):
    risk_index: float
    risk_index_display: int
    disclosure_quality: float
    disclosure_quality_display: int
    n_applicable: int
    n_not_stated: int
    complete: bool
    rejected_flags: list[str]
    scoring_version: str


class Evidence(BaseModel):
    sentence_id: str
    heading: str | None
    match: Literal["exact", "normalized"]
    offset_utf16: tuple[int, int]
    text: str                                    # the POLICY's own characters, not the model's quote


class FlagResult(BaseModel):
    id: str
    key: str
    title: str
    group: Literal["general", "ai", "dpdp"]
    type: str
    weight: float
    question: str
    state: State
    state_meaning: str
    status: Status
    applicable: bool
    not_applicable_reason: str | None
    risk_points: float
    max_risk_points: float
    quality_points: float
    rationale: str | None
    evidence: list[Evidence]
    dropped_evidence_count: int
    n_candidates: int
    n_search_terms: int


class Readability(BaseModel):
    fk_grade: float
    flesch_reading_ease: float
    reading_minutes: float
    words: int
    prose_sentences: int
    avg_words_per_sentence: float


class VagueExample(BaseModel):
    sentence_id: str
    text: str
    cues: dict[str, list[str]]


class Vagueness(BaseModel):
    vague_sentence_fraction: float
    multi_category_fraction: float
    cues_per_1000_words: dict[str, float]
    examples: list[VagueExample]


class BertCategory(BaseModel):
    name: str
    share: float


class BertProfile(BaseModel):
    available: bool
    reason: Literal["disabled", "unavailable"] | None = None
    paragraphs: int | None = None
    threshold: float | None = None
    categories: list[BertCategory] | None = None


class Metrics(BaseModel):
    readability: Readability
    vagueness: Vagueness
    bert_profile: BertProfile


class Paragraph(BaseModel):
    id: str
    offset_utf16: tuple[int, int]
    is_heading: bool


class Document(BaseModel):
    paragraphs: list[Paragraph]
    text: str | None = None                      # only for saved examples, never for live input


class Warning_(BaseModel):
    code: Literal["FEW_LINE_BREAKS", "NO_MATCHES", "MOCK_PROVIDER", "BERT_UNAVAILABLE"]
    message: str


class Meta(BaseModel):
    provider: str
    model: str
    prompt_version: str
    rules_version: str
    flag_definitions_version: str
    privascore_version: str
    llm_calls: int
    timings_ms: dict[str, int]
    analysed_at: str


class EvaluateResponse(BaseModel):
    api_version: str
    source: Literal["live", "example"]
    policy: Policy
    scores: Scores
    flags: list[FlagResult]
    metrics: Metrics
    document: Document
    warnings: list[Warning_]
    meta: Meta


class ExampleSummary(BaseModel):
    """One row of GET /examples: enough to list and plot the saved analyses, without their
    flags, evidence or text. The full analysis comes from GET /examples/{policy_id}."""
    policy_id: str
    company_name: str
    cohort: str
    scope: str
    source_url: str
    chars: int
    sentences: int
    risk_index: float
    risk_index_display: int
    disclosure_quality: float
    disclosure_quality_display: int
    n_not_stated: int
    complete: bool


class ExampleList(BaseModel):
    run: str
    provider: str
    model: str
    analysed_at: str
    examples: list[ExampleSummary]

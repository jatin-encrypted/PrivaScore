"""Quote verifier: does a quote really occur in the policy, and inside the sentences cited for it?

Used by the LLM extractor on every answer. Match levels:
  exact       the quote occurs character-for-character
  normalized  it occurs after Unicode/quote-mark/dash/case/whitespace normalisation, or after
              also ignoring punctuation and spaces ("compact")
  anything else is rejected. Fuzzy similarity is reported only as a diagnostic (to tell the
  LLM how far off it was when retrying); a fuzzy match is NEVER accepted as evidence.

What verification proves: the words exist in the policy at the cited place.
What it does not prove: that those words support the label. That is what the evaluation
against the human gold labels measures.
"""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .text import flatten, normalize, normalize_with_map, segment

ELLIPSIS_RE = re.compile(r"\s*(?:\.\.\.|…)\s*")
MIN_QUOTE_WORDS = 4


class PolicyDoc:
    """A policy text with sentence IDs identical to the gold-set evidence packets."""

    def __init__(self, text: str, policy_id: str = ""):
        self.text = text
        self.policy_id = policy_id
        self.paragraphs = segment(text)
        self.flat = flatten(self.paragraphs)
        self.sentences = {s["sid"]: s for _, s in self.flat}
        self.heading_of = {s["sid"]: p["heading"] for p, s in self.flat}
        self.order = {s["sid"]: i for i, (_, s) in enumerate(self.flat)}
        self._norm = normalize_with_map(text)
        self._compact = normalize_with_map(text, compact=True)

    def sids_overlapping(self, start: int, end: int):
        return [sid for sid, s in self.sentences.items() if s["start"] < end and start < s["end"]]

    def find(self, quote: str, within: tuple | None = None):
        """Locate `quote`. within=(start, end) restricts the search to that character range.
        Returns (status, start, end) with offsets in the original text, or ("not_found", None, None)."""
        lo, hi = within if within else (0, len(self.text))
        hay = self.text[lo:hi]
        pos = hay.find(quote)
        if pos >= 0:
            return "exact", lo + pos, lo + pos + len(quote)
        for compact, (norm, idx) in ((False, self._norm), (True, self._compact)):
            needle = normalize(quote, compact)
            if not needle:
                continue
            # restrict the normalised haystack to the original range via the index map
            a = next((k for k, i in enumerate(idx) if i >= lo), len(idx))
            b = next((k for k, i in enumerate(idx) if i >= hi), len(idx)) if hi < len(self.text) else len(idx)
            pos = norm.find(needle, a, b)
            if pos >= 0 and pos + len(needle) <= b:
                return "normalized", idx[pos], idx[pos + len(needle) - 1] + 1
        return "not_found", None, None

    def closest(self, quote: str):
        """Diagnostic only: best fuzzy alignment score (0-100) and the closest original text."""
        norm, idx = self._norm
        n = normalize(quote)
        if not n or not norm:
            return 0.0, ""
        al = fuzz.partial_ratio_alignment(n, norm)
        s, e = idx[al.dest_start], idx[max(al.dest_end, al.dest_start + 1) - 1] + 1
        return round(al.score, 1), self.text[s:e]


@dataclass
class QuoteCheck:
    quote: str
    ok: bool
    status: str                 # exact | normalized | not_found | outside_cited | too_short | empty
    start: int | None = None
    end: int | None = None
    sids: list = field(default_factory=list)
    message: str = ""
    closest_score: float | None = None
    closest_text: str = ""


def verify_quote(doc: PolicyDoc, quote: str, cited_sids=None, min_words: int = MIN_QUOTE_WORDS) -> QuoteCheck:
    """Verify one quote. If cited_sids is given, the quote must lie inside those sentences."""
    q = (quote or "").strip().strip('"“”').strip()
    if not q:
        return QuoteCheck(quote, False, "empty", message="empty quote")
    parts = [p for p in ELLIPSIS_RE.split(q) if p.strip()]
    if len(q.split()) < min_words:
        # A short quote is fine only when it is the WHOLE cited sentence (e.g. "MR. Praveen Parihar");
        # a short fragment of a longer sentence is too weak to show what the sentence says.
        whole = cited_sids and any(normalize(doc.sentences[s]["text"]) == normalize(q)
                                   for s in cited_sids if s in doc.sentences)
        if not whole:
            return QuoteCheck(quote, False, "too_short",
                              message=f"quote has fewer than {min_words} words and is not a whole sentence")

    spans, statuses = [], []
    for part in parts:
        found = None
        if cited_sids:
            for sid in cited_sids:
                s = doc.sentences.get(sid)
                if s is None:
                    continue
                st, a, b = doc.find(part, within=(s["start"], s["end"]))
                if st != "not_found":
                    found = (st, a, b)
                    break
        if found is None:
            st, a, b = doc.find(part)
            if st != "not_found" and cited_sids:
                where = doc.sids_overlapping(a, b)
                return QuoteCheck(quote, False, "outside_cited", a, b, where,
                                  f"quote occurs in {', '.join(where)}, not in the cited sentences "
                                  f"{', '.join(cited_sids)}")
            if st == "not_found":
                score, near = doc.closest(part)
                return QuoteCheck(quote, False, "not_found", message="quote not found in the policy text",
                                  closest_score=score, closest_text=near)
            found = (st, a, b)
        statuses.append(found[0])
        spans.append((found[1], found[2]))

    start, end = min(a for a, _ in spans), max(b for _, b in spans)
    sids = sorted({sid for a, b in spans for sid in doc.sids_overlapping(a, b)}, key=doc.order.get)
    status = "exact" if all(s == "exact" for s in statuses) else "normalized"
    return QuoteCheck(quote, True, status, start, end, sids)

"""Deterministic text checks (no LLM): readability and vague-wording cues.

These are DESCRIPTIVE indicators reported next to the Risk Index and Disclosure Quality.
They are deliberately not folded into either score: the literature gives no validated
coefficients for doing so.

Readability
  Flesch Reading Ease  = 206.835 - 1.015 (words/sentence) - 84.6 (syllables/word)   (Flesch 1948)
  Flesch-Kincaid grade = 0.39 (words/sentence) + 11.8 (syllables/word) - 15.59      (Kincaid et al. 1975)
  Syllables are counted with a vowel-group heuristic, so values are approximate (typically within
  about +/-1 grade of dictionary-based tools). Reading time uses 238 words/minute (Brysbaert 2019,
  adult silent reading of non-fiction).

Vague-wording cues
  Four categories from Bhatia, Breaux, Reidenberg & Norton (2016), "A Theory of Vagueness and
  Privacy Risk Perception" (IEEE RE): Conditionality, Generalization, Modality, Numeric quantifier.
  The TERM LIST below is PrivaScore's own lexicon built around those categories; individual terms
  have not been checked against the paper's tables, so cite the categories, not the list.
  A hit is a cue, not a judgement: "may" in "we may share" is vague hedging, but a nearby sentence
  can resolve it (false vagueness, Lian et al. 2023). No context filter is applied here.
"""
import re
from dataclasses import dataclass, field

from .text import flatten, segment

LEXICON_VERSION = "privascore-vague-1.0"
LEXICON_SOURCE = ("Categories: Bhatia et al. 2016 (IEEE RE). Terms: PrivaScore lexicon (not verified term-by-term "
                  "against the paper).")

VAGUE_TERMS = {
    "conditionality": [
        "as needed", "as necessary", "where necessary", "if necessary", "when necessary", "as appropriate",
        "where appropriate", "when appropriate", "as applicable", "where applicable", "if applicable",
        "depending on", "depends on", "from time to time", "at our discretion", "in our discretion",
        "as required", "reasonably necessary", "otherwise reasonably", "to the extent", "in certain cases",
        "in some cases", "in certain circumstances", "in some circumstances",
    ],
    "generalization": [
        "generally", "usually", "typically", "normally", "commonly", "mostly", "largely", "primarily",
        "mainly", "often", "among other things", "such as", "including but not limited to",
        "including without limitation", "and the like", "and other", "or other", "etc",
    ],
    "modality": [
        "may", "might", "can", "could", "would", "possibly", "possible", "potentially", "likely",
    ],
    "numeric_quantifier": [
        "some", "certain", "various", "numerous", "several", "many", "much", "most", "few", "a number of",
        "any", "other",
    ],
}


def _compile(term: str):
    if term == "may":       # not the month: "May 2026", "May 26"
        return re.compile(r"\bmay\b(?!\s+\d)", re.IGNORECASE)
    return re.compile(r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b", re.IGNORECASE)


_PATTERNS = {cat: [(t, _compile(t)) for t in terms] for cat, terms in VAGUE_TERMS.items()}

WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
READING_WPM = 238


def count_syllables(word: str) -> int:
    """Vowel-group heuristic with common English corrections. Approximate by design."""
    w = word.lower().replace("’", "'")
    w = re.sub(r"'s$", "", w)
    if len(w) <= 3:
        return 1
    # silent endings: "shared", "makes", "share" (but "-ted/-ded" is pronounced: "deleted"; "-le" is kept: "table")
    w = re.sub(r"(?:[^laeiouydt]ed|[^laeiouy]es|[^laeiouy]e)$", lambda m: m.group(0)[0], w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", w)))


@dataclass
class VagueSentence:
    sid: str
    categories: dict
    text: str


@dataclass
class TextStats:
    words: int
    sentences: int
    syllables: int
    flesch_reading_ease: float
    fk_grade: float
    avg_words_per_sentence: float
    reading_minutes: float
    vague_sentence_fraction: float          # sentences with >= 1 cue / all prose sentences
    multi_category_fraction: float          # sentences with cues from >= 2 categories
    cues_per_1000_words: dict               # per category
    top_vague: list = field(default_factory=list)

    def to_dict(self):
        d = {k: v for k, v in vars(self).items() if k != "top_vague"}
        d["top_vague"] = [vars(v) for v in self.top_vague]
        d["lexicon"] = {"version": LEXICON_VERSION, "source": LEXICON_SOURCE}
        return d


def is_prose(text: str) -> bool:
    """Skip navigation / headings / single labels: a prose sentence has >= 6 words and ends like a sentence
    or is long enough to be one."""
    n = len(WORD_RE.findall(text))
    return n >= 6 and (text.rstrip()[-1:] in ".;:!?" or n >= 15)


def analyse(text: str, top_n: int = 10) -> TextStats:
    flat = flatten(segment(text))
    prose = [s for _, s in flat if is_prose(s["text"])]
    words = syll = 0
    vague, multi = [], 0
    cue_counts = {c: 0 for c in VAGUE_TERMS}
    for s in prose:
        ws = WORD_RE.findall(s["text"])
        words += len(ws)
        syll += sum(count_syllables(w) for w in ws)
        cats = {}
        for cat, pats in _PATTERNS.items():
            hits = [t for t, rx in pats for _ in rx.finditer(s["text"])]
            if hits:
                cats[cat] = hits
                cue_counts[cat] += len(hits)
        if cats:
            vague.append(VagueSentence(s["sid"], cats, s["text"]))
            multi += len(cats) >= 2
    n = len(prose)
    wps = words / n if n else 0.0
    spw = syll / words if words else 0.0
    ranked = sorted(vague, key=lambda v: (-len(v.categories), -sum(len(h) for h in v.categories.values())))
    return TextStats(
        words=words, sentences=n, syllables=syll,
        flesch_reading_ease=round(206.835 - 1.015 * wps - 84.6 * spw, 1) if n else 0.0,
        fk_grade=round(0.39 * wps + 11.8 * spw - 15.59, 1) if n else 0.0,
        avg_words_per_sentence=round(wps, 1),
        reading_minutes=round(words / READING_WPM, 1),
        vague_sentence_fraction=round(len(vague) / n, 3) if n else 0.0,
        multi_category_fraction=round(multi / n, 3) if n else 0.0,
        cues_per_1000_words={c: round(1000 * k / words, 1) if words else 0.0 for c, k in cue_counts.items()},
        top_vague=ranked[:top_n],
    )


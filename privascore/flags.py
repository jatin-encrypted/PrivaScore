"""Flag definitions and retrieval (search terms -> candidate sentences).

The single source of truth is gold_set/flag_definitions.json: the human evidence packets and
the LLM extractor search with exactly the same terms.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .text import norm_for_search

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLAGS_FILE = REPO_ROOT / "gold_set" / "flag_definitions.json"


def repo_relative(path: Path | str) -> str:
    """`path` relative to the repository root if it lies inside it, otherwise unchanged.

    Every path written into a run record goes through this, so the records do not
    contain the local home directory."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)

STATES = ("ED", "CD", "EE", "NS", "UN")
PRESENCE_TO_STATE = {"Absent": "NS", "Unclear": "UN"}


@dataclass(frozen=True)
class Flag:
    id: str
    key: str
    type: str          # exposure | governance | readiness | readiness_info
    weight: float
    question: str
    terms: tuple

    @property
    def protective(self) -> bool:
        """True when ED means a protection exists (governance/readiness), False for exposure."""
        return self.type != "exposure"


@dataclass
class FlagSet:
    flags: list
    version: str
    sha256: str
    self_names: dict = field(default_factory=dict)

    def by_id(self):
        return {f.id: f for f in self.flags}


def load_flags(path: Path = DEFAULT_FLAGS_FILE) -> FlagSet:
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    flags = [Flag(f["id"], f["key"], f["type"], float(f["weight"]), f["question"], tuple(f["terms"]))
             for f in doc["flags"]]
    self_names = {k: frozenset(n.lower() for n in v) for k, v in doc.get("self_names", {}).items()}
    return FlagSet(flags, doc.get("version", "?"), hashlib.sha256(raw).hexdigest(), self_names)


def term_hits(t, rx, hay, self_names):
    if not t.get("exclude_self"):
        return rx.search(hay) is not None
    return any(m.group(0).lower() not in self_names for m in rx.finditer(hay))


def search_flag(flag, flat, self_names=frozenset()):
    """flat: list of (paragraph, sentence). Returns (search_log, candidates).

    A sentence is a candidate when it matches >= 1 core term or >= 2 support terms.
    score = 3 * (#core terms) + (#support terms).
    """
    terms = flag.terms if isinstance(flag, Flag) else flag["terms"]
    compiled = [(t, re.compile(t["regex"], re.IGNORECASE)) for t in terms]
    log = {t["label"]: {"regex": t["regex"], "tier": t["tier"], "sentences_matched": 0} for t in terms}
    cands = []
    for idx, (para, s) in enumerate(flat):
        hay = norm_for_search(s["text"])
        core, support = [], []
        for t, rx in compiled:
            if term_hits(t, rx, hay, self_names):
                log[t["label"]]["sentences_matched"] += 1
                (core if t["tier"] == "core" else support).append(t["label"])
        if core or len(support) >= 2:
            cands.append({"idx": idx, "sid": s["sid"], "heading": para["heading"], "core": core, "support": support,
                          "score": 3 * len(core) + len(support)})
    return log, cands

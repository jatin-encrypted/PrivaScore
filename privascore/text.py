"""Text handling shared by the gold-set tools and the product pipeline.

The normalisation and the segmentation (first written for gold_set/build_evidence.py) live
here so that human gold labels and LLM extractions use the SAME sentence IDs and
the SAME notion of "the quote appears in the policy". Changing anything here changes sentence
IDs: bump SEGMENTER_VERSION and rebuild the evidence packets.
"""
import re
import unicodedata

SEGMENTER_VERSION = "1"

# ---------------------------------------------------------------- normalisation (for matching)

CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "`": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
}
INVISIBLE = {"​", "‌", "‍", "⁠", "﻿", "­", "⁣"}

# Screen-reader-only link labels that HTML extraction (v1) dropped into sentences. Text v2 no
# longer contains them; kept so matching against v1 text or user-pasted text still works.
IGNORABLE_RE = re.compile(r"\(opens in a new (?:window|tab)\)", re.IGNORECASE)


def normalize_with_map(text: str, compact: bool = False):
    """Return (normalised string, list mapping each normalised char to its index in `text`).

    Normalised = NFKC, curly quotes/dashes mapped to ASCII, invisible characters removed,
    casefolded, whitespace runs collapsed to one space. compact=True also drops all spaces and
    punctuation. The map lets callers show the ORIGINAL text for any normalised match.
    """
    skip = {i for m in IGNORABLE_RE.finditer(text) for i in range(m.start(), m.end())}
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(text):
        if ch in INVISIBLE or i in skip:
            continue
        for c in unicodedata.normalize("NFKC", CHAR_MAP.get(ch, ch)):
            c = CHAR_MAP.get(c, c).casefold()
            if c.isspace():
                if compact or prev_space:
                    continue
                out.append(" ")
                idx.append(i)
                prev_space = True
                continue
            if compact and not c.isalnum():
                continue
            for cc in c:  # casefold can expand (e.g. "ß" -> "ss")
                out.append(cc)
                idx.append(i)
            prev_space = False
    s = "".join(out)
    if s.endswith(" "):
        s, idx = s[:-1], idx[:-1]
    return s, idx


def normalize(text: str, compact: bool = False) -> str:
    return normalize_with_map(text, compact)[0]


def norm_for_search(s: str) -> str:
    """Light normalisation used before running the flag search regexes."""
    return (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
             .replace("–", "-").replace("—", "-").replace(" ", " "))


def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- segmentation (sentence IDs)

# Split after . ! ? (optionally followed by a closing quote/bracket) when the next
# sentence starts with a capital, digit, quote or bracket. Abbreviations such as
# "e.g. the" are not split because the next word is lowercase.
SENT_SPLIT = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+(?=[A-Z0-9\"'“‘(\[•])")
ABBREV_END = re.compile(r"\b(?:e\.g|i\.e|etc|Inc|Ltd|Co|Corp|Mr|Ms|Dr|No|U\.S|vs|St|Pvt)\.$")


def is_heading(line: str) -> bool:
    words = line.split()
    return (0 < len(words) <= 12 and not re.search(r"[.;:,]$", line)
            and (line[0].isupper() or line[0].isdigit()))


def segment(text: str):
    """Return paragraphs: list of dict(pid, heading, is_heading, start, end,
    sentences=[dict(sid, start, end, text)]). One non-empty line = one paragraph."""
    paragraphs, heading, pos, n = [], "", 0, 0
    for line in text.split("\n"):
        start = pos
        pos += len(line) + 1
        stripped = line.strip()
        if not stripped:
            continue
        n += 1
        lead = len(line) - len(line.lstrip())
        p_start = start + lead
        pid = f"p{n:03d}"
        if is_heading(stripped):
            heading = stripped
        pieces, cur = [], 0
        for m in SENT_SPLIT.finditer(stripped):
            cand = stripped[cur:m.start()].rstrip()
            if ABBREV_END.search(cand):
                continue
            pieces.append((cur, m.start()))
            cur = m.end()
        pieces.append((cur, len(stripped)))
        sentences = []
        for k, (a, b) in enumerate(pieces, 1):
            s_text = stripped[a:b].strip()
            if not s_text:
                continue
            a2 = stripped.index(s_text, a)
            sentences.append({"sid": f"{pid}.s{k}", "start": p_start + a2, "end": p_start + a2 + len(s_text),
                              "text": s_text})
        paragraphs.append({"pid": pid, "heading": heading if not is_heading(stripped) else stripped,
                           "is_heading": is_heading(stripped), "start": p_start,
                           "end": p_start + len(stripped), "sentences": sentences})
    return paragraphs


def flatten(paragraphs):
    """List of (paragraph, sentence) in document order."""
    return [(p, s) for p in paragraphs for s in p["sentences"]]

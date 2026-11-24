"""Step 1 of the gold set: download the 15 privacy policies and freeze them.

For each policy we save:
  policies/raw/<id>.html   exactly the bytes the server returned
  policies/text/<id>.txt   readable text extracted from that HTML
  policies/manifest.json   URL, final URL after redirects, HTTP status, UTC fetch
                           time, sha256 of raw and text, length, and a warning
                           when the page looks blocked or JavaScript-rendered

Why: the gold labels must point at one fixed copy of each policy. Policies
change often, so "the text we labelled" has to be a dated, hashed file.

Re-running never overwrites an existing snapshot unless --refetch is given.
Some sites only show the policy after JavaScript runs (or after a bot check), so
--browser loads the page in headless Chromium (Playwright) and saves the
rendered DOM instead. The manifest records which method was used.

Usage: .venv/bin/python -I gold_set/fetch_policies.py [--only P01,P07] [--refetch] [--browser]
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, CData, Comment, Declaration, Doctype, ProcessingInstruction

HERE = Path(__file__).resolve().parent
OUT = HERE / "policies"

POLICIES = [
    # id, short name, cohort, scope, url
    ("P01", "openai", "ai", "consumer", "https://openai.com/policies/row-privacy-policy/"),
    ("P02", "anthropic", "ai", "consumer", "https://www.anthropic.com/legal/privacy"),
    ("P03", "deepseek", "ai", "consumer", "https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html"),
    ("P04", "perplexity", "ai", "consumer", "https://www.perplexity.ai/hub/legal/privacy-notice"),
    ("P05", "xai", "ai", "consumer", "https://x.ai/legal/privacy-policy"),
    ("P06", "zoom", "global", "all_users", "https://www.zoom.com/en/trust/privacy/privacy-statement/"),
    ("P07", "spotify", "global", "all_users", "https://www.spotify.com/in-en/legal/privacy-policy/"),
    ("P08", "reddit", "global", "all_users", "https://www.reddit.com/policies/privacy-policy"),
    ("P09", "notion", "global", "all_users", "https://www.notion.so/Privacy-Policy-3468d120cf614d4c9014c09f6adc9091"),
    ("P10", "duolingo", "global", "all_users", "https://www.duolingo.com/privacy"),
    ("P11", "razorpay", "india", "all_users", "https://razorpay.com/privacy-policy/"),
    ("P12", "phonepe", "india", "all_users", "https://www.phonepe.com/privacy-policy/"),
    ("P13", "swiggy", "india", "all_users", "https://www.swiggy.com/privacy-policy"),
    ("P14", "zomato", "india", "all_users", "https://www.zomato.com/policies/privacy/"),
    ("P15", "unacademy", "india", "all_users", "https://unacademy.com/privacy"),
]

HEADERS = {
    # A normal desktop browser UA: several of these sites return 403 to unknown clients.
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
}

# A real privacy policy is long and uses these words; a blocked/JS shell page does not.
MIN_WORDS = 1500
POLICY_WORDS = ("personal", "data", "information", "privacy")
BLOCK_HINTS = ("captcha", "access denied", "enable javascript", "are you a robot",
               "cloudflare", "just a moment")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


TEXT_EXTRACTOR_VERSION = "2"

BLOCK_TAGS = {"address", "article", "aside", "blockquote", "dd", "details", "div", "dl", "dt", "fieldset",
              "figcaption", "figure", "form", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li", "main", "ol", "p",
              "pre", "section", "summary", "table", "tbody", "thead", "tfoot", "tr", "td", "th", "ul", "caption"}
HIDDEN_CLASS_RE = re.compile(r"\b(?:sr-only|visually-hidden|screen-reader-text|screenreader)\b", re.IGNORECASE)
BREAK = " "  # paragraph separator used as an internal line-break marker


def html_to_text(html: bytes) -> str:
    """Readable text, one block element per line. Inline elements (links, bold, spans) stay
    inside their sentence. No wording is rewritten; only whitespace is collapsed as a browser does.

    v1 (12 Nov) used get_text("\\n"), which put every inline element on its own line and split
    sentences at links. v2 fixes that and drops screen-reader-only text that is not visible.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    # Navigation chrome is not policy text.
    for tag in soup(["nav", "header", "footer"]):
        tag.decompose()
    for tag in soup.find_all(class_=HIDDEN_CLASS_RE):
        tag.decompose()
    # HTML comments (e.g. React's <!--$--> markers), doctype, CDATA: not visible text.
    for node in soup.find_all(string=lambda s: isinstance(s, (Comment, Doctype, CData, ProcessingInstruction, Declaration))):
        node.extract()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    # Collapse source-code whitespace inside text nodes, as HTML rendering does.
    for s in root.find_all(string=True):
        s.replace_with(re.sub(r"\s+", " ", str(s)))
    for br in root.find_all("br"):
        br.replace_with(BREAK)
    for tag in root.find_all(BLOCK_TAGS):
        tag.insert_before(BREAK)
        tag.insert_after(BREAK)
    text = root.get_text("")
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.split(BREAK)]
    return "\n".join(ln for ln in lines if ln) + "\n"


def assess(text: str, status: int) -> list[str]:
    warnings = []
    words = len(text.split())
    low = text.lower()
    if status != 200:
        warnings.append(f"HTTP {status}")
    if words < MIN_WORDS:
        warnings.append(f"only {words} words: probably JavaScript-rendered or blocked")
    if sum(low.count(w) for w in POLICY_WORDS) < 20:
        warnings.append("few privacy keywords: may not be the policy text")
    hits = [h for h in BLOCK_HINTS if h in low[:3000]]
    if hits:
        warnings.append("block-page hints: " + ", ".join(hits))
    return warnings


class BrowserFetcher:
    """Headless Chromium: waits for the page's JavaScript, then returns the rendered HTML."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._ctx = self._browser.new_context(user_agent=HEADERS["User-Agent"], locale="en-IN")

    def get(self, url: str):
        page = self._ctx.new_page()
        try:
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(2000)  # late-rendering content / bot-check redirect
            except Exception:
                # Pages with endless background requests never go idle: load, then wait.
                resp = page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(8000)
            html = page.content().encode("utf-8")
            return (resp.status if resp else None), page.url, html
        finally:
            page.close()

    def close(self):
        self._browser.close()
        self._pw.stop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated ids, e.g. P01,P07")
    ap.add_argument("--refetch", action="store_true", help="overwrite existing snapshots")
    ap.add_argument("--browser", action="store_true", help="render with headless Chromium")
    ap.add_argument("--reextract", action="store_true",
                    help="no download: re-derive text/ from the saved raw/ HTML with the current extractor; "
                         "the previous text files move to text_v<old version>/ and their hashes stay in the manifest")
    args = ap.parse_args()
    if args.reextract:
        return reextract(set(args.only.split(",")) if args.only else None)
    browser = BrowserFetcher() if args.browser else None
    only = set(args.only.split(",")) if args.only else None

    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    (OUT / "text").mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for pid, name, cohort, scope, url in POLICIES:
        if only and pid not in only:
            continue
        key = f"{pid}_{name}"
        raw_path = OUT / "raw" / f"{key}.html"
        txt_path = OUT / "text" / f"{key}.txt"
        if raw_path.exists() and not args.refetch:
            print(f"{key:15} kept existing snapshot (use --refetch to replace)")
            continue

        entry = {"id": pid, "name": name, "cohort": cohort, "scope": scope, "url": url}
        try:
            if browser:
                status, final_url, raw = browser.get(url)
                entry.update(status=status, final_url=final_url, content_type="text/html (rendered)")
            else:
                r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
                status, raw = r.status_code, r.content
                entry.update(status=status, final_url=r.url,
                             content_type=r.headers.get("Content-Type", ""))
        except Exception as e:  # network errors from either fetcher
            entry.update(status=None, error=str(e)[:300], warnings=["download failed"])
            manifest[key] = entry
            print(f"{key:15} FAILED  {e.__class__.__name__}")
            continue

        text = html_to_text(raw)
        raw_path.write_bytes(raw)
        txt_path.write_text(text, encoding="utf-8")
        entry.update(
            fetched_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            method="playwright-chromium" if browser else "requests",
            raw_file=str(raw_path.relative_to(HERE)),
            text_file=str(txt_path.relative_to(HERE)),
            raw_sha256=sha256(raw),
            text_sha256=sha256(text.encode("utf-8")),
            raw_bytes=len(raw),
            text_words=len(text.split()),
            warnings=assess(text, status),
            text_extractor_version=TEXT_EXTRACTOR_VERSION,
        )
        manifest[key] = entry
        flag = "OK " if not entry["warnings"] else "CHECK"
        print(f"{key:15} {flag} status {status}  {entry['text_words']:>6} words  "
              f"{'; '.join(entry['warnings'])}")
        time.sleep(1.0)  # be polite

    if browser:
        browser.close()
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    print(f"\nwrote {manifest_path.relative_to(HERE.parent)}")
    return 0


def reextract(only) -> int:
    """Re-derive the text files from the unchanged raw HTML. Raw files and their hashes are verified first."""
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for key, e in sorted(manifest.items()):
        if only and e["id"] not in only:
            continue
        raw = (HERE / e["raw_file"]).read_bytes()
        if sha256(raw) != e["raw_sha256"]:
            sys.exit(f"ERROR: {key} raw HTML no longer matches its manifest hash; refusing.")
        old_ver = e.get("text_extractor_version", "1")
        if old_ver == TEXT_EXTRACTOR_VERSION:
            print(f"{key:15} already extracted with v{old_ver}")
            continue
        old_path = HERE / e["text_file"]
        archive = OUT / f"text_v{old_ver}" / old_path.name
        archive.parent.mkdir(exist_ok=True)
        old_path.replace(archive)
        e.setdefault("previous_text_versions", []).append({
            "version": old_ver, "file": str(archive.relative_to(HERE)), "sha256": e["text_sha256"],
            "words": e["text_words"]})
        text = html_to_text(raw)
        old_path.write_text(text, encoding="utf-8")
        e.update(text_sha256=sha256(text.encode("utf-8")), text_words=len(text.split()),
                 text_extractor_version=TEXT_EXTRACTOR_VERSION,
                 warnings=assess(text, e["status"]))
        print(f"{key:15} v{old_ver} -> v{TEXT_EXTRACTOR_VERSION}: {e['previous_text_versions'][-1]['words']:>6} -> "
              f"{e['text_words']:>6} words  {'; '.join(e['warnings'])}")
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

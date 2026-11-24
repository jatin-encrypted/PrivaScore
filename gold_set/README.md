# Gold set: 15 policies × 16 flags

The reference set used to evaluate the extractor. It covers 15 privacy policies in three cohorts of five:

| Cohort | Policies |
|---|---|
| AI services | P01 OpenAI, P02 Anthropic, P03 DeepSeek, P04 Perplexity, P05 xAI |
| Global apps | P06 Zoom, P07 Spotify, P08 Reddit, P09 Notion, P10 Duolingo |
| Indian apps | P11 Razorpay, P12 PhonePe, P13 Swiggy, P14 Zomato, P15 Unacademy |

Each (policy, flag) pair gets one of five evidence states (ED, CD, EE, NS, UN), so there are 240 labels. The rules are in `ANNOTATION_GUIDELINES.md`.

## Step 1: snapshots (done 2026-11-12)

```bash
.venv/bin/python -I gold_set/fetch_policies.py                 # plain HTTP download
.venv/bin/python -I gold_set/fetch_policies.py --only P08,P09,P10,P13 --refetch --browser
```

- `policies/raw/` holds the bytes as served (or the rendered page for `--browser`).
- `policies/text/` holds the extracted text. **Labels and quotes refer to these files.**
- `policies/manifest.json` records the URL, final URL, HTTP status, UTC fetch time, method, sha256 of the raw page and of the text, and word count.

**Fetch method:** P08 Reddit, P09 Notion, P10 Duolingo and P13 Swiggy only show their text after JavaScript runs (Reddit also serves a bot-check page), so they were rendered with headless Chromium. The other 11 were fetched with plain `requests`.

**Notes on the snapshots:**
- P05 now reads "SpaceXSI Privacy Policy" (SpaceX Super Intelligence LLC), last updated 27 Oct 2026. The file key stays `xai`.
- P11 Razorpay: the saved page contains no "DPDPA", "Sections 5 and 6" or "Eighth Schedule" text, and it uses browsewrap wording ("By visiting or using the Website, you agree…").
- P12 PhonePe offers a language switcher with 11 Indian languages, which matters for DPDP4.
- Anthropic and Unacademy show no "last updated" date in the extracted text, so the fetch date is recorded instead.

Policies change. Never re-fetch over these snapshots; to compare a newer version, fetch it into a separate folder.

## Text extraction v2 (2026-11-14)

The first extraction (v1, 12 Nov) put every link and bold span on its own line, which split sentences. v2 is re-derived from the **unchanged** raw HTML with no new download:
- inline elements stay inside their sentence;
- screen-reader-only text and HTML comments are dropped.

```bash
.venv/bin/python -I gold_set/fetch_policies.py --reextract
```

The v1 hashes are kept in `manifest.json` under `previous_text_versions`. All labelling uses v2.

## Step 2: evidence packets and the labelling sheet

```bash
.venv/bin/python -I gold_set/build_evidence.py --only P01,P07        # packets for some policies
.venv/bin/python -I gold_set/build_evidence.py --init-sheet A1       # all 15 + blank sheet for annotator A1
.venv/bin/python -I gold_set/validate_labels.py --annotator A1      # check + resolve the sheet
```

- `flag_definitions.json` defines the 16 flags: the question for each flag, its weight and type, and 114 search terms.
- `evidence/<key>_numbered.md` is the whole policy, with every sentence numbered (`p042.s2`).
- `evidence/<key>_evidence.md` / `.json` give, per flag, every search term with its hit count (zeros included) and the candidate sentences with their heading and neighbouring sentences. They contain no labels.
- `annotations/labels_<annotator>.csv` is the labelling sheet. `validate_labels.py` enforces the guideline rules and writes `labels_<annotator>_resolved.json`, filling in the exact sentence text and offsets from the snapshot. Quotes are always resolved from sentence IDs, so they cannot be invented.

## Step 3: reference labels (protocol changed 14 Nov 2026)

`annotations/labels_A1.csv` was pre-filled by an LLM from a different model family than the system under test (Claude, recorded in the `drafted_by` column) and then reviewed row by row by the author. `ANNOTATION_GUIDELINES.md` section 6 describes the protocol and its limitations, and section 7 logs every reviewer ruling.

Final tally: **117 verified, 10 edited, 113 accepted, 0 pending**. All 100 borderline rows were reviewed individually; the 113 accepted rows passed a random 25-row spot-check (seed 42, `annotations/spotcheck_A1.json`) with 0 label changes.

```bash
.venv/bin/python -I gold_set/validate_labels.py --annotator A1     # 240 rows, 0 errors
.venv/bin/python -I gold_set/spotcheck_sample.py                   # draws the sample once; never redraws
```

There is a single annotator, so no inter-annotator agreement is reported.

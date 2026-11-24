# PrivaScore

PrivaScore reads a privacy policy and reports what it says about 16 privacy practices, such as selling data for advertising, training AI models on user content, or how long data is kept. Every finding is backed by quotes that are checked word for word against the policy text. The findings are then combined into two transparent 0–100 scores: a **Privacy Risk Index** and a **Disclosure Quality** score.

It was built as a 5th-semester mini project (ECE, LNMIIT).

**Current state:** the analysis pipeline, a 15-policy evaluation set and the supporting classifier experiments are complete. Everything runs from the command line; there is no web interface yet.

## What it reports for each policy

- **For each of the 16 flags:** one of five evidence states, with quotes and the IDs of the sentences they come from.
- **Privacy Risk Index** (0 = lowest risk): how much exposure the policy describes.
- **Disclosure Quality** (0 = says nothing usable): how clearly the policy addresses the 16 flags.
- **Descriptive metrics**, shown next to the scores and never mixed into them: readability, vague-wording cues, and a 10-category profile from a fine-tuned BERT classifier.

## How it works

```
policy text
  → numbered sentences (p042.s2, ...)                                privascore/text.py
  → candidate sentences per flag, found with search terms            gold_set/flag_definitions.json
  → LLM: state + evidence [{sentence id, quote}] per flag            privascore/extractor.py (Gemini or Groq)
  → quote check: every quote must occur in the sentence it cites     privascore/verifier.py
  → Privacy Risk Index + Disclosure Quality                          privascore/scoring.py
```

- A quote counts only if it occurs **verbatim** in its cited sentence, allowing only for differences in Unicode, quote marks, dashes, case and whitespace. Fuzzy matches are never accepted. An answer that fails is retried once with the problems listed; if it still fails, the flag is marked for review and scored as Unclear.
- The LLM returns structured JSON only and has no tools; the policy text is treated as data, not as instructions.
- Every LLM reply is cached by prompt hash in `.cache/llm/`, so re-running a run costs nothing.

## The 16 flags

| ID | What it asks | Type | Weight |
|---|---|---|---:|
| G1 | What personal data does the company itself collect? | exposure | 1 |
| G2 | Does it sell data, or share it for advertising and tracking? | exposure | 3 |
| G3 | Does it build profiles or make automated decisions about users? | exposure | 2 |
| G4 | How specific are the retention periods? | governance | 2 |
| G5 | Can users access, correct and delete their data, and which users? | governance | 2 |
| G6 | Is data transferred abroad, and are safeguards named? | exposure | 1 |
| G7 | What age threshold and safeguards apply to children? | governance | 2 |
| AI1 | Is user data or content used to train AI models? | exposure | 3 |
| AI2 | Can users opt out of that training? (only applies if AI1 does) | governance | 2 |
| AI3 | Can people (staff, contractors, reviewers) read user content? | exposure | 2 |
| AI4 | Can de-identified or aggregated data be kept, used or shared? | exposure | 2 |
| AI5 | Is user content sent to outside AI providers or licensed for training? | exposure | 2 |
| DPDP1 | Is consent an affirmative action, or browsewrap ("by using the site...")? | readiness | 2 |
| DPDP2 | Is withdrawing consent as easy as giving it? | readiness | 2 |
| DPDP3 | Is a Grievance Officer or Data Protection Officer named, with contact details? | readiness | 1 |
| DPDP4 | Is the notice available in Indian languages? | informational | 0 |

The DPDP flags check readiness against India's Digital Personal Data Protection Act 2023 and its Rules. They are not a legal compliance verdict. The full definitions and search terms are in [`gold_set/flag_definitions.json`](gold_set/flag_definitions.json) and [`gold_set/ANNOTATION_GUIDELINES.md`](gold_set/ANNOTATION_GUIDELINES.md).

## Evidence states and scores

| State | Meaning |
|---|---|
| **ED**, explicitly disclosed | The policy clearly states the practice or right. |
| **CD**, conditionally disclosed | It exists, with conditions: an opt-out, a changeable default, a region or tier limit, or a purpose restriction. |
| **EE**, explicitly excluded | The policy says the practice does not happen, or denies the right. |
| **NS**, not stated | The policy says nothing usable about the flag. |
| **UN**, unclear | The policy addresses the flag, but the wording is contradictory or too vague to classify. |

**Privacy Risk Index** = 100 × Σ rᵢ / Σ wᵢ over the applicable flags, where rᵢ = f(state) × weight:

| State | Exposure flag | Governance / readiness flag |
|---|---:|---:|
| ED | 1.0 | 0.0 |
| CD | 0.5 | 0.5 |
| EE | 0.0 | 1.0 |
| UN | 0.5 | 0.5 |
| NS | 0.0 | 0.0 |

**Disclosure Quality** = 100 × Σ qᵢ / (2 × number of applicable flags), with q = 2 for ED and EE, 1.5 for CD, 0.5 for UN and 0 for NS.

- **"Not stated" never adds risk.** Silence lowers Disclosure Quality instead, so read the two scores together: a low Risk Index with low Quality means the policy says little, not that it is safe.
- DPDP4 (weight 0) is reported but not scored. AI2 is excluded from both scores when AI1 is not ED or CD.
- The weights are design choices. `weight_sensitivity()` and `ranking_stability()` in `privascore/scoring.py` show how much the scores and the policy ranking depend on them.

Both scores are rule-based indices. They are **not** probabilities that a company misuses data.

## Results

Full details, including the classifier experiments, are in [`experiments/README.md`](experiments/README.md).

**Extractor on the gold set** (15 policies: 5 AI services, 5 global apps, 5 Indian apps; 210 headline (policy, flag) pairs):

| Model | State accuracy (5 states) | Presence accuracy | Risk Index error | Ranking agreement (Kendall τ) |
|---|---:|---:|---:|---:|
| **gemini-3.6-flash** | **0.87** (95% CI 0.82–0.91) | **0.96** | 3.5 points | 0.72 |
| gemini-3.5-flash-lite | 0.73 (95% CI 0.67–0.79) | 0.92 | 6.2 points | 0.33 |

On the same pairs, 3.6-flash is right where 3.5-flash-lite is wrong 39 times; the reverse happens 10 times (sign test p = 3.8 × 10⁻⁵).

**BERT clause classifier** (`bert-base-uncased`, fine-tuned on OPP-115):

- OPP-115 test macro F1 **0.7665** (3 seeds) vs **0.7273** for TF-IDF + logistic regression. A paired policy-level bootstrap gives a 95% CI of [+0.011, +0.068] for the difference.
- On APP-350 Android app policies, which it never saw in training: 0.7715 vs 0.7446 on First / Third Party. The Third Party gain is supported; the overall difference is borderline (its CI includes 0).
- Training BERT on OPP-115 and APP-350 together (with a masked loss for APP-350's missing labels) raised First / Third Party F1 on held-out APP-350 policies by +0.078, but did not improve OPP-115 (−0.011, 95% CI [−0.028, +0.005]). The OPP-115-only model is kept, which also keeps APP-350 as an out-of-domain test.
- On the gold set, a pre-registered test found that BERT does not improve evidence retrieval enough to justify the larger prompts (+4.3 points of recall against a required +5). It is therefore used only as a descriptive category profile.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp privascore.example.toml privascore.toml     # choose the provider ("gemini" or "groq") and the model
cp .env.example .env                           # paste GEMINI_API_KEY (or GROQ_API_KEY); .env is git-ignored
.venv/bin/python -m privascore.llm.smoke        # one tiny call: checks the key, the model and JSON mode
```

Model names and free-tier limits change often; check them in your provider's console.

**Run the extractor** on the saved policy snapshots in `gold_set/policies/`:

```bash
.venv/bin/python -m privascore.extract --policies P01,P07 --provider mock   # dry run: no key, labels are meaningless
.venv/bin/python -m privascore.extract --policies P11 --run-name try1        # one real policy
.venv/bin/python -m privascore.extract --all --batch --run-name my_run       # all 15, one call per policy
.venv/bin/python -m privascore.evaluate --run runs/my_run                    # compare with the reference labels
```

Without `--batch` the extractor makes up to 16 calls per policy (one per flag). Flags with no matching sentence skip the LLM. Results go to `runs/<run-name>/`, one JSON file per policy plus `run.json`.

**Descriptive metrics and BERT** (needs `pip install -e ".[bert]"` and the checkpoint, see below):

```bash
.venv/bin/python -I -m privascore.bert --sanity        # checks the checkpoint reproduces its OPP-115 test score
.venv/bin/python -I -m privascore.metrics              # readability, vagueness, BERT profile → runs/policy_metrics/
.venv/bin/python -I -m privascore.metrics --no-bert    # readability and vagueness only (no torch needed)
.venv/bin/python -I -m privascore.bert_eval            # pre-registered BERT test on the gold set → runs/bert_eval/
```

**Tests** (no network, no API key):

```bash
.venv/bin/python -m pytest -q
```

### Reading a flag result

| `status` | Meaning |
|---|---|
| `verified` | every quote was found verbatim in its cited sentence |
| `verified_partial` | the label passed its checks; quotes that failed were dropped and listed in `dropped_evidence` |
| `absent_unverifiable` | the LLM said Absent; the search log is attached, because absence cannot be proven |
| `no_candidates` | no sentence matched the search terms, so the flag is Absent without an LLM call |
| `not_applicable` | AI2 when AI1 is not ED or CD |
| `rejected` | no verified answer after the retry; scored as UN, and the policy's scores are marked `complete: false` |

## BERT checkpoint

The BERT features use the seed-44 run in `models/Bert_seed_44/`. The repository holds its `result.json` and saved probabilities. The weights (`checkpoint-1134/`, 418 MB) are not stored in git: place that folder in `models/Bert_seed_44/checkpoints/`, then run `privascore.bert --sanity`. The training code is in [`experiments/03_bert_opp115/`](experiments/03_bert_opp115/).

## Data

- **OPP-115** (Wilson et al., ACL 2016) and **APP-350** (Zimmeck et al., PETS 2019) come from the Usable Privacy Policy Project ([usableprivacy.org](https://usableprivacy.org)). They may be used for non-commercial research, teaching and scholarship only, and publications that use them must cite the papers above. To re-run the experiments, unzip them into `data/raw/` (git-ignored).
- `data/opp115/` holds the policy-level train / validation / test splits derived from OPP-115, under the same terms. The combined OPP-115 + APP-350 splits are regenerated into `data/combined/` (git-ignored).
- `gold_set/policies/` holds snapshots of 15 public privacy policies, fetched on 12 November 2026 so that every label can be checked against the exact text. Each policy remains the property of its publisher.

## License

The code is released under the [MIT License](LICENSE).

The MIT License covers the code only. It does not cover the datasets:

- **OPP-115 and APP-350** may be used for **non-commercial research, teaching and scholarship only**, under the terms of the Usable Privacy Policy Project. The same applies to everything in this repository derived from them: the splits in `data/opp115/`, the experiment outputs, and the BERT probabilities and checkpoint, which were trained on OPP-115.
- **The policy snapshots** in `gold_set/policies/` remain the property of their publishers and are included only so that the evaluation can be checked.

## Repository layout

```
privascore/            the pipeline: text, flags, extractor, verifier, scoring, evaluation, metrics, BERT
  llm/                 Gemini, Groq and mock clients
tests/                 unit tests (no network, no API key)
gold_set/              policy snapshots, flag definitions, annotation guidelines, reference labels
runs/                  saved extractor runs and evaluations, the BERT gold-set test, policy metrics
experiments/           classifier experiments on OPP-115 and APP-350 (see experiments/README.md)
data/opp115/           OPP-115 splits
models/Bert_seed_44/   seed-44 BERT run (weights downloaded separately)
LICENSE                MIT, for the code only (see License)
```

## Limitations

- **Small reference set.** 15 policies and a single annotator, so there is no inter-annotator agreement. The reference labels were pre-filled by an LLM from a different model family than the extractor (Claude) and then reviewed row by row by the author: 117 verified, 10 edited, and 113 accepted after a random spot-check. This can bias the labels towards the pre-fill. See [`gold_set/ANNOTATION_GUIDELINES.md`](gold_set/ANNOTATION_GUIDELINES.md), section 6.
- **LLM output varies.** Re-running gemini-3.5-flash-lite with identical prompts changed 14% of the states. Accuracy stayed the same, but the policy ranking did not.
- **BERT was trained on 2016 website policies.** Its calibration gets worse on other data, and its confidence does not drop when that happens. Its probabilities are never shown as confidence about a policy.
- **Results describe a snapshot.** Policies change, and the DPDP checks describe readiness, not legal compliance.

## References

- S. Wilson et al. *The Creation and Analysis of a Website Privacy Policy Corpus.* ACL 2016. (OPP-115)
- S. Zimmeck et al. *MAPS: Scaling Privacy Compliance Analysis to a Million Apps.* PETS 2019. (APP-350)
- J. Bhatia, T. Breaux, J. Reidenberg, T. Norton. *A Theory of Vagueness and Privacy Risk Perception.* IEEE RE 2016. (vagueness categories)
- R. Flesch. *A New Readability Yardstick.* 1948; J. P. Kincaid et al. 1975. (readability formulas)

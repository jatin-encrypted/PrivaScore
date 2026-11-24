# Experiments

The classifier experiments behind PrivaScore, in the order they were run, followed by the evaluations of the full pipeline on the 15-policy gold set.

Rules applied to every experiment:

- Splits are made **by policy**, never by segment, so no policy appears in two splits.
- Everything (vectorizers, thresholds, model selection) is fitted on training or validation data only.
- **Macro F1** is the main metric, because the classes are very imbalanced.
- Label mappings between datasets were written down and approved before any model was trained on them.
- External tests use a fixed 0.5 threshold, with no tuning on the external data.

| # | Experiment | Main result |
|---|---|---|
| 00 | [OPP-115 data preparation](#00-opp-115-data-preparation) | 3,791 segments, 10 classes, 80 / 17 / 18 policies |
| 01 | [TF-IDF baseline](#01-tf-idf--logistic-regression-baseline) | test macro F1 **0.7273** |
| 02 | [Adding APP-350 to the training data](#02-adding-app-350-to-the-training-data) | TF-IDF: does not help (best 0.7243) |
| 03 | [BERT fine-tuning](#03-bert-fine-tuning-on-opp-115) | test macro F1 **0.7665** (3-seed mean) |
| 04 | [Paired bootstrap](#04-is-bert-really-better-paired-policy-bootstrap) | BERT − TF-IDF +0.039, 95% CI [+0.011, +0.068] |
| 05 | [APP-350 external test](#05-external-test-on-app-350-android-app-policies) | 0.7715 vs 0.7446 on First/Third Party; CI includes 0 |
| 06 | [Calibration under domain shift](#06-calibration-under-domain-shift) | calibrated in-domain; worse on APP-350, with no drop in confidence |
| 07 | [BERT on OPP-115 + APP-350](#07-bert-trained-on-opp-115--app-350-masked-loss) | OPP-115: 0.7553, no gain (−0.011, CI [−0.028, +0.005]); APP-350: +0.078. Not adopted |
| P1 | [LLM extractor on the gold set](#p1-llm-extractor-on-the-gold-set) | gemini-3.6-flash: state accuracy **0.87** |
| P2 | [BERT on the gold set (pre-registered)](#p2-bert-on-the-gold-set-pre-registered) | rule not met: BERT kept as a standalone profiler |

Commands below are run from the repository root. BERT training (03, 07) and the BERT half of 05 need a GPU (they were run on Google Colab); everything else runs on a laptop CPU.

---

## 00. OPP-115 data preparation

**Data:** OPP-115 (Wilson et al., ACL 2016): 115 website privacy policies annotated by three annotators each. Download `OPP-115_v1_0.zip` from usableprivacy.org into `data/raw/` and unzip it there.

- OPP-115 is distributed as CSV. Using the 0.75-overlap consolidation gives **3,791 labelled segments**; about 48% carry two or more labels, so the task is **multi-label**.
- Segments per class: First Party Collection/Use 1,521 · Third Party Sharing/Collection 1,186 · User Choice/Control 632 · User Access, Edit and Deletion 231 · Data Retention 156 · Data Security 375 · Policy Change 192 · **Do Not Track 32** · International and Specific Audiences 353 · Other 1,762.
- Policy-level split, seed 42, 70 / 15 / 15: **80 / 17 / 18 policies**, **2,582 / 627 / 582 segments**. Test supports per class: 262, 205, 123, 50, 27, 47, 31, **5**, 72, 268.

Do Not Track has only 5 test examples (and 4 in validation), so its F1 is never used as evidence.

```bash
python experiments/00_opp115_data/parse_opp115.py --corpus-dir data/raw/OPP-115 --out opp115_clean.jsonl --label-map-out opp115_label_map.json
python experiments/00_opp115_data/split_and_encode.py --in opp115_clean.jsonl --label-map opp115_label_map.json --out-dir <dir>
```

Run on the official zip, these two scripts reproduce the four files in `data/opp115/` byte for byte. `opp115_clean.jsonl` is also the OPP-115 input to experiment 02.

---

## 01. TF-IDF + Logistic Regression baseline

**Question:** what does a simple linear model score? This is the number BERT has to beat. It was fixed before BERT was trained and has not been changed since.

**Setup:** `TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english", min_df=2)` fitted on training text only, then `OneVsRestClassifier(LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))`.

| Split | Macro F1 |
|---|---:|
| Train | 0.9022 |
| Validation | 0.7251 |
| **Test** | **0.7273** |

Per-class test F1: First Party .77 · Third Party .83 · User Choice .59 · User Access .67 · **Data Retention .49** · Data Security .63 · Policy Change .79 · Do Not Track 1.00 (n = 5) · International .75 · Other .75.

```bash
python experiments/01_tfidf_baseline/baseline_tfidf.py --data-dir data/opp115 --label-map data/opp115/opp115_label_map.json
```

Files: `baseline_tfidf.py`, `baseline_results.txt` (original output).

---

## 02. Adding APP-350 to the training data

**Question:** does adding APP-350 (Zimmeck et al., PETS 2019; 350 Android app policies) improve the OPP-115 classifier?

**Mapping** (approved before training). APP-350 annotates practices as `DataType_Party` with a separate `PERFORMED` / `NOT_PERFORMED` modality, so only two OPP-115 classes can be mapped:

| APP-350 | OPP-115 |
|---|---|
| `*_1stParty` | First Party Collection/Use |
| `*_3rdParty` | Third Party Sharing/Collection |
| `SSO`, `Facebook_SSO` | excluded (party is ambiguous) |
| unannotated segments | excluded |
| the other 8 OPP-115 classes | no coverage possible |

`PERFORMED` and `NOT_PERFORMED` map to the same topic label; the original modality is kept in `modality_detail`. Result: 3,937 mapped segments (2,973 First Party only, 535 Third Party only, 429 both).

**Split:** OPP-115 keeps its original split, so all results below are measured on the **same 18 OPP-115 test policies**. APP-350 is split 245 / 53 / 52 policies; 142 APP-350 policies contain hand-edited synthetic negations, so test policies are drawn only from the non-synthetic ones. Combined segments: train 5,308 (2,582 OPP-115 + 2,726 APP-350), validation 1,176 (627 + 549), test 1,244 (582 + 662).

| Variant (TF-IDF + LogReg) | OPP-115 test macro F1 |
|---|---:|
| OPP-115 only (experiment 01) | **0.7273** |
| Naive combined | 0.7006 |
| Fix A: vectorizer fitted on OPP-115 text only | 0.6995 |
| **Fix B: per-label masking** (APP-350 rows train only the First / Third Party classifiers) | **0.7243** |
| Fix B with the vectorizer fitted on combined text | 0.7125 |

**Why naive combining hurt:** `OneVsRestClassifier` trained all 10 per-label classifiers on the APP-350 rows. For the 8 classes APP-350 never annotates, its 2,726 training rows became negatives that carry no real information. Masking them out (the `label_mask` field) almost closes the gap. What remains is a small drop in Third Party F1 (0.83 → 0.80); First Party is unchanged.

The combined test macro F1 over all rows (0.6429) is not a fair number: APP-350 rows can never be positive on 8 of the 10 classes, which drags the macro average down.

**Conclusion:** combining does not improve the OPP-115 TF-IDF classifier. The BERT model in experiment 03 was therefore trained on OPP-115 only, and APP-350 was used as an external test set (experiment 05). A later BERT run on the combined data, with the same masking built into the loss, is experiment 07.

```bash
python experiments/02_combined_app350/parse_app350_to_opp115.py --corpus-dir data/raw/APP-350_v1.1 --label-map data/opp115/opp115_label_map.json
python experiments/02_combined_app350/split_combined.py --opp115-clean opp115_clean.jsonl --app350-mapped app350_mapped.jsonl \
       --app350-policy-meta app350_policy_meta.json --label-map data/opp115/opp115_label_map.json --out-dir data/combined
python experiments/02_combined_app350/baseline_tfidf_combined.py --data-dir data/combined --label-map data/opp115/opp115_label_map.json
python experiments/02_combined_app350/train_combined_masked.py   --data-dir data/combined --label-map data/opp115/opp115_label_map.json
```

Files: the four scripts above, `app350_to_opp115_mapping.json`, `combined_label_distribution.json`, and the original outputs `baseline_combined_results.txt` and `train_combined_masked_results.txt`. Fix A and the combined-vectorizer variant were one-off runs; their script is not included. The combined `.jsonl` files are not stored in git; `split_combined.py` regenerates them into `data/combined/` (git-ignored). The experiment 07 files are in this folder too, because they use the same combined split.

---

## 03. BERT fine-tuning on OPP-115

**Question:** does a fine-tuned transformer beat the TF-IDF baseline?

| Setting | Value |
|---|---|
| Model | `bert-base-uncased`, 10 sigmoid outputs (multi-label), `BCEWithLogitsLoss` |
| Class weights | `pos_weight = sqrt(neg / pos)` per class (1.1 to 10.5; fully balanced would give about 111 for Do Not Track) |
| Input length | 256 tokens (95th percentile of segment length is about 163 words) |
| Optimiser | lr 2e-5, batch 16, weight decay 0.01, 10% warm-up then linear decay, fp16 on GPU |
| Schedule | up to 8 epochs, early stopping (patience 3) on validation macro F1 |
| Seeds | 42, 43, 44 |
| Threshold | 0.5 for every class |

| | Seed 42 | Seed 43 | Seed 44 | **Mean** |
|---|---:|---:|---:|---:|
| Validation macro F1 | 0.7765 | 0.7922 | 0.7849 | 0.7845 |
| **Test macro F1** | 0.7591 | 0.7620 | 0.7785 | **0.7665** (sample std 0.0105) |

- **+0.0392 absolute (+5.4% relative)** over TF-IDF. Experiment 04 checks whether this is more than test-set noise.
- Per-class thresholds tuned on validation did **not** help (test 0.7636 vs 0.7665), so 0.5 stays.
- Per-class test F1, BERT / TF-IDF: First .81 / .77 · Third .89 / .83 · User Choice .60 / .59 · User Access .70 / .67 · Retention .53 / .49 · Security .70 / .63 · Policy Change .79 / .79 · Do Not Track 1.00 / 1.00 · **International .89 / .75** · Other .77 / .75.

**A bug found and fixed along the way.** Training logs warned about missing `LayerNorm.weight/bias` and unexpected `LayerNorm.gamma/beta` keys. In Transformers 5.x, `Trainer` saves checkpoints with the original `gamma`/`beta` names, but `load_best_model_at_end` reloads them with `load_state_dict(strict=False)` and no renaming. As a result, the LayerNorm parameters silently kept their **last-epoch** values while every other parameter came from the best epoch. `train_bert_opp115.py` now reloads the best checkpoint with `from_pretrained()` (which does rename) before predicting. After the fix, the reported validation F1 equals the logged best-epoch value exactly for all three seeds. The effect before the fix was small (at most 0.0002), and the numbers above come from the corrected run. `verify_best_checkpoint.py` checks the checkpoint files directly.

Environment of the reported run: Colab GPU, torch 2.14.1, transformers 5.22.1. Only the seed-44 run is kept in the repo (`models/Bert_seed_44/`: `result.json` and the train / validation / test probabilities). Its 418 MB checkpoint (`checkpoint-1134`) is stored outside git.

```bash
python experiments/03_bert_opp115/train_bert_opp115.py --data-dir data/opp115 --label-map data/opp115/opp115_label_map.json \
       --out-dir bert_runs --seeds 42,43,44                      # GPU
python experiments/03_bert_opp115/smoke_test_bert_pipeline.py data/opp115   # tiny random BERT, CPU, checks the training script runs end to end
```

---

## 04. Is BERT really better? Paired policy bootstrap

**Question:** with only 18 test policies, could the +0.039 gain be test-set noise?

**Method:** segments from one policy are not independent, so the bootstrap resamples **policies** (20,000 draws of 18 policies with replacement) and scores both systems on the same resample. The full-test scores reproduce 0.7591 / 0.7620 / 0.7785 / 0.7273 exactly.

| Comparison | Difference | 95% CI | P(BERT > TF-IDF) |
|---|---:|---|---:|
| **BERT 3-seed mean − TF-IDF** | **+0.0392** | **[+0.0109, +0.0677]** | 0.996 |
| Seed 42 − TF-IDF | +0.0318 | [+0.0023, +0.0644] | 0.982 |
| Seed 43 − TF-IDF | +0.0347 | [+0.0053, +0.0642] | 0.989 |
| Seed 44 − TF-IDF | +0.0512 | [+0.0208, +0.0789] | 0.999 |

- Relative gain +5.4%, 95% CI [+1.4%, +9.8%]; P(gain ≥ 5%) = 0.58. The +5% project target is **not** reliably met.
- Per class, the CI excludes zero for three classes only: **International** +0.137 [+0.039, +0.220], **Third Party** +0.059 [+0.023, +0.097] and **First Party** +0.039 [+0.004, +0.081]. Data Security and Data Retention point the same way, but their CIs include zero.
- Per policy, BERT makes fewer label errors in 14 of 18 policies, ties in 1 and loses in 3 (sign test p ≈ 0.013). Three policies account for 58% of the net error reduction.

**Conclusion:** BERT is reliably better than TF-IDF on OPP-115, by a modest margin.

```bash
python experiments/04_paired_bootstrap/paired_bootstrap.py --probs-dir <dir with seed_42/ seed_43/ seed_44/test_probs.npy> --data-dir data/opp115
```

The repo only contains the seed-44 probabilities, so a full re-run needs the seed 42 and 43 files from the training run. Files: `paired_bootstrap.py`, `paired_bootstrap_output.txt`, `paired_bootstrap_results.json`.

---

## 05. External test on APP-350 (Android app policies)

**Question:** do classifiers trained only on OPP-115 (2016 website policies) still separate first-party from third-party data collection in a different corpus? Neither model saw APP-350 during training.

**Design:** the three existing BERT checkpoints (not retrained) against the OPP-115-only TF-IDF model; fixed threshold 0.5; **First Party and Third Party only** (BERT's other 8 outputs are ignored, so there is no 10-class score). The test set is the 52 held-out, non-synthetic APP-350 test policies from experiment 02, re-derived from the raw YAML.

- **Evaluation population:** 51 policies, **662 annotated segments** (1,745 unannotated and 23 SSO-only segments excluded). First Party positives 557 (**84.1%**), Third Party 185 (27.9%).
- **Label rule:** inside an annotated segment, a class is negative if no practice of that party is annotated. Recall needs no assumption about negatives; precision and F1 depend on this rule.
- **Mapping is operational, not an equivalence:** APP-350 "third party" means ad and analytics SDKs only, so a correct prediction of, say, partner sharing is scored as wrong. Third Party precision is therefore a lower bound.
- **Checks:** labels re-derived from the raw YAML match the combined split for 662 of 662 rows; TF-IDF reproduces 0.7273 on OPP-115 before use; each BERT checkpoint re-scores OPP-115 test exactly before producing APP-350 probabilities; the evaluation file's sha256 is checked so the row order cannot drift.

| System | First P | First R | First F1 | Third P | Third R | Third F1 | **Macro F1** |
|---|---:|---:|---:|---:|---:|---:|---:|
| TF-IDF (OPP-115 only) | 0.868 | 0.813 | 0.840 | 0.621 | 0.681 | 0.649 | **0.7446** |
| BERT seed 42 | 0.918 | 0.767 | 0.836 | 0.717 | 0.714 | 0.715 | 0.7755 |
| BERT seed 43 | 0.910 | 0.747 | 0.821 | 0.747 | 0.686 | 0.715 | 0.7680 |
| BERT seed 44 | 0.920 | 0.763 | 0.834 | 0.702 | 0.714 | 0.708 | 0.7710 |
| **BERT mean of 3 seeds** | 0.916 | 0.759 | 0.830 | 0.722 | 0.705 | 0.713 | **0.7715** |
| Predict "yes" for everything | 0.841 | 1.000 | 0.914 | 0.279 | 1.000 | 0.437 | 0.6753 |

Threshold-free AUC: First Party 0.715 (TF-IDF) vs 0.767 (BERT); Third Party 0.840 vs 0.860.

Paired policy bootstrap (20,000 draws over 51 policies), BERT mean minus TF-IDF:

| Metric | Difference | 95% CI | P(> 0) |
|---|---:|---|---:|
| First Party F1 | −0.010 | [−0.022, +0.008] | 0.12 |
| **Third Party F1** | **+0.063** | **[+0.010, +0.125]** | 0.99 |
| Macro F1 (2 classes) | +0.027 | [−0.001, +0.060] | 0.97 |
| **First Party AUC** | **+0.052** | **[+0.006, +0.091]** | 0.99 |
| Third Party AUC | +0.020 | [−0.018, +0.059] | 0.85 |

**Conclusion:** on APP-350, BERT is at least as good as TF-IDF and probably somewhat better. The macro-F1 gain is **borderline** (its CI just includes zero). Two results are clearly supported: Third Party F1 at 0.5, and First Party ranking quality (AUC). No metric shows BERT worse. Both models score **below** the predict-everything reference on First Party F1, because 84% of segments are positive, so First Party F1 says little on its own here.

```bash
# 1. build and verify the evaluation set (CPU). --outputs-dir must contain split_combined.py,
#    combined_test.jsonl and the opp115_*.jsonl files from experiment 02.
python experiments/05_app350_external/build_app350_eval_set.py --app350-dir data/raw/APP-350_v1.1 --outputs-dir <dir> --out-dir <out>
# 2. BERT probabilities from the existing checkpoints (GPU)
python experiments/05_app350_external/predict_bert_external.py --eval-set experiments/05_app350_external/app350_external_eval.jsonl \
       --opp115-test data/opp115/opp115_test.jsonl --runs-dir bert_runs --out-dir bert_external
# 3. metrics and paired bootstrap (CPU)
python experiments/05_app350_external/evaluate_app350_external.py --eval-dir experiments/05_app350_external \
       --bert-dir experiments/05_app350_external/bert_external --outputs-dir data/opp115 --out-prefix app350_external
```

Files: the three scripts, `app350_external_eval.jsonl` and its manifest, `bert_external/` (the BERT probabilities for seeds 42 to 44, plus metadata), and the original TF-IDF output (`app350_external_tfidf_only_output.txt` / `.json`). See also the reproducibility note below.

---

## 06. Calibration under domain shift

**Question:** can BERT's output probabilities be read as confidence, and does that still hold on new data?

Computed from the saved 3-seed probabilities, First and Third Party only. (This was a one-off calculation and is not saved as a script.)

| Dataset | Class | Prevalence | Mean p | ECE | Brier | Mean confidence |
|---|---|---:|---:|---:|---:|---:|
| OPP-115 test | First Party | 0.450 | 0.412 | 0.041 | 0.115 | 0.845 |
| OPP-115 test | Third Party | 0.352 | 0.348 | 0.046 | 0.061 | 0.895 |
| APP-350 | First Party | 0.841 | 0.685 | **0.159** | 0.185 | 0.857 |
| APP-350 | Third Party | 0.279 | 0.324 | 0.061 | 0.125 | 0.871 |

**Conclusion:** BERT is well calibrated in-domain. On APP-350, First Party calibration error roughly quadruples, while the model's confidence barely changes (0.85 → 0.86): **it does not signal that it is out of its depth.** Part of the gap comes from the prevalence shift (45% → 84%) and the narrower label definition, so this is suggestive rather than conclusive. As a result, PrivaScore never shows BERT probabilities as "confidence" or as the probability that a policy is risky.

---

## 07. BERT trained on OPP-115 + APP-350 (masked loss)

**Question:** in experiment 02, masking fixed the problem with combining the two datasets for TF-IDF. Does a BERT model trained on both datasets, with the same masking, beat the OPP-115-only BERT from experiment 03?

**Setup:** the recipe from 03 (a fresh `bert-base-uncased`, 256 tokens, lr 2e-5, batch 16, up to 8 epochs, patience 3, seeds 42 / 43 / 44, threshold 0.5), trained on the combined split from 02: 5,308 training segments (2,582 OPP-115 + 2,726 APP-350). Three things change:

- **Masked loss.** The per-label BCE is multiplied by `label_mask` and averaged over annotated entries only. APP-350 rows therefore train only the First and Third Party outputs; their 8 unannotated labels add zero loss and zero gradient. `--self-test` checks these properties before training.
- `pos_weight` is counted only over rows where that label is annotated.
- Early stopping uses mask-aware validation macro F1 over all validation rows (OPP-115 and APP-350). Only the probabilities were saved, not the checkpoints.

The test rows are the same as before, and the script asserts this: OPP-115 test = the 582 segments / 18 policies of experiments 01 and 03; APP-350 test = the 662 segments / 51 policies of the external test in 05.

| Test set | BERT, OPP-115 only | BERT, combined (seeds 42 / 43 / 44) | Difference | 95% CI | P(Δ > 0) |
|---|---:|---:|---:|---|---:|
| OPP-115, 10-class macro F1 | 0.7665 | 0.7553 (0.7547 / 0.7590 / 0.7521) | **−0.011** | [−0.028, +0.005] | 0.08 |
| APP-350, First / Third Party macro F1 | 0.7715 (never saw APP-350) | 0.8493 (0.8533 / 0.8417 / 0.8528) | **+0.078** | [+0.064, +0.091] | 1.000 |

Differences are 3-seed means; intervals come from the paired policy bootstrap of experiment 04 (20,000 draws). P(Δ > 0) is the share of draws in which the combined model scores higher. It is not a p-value: 1.000 means all 20,000 draws favoured the combined model.

- **OPP-115: no improvement.** The point estimate is slightly negative and the interval includes zero. No per-class interval excludes zero; the largest drops (User Choice −0.034, Policy Change −0.030) are within noise. The OPP-115-only model makes fewer label errors in 10 of the 18 test policies, the combined model in 5, with 3 ties. Against TF-IDF, the combined model is +0.028 [−0.000, +0.055], a weaker margin than the OPP-115-only model's +0.039 [+0.011, +0.068]. Per-class thresholds tuned on validation give 0.7572, so they don't change this.
- **APP-350: a large gain on both classes.** First Party +0.080 [+0.064, +0.095], Third Party +0.076 [+0.048, +0.103]. The combined model makes fewer errors in 41 of 51 policies and more in 3. This is an **in-domain** result: the combined model was trained on 245 other APP-350 policies with the same label definitions, while the 0.7715 model never saw any.

**Decision: PrivaScore keeps the OPP-115-only BERT (0.7665, experiment 03).**

1. **No gain on the task PrivaScore uses BERT for.** PrivaScore uses BERT as a 10-category profiler of whole policies. On that 10-class task, combined training gives no measurable improvement and a slightly lower point estimate. The APP-350 gain covers 2 of the 10 categories. In exchange, training needs about twice as many steps per epoch (332 vs 162), a custom loss and a mask-aware validation metric.
2. **It would use up the external test.** Once APP-350 is in the training data, APP-350 results are in-domain. The 662 test rows still come from held-out policies, but they no longer measure how well the model carries over to a different kind of policy, and the project has no other labelled out-of-domain set. With the OPP-115-only model, experiments 05 and 06 stay genuine out-of-domain checks.
3. **Missing labels need special handling in a neural model.** APP-350 annotates only 2 of the 10 classes. TF-IDF trains a separate classifier per class, so the unannotated rows can simply be left out of those 8 classifiers (Fix B in 02). BERT predicts all 10 classes from one shared encoder, so a row cannot be left out for some classes only: the missing labels have to be masked inside the loss. With a plain BCE loss they would count as confirmed negatives, the same contamination that pulled naive TF-IDF combining from 0.7273 to 0.7006. Even with masking, APP-350 rows still update the shared encoder that the other 8 classes rely on. That may explain the small drop on OPP-115, but it was not tested.

```bash
python experiments/02_combined_app350/train_bert_combined_masked.py --self-test      # CPU, a few seconds: checks the masked loss
python experiments/02_combined_app350/train_bert_combined_masked.py --data-dir data/combined \
       --label-map data/opp115/opp115_label_map.json --out-dir bert_combined_runs --seeds 42,43,44     # GPU
# --data-dir must contain opp115_{train,test}.jsonl, opp115_label_map.json, combined_test.jsonl and app350_external_eval.jsonl
python experiments/02_combined_app350/paired_bootstrap_combined.py --combined-dir experiments/02_combined_app350/bert_combined_runs \
       --opp-only-probs-dir <dir with seed_42/ seed_43/ seed_44/test_probs.npy> \
       --external-probs-dir experiments/05_app350_external/bert_external --data-dir <dir>
```

Files (in `02_combined_app350/`): `train_bert_combined_masked.py`, `bert_combined_runs/` (run config, summary, test-row metadata, and for each seed `result.json` plus validation and test probabilities), `paired_bootstrap_combined.py` and its original output `paired_bootstrap_combined_output.txt`. As in 04, a full re-run of the bootstrap needs the seed 42 and 43 probabilities of the OPP-115-only model.

---

## P1. LLM extractor on the gold set

**Question:** how well does the LLM extractor (`privascore.extract`) reproduce the reference labels of the 15-policy gold set, and which model should be the main extractor?

Each run labels 240 (policy, flag) pairs with one of five evidence states. Headline numbers use **210 pairs**: G1 is left out because it is almost always ED, and DPDP4 because it has weight 0. The gold labels are described in [`gold_set/`](../gold_set/README.md).

| Run (`runs/…`) | Model | Prompt rules | State accuracy | Presence accuracy | Macro F1 (states) | Risk Index error | Quality error | Kendall τ (ranking) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `gemini35lite_batch_v1` | gemini-3.5-flash-lite | v1.0 | 0.72 (151/210) | 0.93 | 0.74 | 8.3 | 5.3 | 0.15 |
| `gemini35lite_batch_v1.1` | gemini-3.5-flash-lite | v1.1 | 0.73 (154/210) | 0.92 | 0.75 | 6.2 | 4.7 | 0.33 |
| `gemini35lite_batch_v1.1_rerun1` | gemini-3.5-flash-lite | v1.1 | 0.73 (154/210) | 0.93 | 0.77 | 5.1 | 5.7 | 0.49 |
| **`gemini36_batch_v1.1`** | **gemini-3.6-flash** | v1.1 | **0.87 (183/210)** | **0.96** | **0.81** | **3.5** | **3.8** | **0.72** |

Errors are mean absolute differences in points (0 to 100) between the scores computed from predicted and from reference labels. 95% Wilson intervals: 3.6-flash 0.82 to 0.91, 3.5-flash-lite v1.1 0.67 to 0.79.

- **3.6-flash is clearly better.** On the 210 headline pairs it is right where 3.5-flash-lite is wrong 39 times, and the reverse happens 10 times (sign test p = 3.8 × 10⁻⁵). It is the main extractor. It made 2 false "Not stated" calls out of 170 addressed pairs, and 0 answers were rejected by the quote verifier.
- **The v1.1 prompt rules did not measurably help** the smaller model: 23 pairs improved and 20 got worse (p = 0.76).
- **Identical reruns are not identical:** re-running 3.5-flash-lite with the same prompts changed the state of 33 of 240 pairs (14%). Accuracy stayed the same, but the policy ranking moved (τ 0.33 → 0.49). Single-run rankings from a small model should not be trusted.
- Every run reports 95% intervals; per-flag numbers rest on 15 items each.

```bash
python -m privascore.evaluate --run runs/gemini36_batch_v1.1      # → evaluation.json / evaluation.md in the run folder
```

---

## P2. BERT on the gold set (pre-registered)

**Question:** can the OPP-115 BERT help the extractor find evidence sentences in modern policies?

The flag → OPP-115 class mapping, the 0.5 threshold and the decision rule were written down **before** any result was seen:

> Use BERT as a retrieval booster only if it raises evidence recall on the four strongly-mapped flags (G1, G2, G4, G5) by **at least 5 points** while adding **at most 25%** more sentences to the prompt. Otherwise keep BERT as a standalone category profiler.

A sanity gate first re-scores OPP-115 test with the seed-44 checkpoint: 0.7785 stored, 0.7785 rescored, 0 label flips.

| | Keyword recall | Keywords + BERT (within budget) | Extra sentences |
|---|---:|---:|---:|
| Strong flags (185 evidence sentences) | 0.816 | 0.859 (**+4.3 pts**) | 22.0% |

**Outcome: the rule is not met**, so BERT is not integrated into retrieval. It is reported as a standalone 10-category profile of each policy (`runs/policy_metrics/`), next to the scores and never inside them. Because the reference evidence was first drafted from the keyword packets, keyword recall is optimistic and BERT's recall is a lower bound.

```bash
python -I -m privascore.bert --sanity      # sanity gate only
python -I -m privascore.bert_eval          # tests A to C → runs/bert_eval/
```

---

## Reproducibility note: library versions

Re-running the scikit-learn experiments with scikit-learn 1.9.1 (newer than the version originally used) gives slightly different TF-IDF numbers. BERT numbers do not change, because they come from saved probabilities.

| Number | Original | Re-run (scikit-learn 1.9.1) |
|---|---:|---:|
| 01: OPP-115 test macro F1 | 0.7273 | 0.7271 |
| 02: naive combined, OPP-115 rows | 0.7006 | 0.7008 |
| 02: Fix B (masking) | 0.7243 | 0.7244 |
| 05: TF-IDF macro F1 on APP-350 | 0.7446 | 0.7389 |
| 05: BERT − TF-IDF macro F1, 95% CI | [−0.001, +0.060] | [+0.004, +0.065] |

No conclusion in 01 to 04 changes. In 05, the macro-F1 interval moves just above zero with the newer library. A difference that depends on the library version is exactly what "borderline" means, so the conclusion stays as reported: the Third Party gain is supported, and the overall macro-F1 gain is not established.

## What these results do not show

- That the +5% target over TF-IDF was met: the interval runs from +1.4% to +9.8%.
- That BERT fixes Data Retention: the direction is positive, but the interval includes zero.
- That more training data helps BERT on OPP-115: adding APP-350 (07) did not, and the combined model's APP-350 gain is in-domain, not evidence of generalisation.
- Anything from Do Not Track F1: 5 test examples.
- That BERT works on modern AI-era policies: it was trained on 2016 website policies, and its only test on current policies is the gold-set profiling in P2.
- That APP-350 scores can be compared with OPP-115 10-class scores, or that BERT probabilities measure how risky a policy is.

All intervals cover test-set sampling only (18 OPP-115 policies, 51 APP-350 policies, 15 gold-set policies), not training variance beyond three seeds. With this few policies, percentile bootstrap intervals are slightly optimistic.

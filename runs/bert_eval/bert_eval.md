# Fine-tuned OPP-115 BERT on the 15-policy reference set (Tests A-C)

Sanity gate: OPP-115 test macro F1 stored 0.7785 / rescored 0.7785 (passed; 0 label flips vs stored test predictions).

Reference labels sha256 880e97c489df. LLM comparison: gemini35lite_batch_v1.1. Unmapped (not evaluated): AI1, AI3, AI4, DPDP4.

## Decision (pre-registered)

- Rule: >= 5.0 pp recall gain on G1,G2,G4,G5 with <= 25% extra sentences
- Measured (budgeted booster): **+4.3 pp** recall, **22.0%** extra sentences
- Outcome: **STANDALONE profiler (do not integrate as booster)**

## A. Presence (addressed vs not addressed)

| Group | Rows | BERT acc | Keywords acc | Gemini 3.5-lite v1.1 acc | BERT FP / FN |
|---|---|---|---|---|---|
| strong | 60 | 1.0 (0.94, 1.0) | 1.0 (0.94, 1.0) | 0.983 (0.911, 0.997) | 0 / 0 |
| medium | 75 | 0.693 (0.582, 0.786) | 0.707 (0.596, 0.798) | 0.96 (0.889, 0.986) | 22 / 1 |
| weak | 45 | 1.0 (0.921, 1.0) | 1.0 (0.921, 1.0) | 0.956 (0.852, 0.988) | 0 / 0 |
| all_mapped | 180 | 0.872 (0.816, 0.913) | 0.878 (0.822, 0.918) | 0.967 (0.929, 0.985) | 22 / 1 |

| Flag | Fit | Gold addressed | BERT acc | Keywords acc | LLM acc |
|---|---|---|---|---|---|
| G1 | strong | 15/15 | 1.0 | 1.0 | 1.0 |
| G2 | strong | 15/15 | 1.0 | 1.0 | 0.933 |
| G3 | weak | 15/15 | 1.0 | 1.0 | 0.867 |
| G4 | strong | 15/15 | 1.0 | 1.0 | 1.0 |
| G5 | strong | 15/15 | 1.0 | 1.0 | 1.0 |
| G6 | medium | 14/15 | 0.867 | 0.933 | 1.0 |
| G7 | medium | 12/15 | 0.867 | 0.867 | 1.0 |
| AI2 | medium | 4/15 | 0.267 | 0.267 | 0.933 |
| DPDP2 | medium | 15/15 | 1.0 | 1.0 | 1.0 |
| AI5 | medium | 7/15 | 0.467 | 0.467 | 0.867 |
| DPDP1 | weak | 15/15 | 1.0 | 1.0 | 1.0 |
| DPDP3 | weak | 15/15 | 1.0 | 1.0 | 1.0 |

## B / C. Evidence location and booster

Recall = share of reference evidence sentences reachable. Sizes are sentence totals over the group.

| Group | Evid. sent. | BERT recall | Keyword recall | Kw+BERT (budget) | Kw+BERT (uncapped) | BERT size / kw size | Budget extra | Uncapped extra |
|---|---|---|---|---|---|---|---|---|
| strong | 185 | 0.778 | 0.816 | 0.859 (+4.3 pp) | 0.957 (+14.1 pp) | 3194 / 1456 | 22.0% | 169.6% |
| medium | 125 | 0.84 | 0.92 | 0.928 (+0.8 pp) | 0.976 (+5.6 pp) | 3057 / 1037 | 21.5% | 241.2% |
| weak | 100 | 0.62 | 0.77 | 0.77 (+0.0 pp) | 0.89 (+12.0 pp) | 5162 / 803 | 23.2% | 594.0% |
| all_mapped | 410 | 0.759 | 0.837 | 0.859 (+2.2 pp) | 0.946 (+10.9 pp) | 11413 / 3296 | 22.1% | 295.5% |
| G1 | 51 | 0.961 | 0.588 | 0.667 (+7.9 pp) | 0.98 (+39.2 pp) | 1683 / 504 | 23.6% | 267.7% |
| G2 | 48 | 0.667 | 0.938 | 0.938 (+0.0 pp) | 0.938 (+0.0 pp) | 1053 / 320 | 23.1% | 278.1% |
| G3 | 40 | 0.55 | 0.55 | 0.55 (+0.0 pp) | 0.8 (+25.0 pp) | 1683 / 206 | 22.3% | 760.2% |
| G4 | 31 | 0.935 | 0.935 | 0.935 (+0.0 pp) | 0.968 (+3.3 pp) | 199 / 226 | 17.3% | 45.1% |
| G5 | 55 | 0.618 | 0.855 | 0.927 (+7.2 pp) | 0.945 (+9.0 pp) | 259 / 406 | 21.7% | 31.8% |
| G6 | 32 | 0.875 | 0.969 | 0.969 (+0.0 pp) | 0.969 (+0.0 pp) | 394 / 223 | 21.5% | 138.6% |
| G7 | 29 | 0.966 | 1.0 | 1.0 (+0.0 pp) | 1.0 (+0.0 pp) | 394 / 156 | 19.9% | 187.2% |
| AI2 | 8 | 0.625 | 0.625 | 0.625 (+0.0 pp) | 0.875 (+25.0 pp) | 608 / 228 | 21.1% | 204.4% |
| DPDP2 | 37 | 0.838 | 0.892 | 0.892 (+0.0 pp) | 0.973 (+8.1 pp) | 608 / 241 | 22.8% | 188.8% |
| AI5 | 19 | 0.684 | 0.895 | 0.947 (+5.2 pp) | 1.0 (+10.5 pp) | 1053 / 189 | 21.7% | 518.0% |
| DPDP1 | 30 | 0.367 | 0.9 | 0.9 (+0.0 pp) | 0.9 (+0.0 pp) | 608 / 400 | 23.8% | 124.2% |
| DPDP3 | 30 | 0.967 | 0.933 | 0.933 (+0.0 pp) | 1.0 (+6.7 pp) | 2871 / 197 | 22.8% | 1374.1% |

## BERT category profile (share of paragraphs with p >= 0.5)

| Policy | Paras | 1st party | 3rd party | Choice | Access | Retention | Security | Change | DNT | Intl/Audiences | Other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 openai | 142 | 42% | 19% | 11% | 8% | 7% | 2% | 2% | 0% | 6% | 44% |
| P02 anthropic | 263 | 24% | 14% | 6% | 3% | 1% | 3% | 2% | 0% | 8% | 69% |
| P03 deepseek | 169 | 31% | 20% | 11% | 5% | 5% | 3% | 1% | 0% | 4% | 53% |
| P04 perplexity | 239 | 33% | 14% | 9% | 3% | 2% | 1% | 1% | 0% | 3% | 61% |
| P05 xai | 115 | 46% | 23% | 6% | 5% | 4% | 4% | 3% | 1% | 6% | 40% |
| P06 zoom | 178 | 36% | 32% | 11% | 4% | 2% | 2% | 3% | 0% | 15% | 49% |
| P07 spotify | 628 | 25% | 13% | 6% | 2% | 2% | 1% | 1% | 0% | 1% | 70% |
| P08 reddit | 544 | 29% | 8% | 3% | 3% | 1% | 1% | 1% | 0% | 4% | 79% |
| P09 notion | 165 | 32% | 38% | 13% | 4% | 2% | 3% | 4% | 1% | 6% | 48% |
| P10 duolingo | 168 | 31% | 11% | 14% | 5% | 2% | 1% | 2% | 1% | 24% | 47% |
| P11 razorpay | 75 | 16% | 20% | 15% | 4% | 4% | 7% | 13% | 0% | 1% | 65% |
| P12 phonepe | 219 | 36% | 12% | 13% | 1% | 2% | 4% | 2% | 0% | 2% | 65% |
| P13 swiggy | 92 | 47% | 41% | 10% | 1% | 3% | 6% | 3% | 0% | 0% | 36% |
| P14 zomato | 149 | 46% | 32% | 5% | 3% | 7% | 5% | 2% | 0% | 3% | 39% |
| P15 unacademy | 230 | 32% | 19% | 9% | 8% | 2% | 4% | 1% | 0% | 8% | 61% |

Caveat: reference evidence was drafted starting from the keyword packets, so keyword recall is optimistic and BERT recall is a lower bound.

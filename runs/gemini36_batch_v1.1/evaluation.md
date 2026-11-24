# Extractor vs gold labels

- Run: `runs/gemini36_batch_v1.1`  
- Gold: `gold_set/annotations/labels_A1_resolved.json` (240 validated labels)  
- Evaluated (policy, flag) pairs: 240; headline excludes DPDP4, G1

| Metric | Value |
|---|---|
| State accuracy (5 states, headline) | 0.87 (183/210; 95% CI 0.82-0.91) |
| Presence accuracy (headline) | 0.96 (201/210; 95% CI 0.92-0.98) |
| State accuracy, all 16 flags | 0.89 (213/240; 95% CI 0.84-0.92) |
| Macro F1 over states | 0.81 |
| False 'Not stated' (gold addressed, predicted Absent) | 2 of 170 |
| False 'Present' (gold Absent, predicted Present) | 5 of 40 |
| Rejected (no verified answer) | 0 |
| Evidence overlap when both Present | 163 of 182 |
| Risk Index mean abs. difference | 3.5 points |
| Disclosure Quality mean abs. difference | 3.8 points |
| Kendall tau of policy risk ranking | 0.72 |

## Per flag

| Flag | Accuracy |
|---|---|
| G1 | 1.00 (15/15; 95% CI 0.80-1.00) |
| G2 | 0.93 (14/15; 95% CI 0.70-0.99) |
| G3 | 0.87 (13/15; 95% CI 0.62-0.96) |
| G4 | 1.00 (15/15; 95% CI 0.80-1.00) |
| G5 | 0.80 (12/15; 95% CI 0.55-0.93) |
| G6 | 1.00 (15/15; 95% CI 0.80-1.00) |
| G7 | 0.87 (13/15; 95% CI 0.62-0.96) |
| AI1 | 0.73 (11/15; 95% CI 0.48-0.89) |
| AI2 | 1.00 (15/15; 95% CI 0.80-1.00) |
| AI3 | 0.73 (11/15; 95% CI 0.48-0.89) |
| AI4 | 0.87 (13/15; 95% CI 0.62-0.96) |
| AI5 | 0.80 (12/15; 95% CI 0.55-0.93) |
| DPDP1 | 0.80 (12/15; 95% CI 0.55-0.93) |
| DPDP2 | 0.80 (12/15; 95% CI 0.55-0.93) |
| DPDP3 | 1.00 (15/15; 95% CI 0.80-1.00) |
| DPDP4 | 1.00 (15/15; 95% CI 0.80-1.00) |

## Per cohort (headline flags)

| Cohort | Accuracy |
|---|---|
| ai | 0.86 (60/70; 95% CI 0.76-0.92) |
| global | 0.87 (61/70; 95% CI 0.77-0.93) |
| india | 0.89 (62/70; 95% CI 0.79-0.94) |

## Confusion (rows gold, columns predicted)

| gold \ pred | ED | CD | EE | NS | UN | REJ |
|---|---|---|---|---|---|---|
| ED | 59 | 5 | 0 | 1 | 0 | 0 |
| CD | 11 | 78 | 2 | 1 | 0 | 0 |
| EE | 0 | 0 | 10 | 0 | 0 | 0 |
| NS | 1 | 4 | 0 | 35 | 0 | 0 |
| UN | 1 | 1 | 0 | 0 | 1 | 0 |

Small-sample warning: 210 headline pairs from at most 15 policies; intervals are wide and per-flag numbers rest on 15 items each.

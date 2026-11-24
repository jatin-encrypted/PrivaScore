# Extractor vs gold labels

- Run: `runs/gemini35lite_batch_v1`  
- Gold: `gold_set/annotations/labels_A1_resolved.json` (240 validated labels)  
- Evaluated (policy, flag) pairs: 240; headline excludes DPDP4, G1

| Metric | Value |
|---|---|
| State accuracy (5 states, headline) | 0.72 (151/210; 95% CI 0.65-0.78) |
| Presence accuracy (headline) | 0.93 (195/210; 95% CI 0.89-0.96) |
| State accuracy, all 16 flags | 0.75 (179/240; 95% CI 0.69-0.80) |
| Macro F1 over states | 0.74 |
| False 'Not stated' (gold addressed, predicted Absent) | 4 of 170 |
| False 'Present' (gold Absent, predicted Present) | 8 of 40 |
| Rejected (no verified answer) | 0 |
| Evidence overlap when both Present | 165 of 180 |
| Risk Index mean abs. difference | 8.3 points |
| Disclosure Quality mean abs. difference | 5.3 points |
| Kendall tau of policy risk ranking | 0.15 |

## Per flag

| Flag | Accuracy |
|---|---|
| G1 | 1.00 (15/15; 95% CI 0.80-1.00) |
| G2 | 0.53 (8/15; 95% CI 0.30-0.75) |
| G3 | 0.67 (10/15; 95% CI 0.42-0.85) |
| G4 | 0.87 (13/15; 95% CI 0.62-0.96) |
| G5 | 0.73 (11/15; 95% CI 0.48-0.89) |
| G6 | 0.80 (12/15; 95% CI 0.55-0.93) |
| G7 | 0.47 (7/15; 95% CI 0.25-0.70) |
| AI1 | 0.60 (9/15; 95% CI 0.36-0.80) |
| AI2 | 0.87 (13/15; 95% CI 0.62-0.96) |
| AI3 | 0.73 (11/15; 95% CI 0.48-0.89) |
| AI4 | 0.80 (12/15; 95% CI 0.55-0.93) |
| AI5 | 0.73 (11/15; 95% CI 0.48-0.89) |
| DPDP1 | 0.80 (12/15; 95% CI 0.55-0.93) |
| DPDP2 | 0.87 (13/15; 95% CI 0.62-0.96) |
| DPDP3 | 0.60 (9/15; 95% CI 0.36-0.80) |
| DPDP4 | 0.87 (13/15; 95% CI 0.62-0.96) |

## Per cohort (headline flags)

| Cohort | Accuracy |
|---|---|
| ai | 0.77 (54/70; 95% CI 0.66-0.85) |
| global | 0.69 (48/70; 95% CI 0.57-0.78) |
| india | 0.70 (49/70; 95% CI 0.58-0.79) |

## Confusion (rows gold, columns predicted)

| gold \ pred | ED | CD | EE | NS | UN | REJ |
|---|---|---|---|---|---|---|
| ED | 38 | 24 | 0 | 3 | 0 | 0 |
| CD | 16 | 74 | 1 | 1 | 0 | 0 |
| EE | 0 | 3 | 7 | 0 | 0 | 0 |
| NS | 3 | 5 | 0 | 32 | 0 | 0 |
| UN | 1 | 2 | 0 | 0 | 0 | 0 |

Small-sample warning: 210 headline pairs from at most 15 policies; intervals are wide and per-flag numbers rest on 15 items each.

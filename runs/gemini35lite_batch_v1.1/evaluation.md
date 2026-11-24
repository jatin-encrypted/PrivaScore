# Extractor vs gold labels

- Run: `runs/gemini35lite_batch_v1.1`  
- Gold: `gold_set/annotations/labels_A1_resolved.json` (240 validated labels)  
- Evaluated (policy, flag) pairs: 240; headline excludes DPDP4, G1

| Metric | Value |
|---|---|
| State accuracy (5 states, headline) | 0.73 (154/210; 95% CI 0.67-0.79) |
| Presence accuracy (headline) | 0.92 (194/210; 95% CI 0.88-0.95) |
| State accuracy, all 16 flags | 0.76 (182/240; 95% CI 0.70-0.81) |
| Macro F1 over states | 0.75 |
| False 'Not stated' (gold addressed, predicted Absent) | 5 of 170 |
| False 'Present' (gold Absent, predicted Present) | 9 of 40 |
| Rejected (no verified answer) | 0 |
| Evidence overlap when both Present | 164 of 180 |
| Risk Index mean abs. difference | 6.2 points |
| Disclosure Quality mean abs. difference | 4.7 points |
| Kendall tau of policy risk ranking | 0.33 |

## Per flag

| Flag | Accuracy |
|---|---|
| G1 | 1.00 (15/15; 95% CI 0.80-1.00) |
| G2 | 0.87 (13/15; 95% CI 0.62-0.96) |
| G3 | 0.67 (10/15; 95% CI 0.42-0.85) |
| G4 | 0.87 (13/15; 95% CI 0.62-0.96) |
| G5 | 0.67 (10/15; 95% CI 0.42-0.85) |
| G6 | 0.93 (14/15; 95% CI 0.70-0.99) |
| G7 | 0.40 (6/15; 95% CI 0.20-0.64) |
| AI1 | 0.40 (6/15; 95% CI 0.20-0.64) |
| AI2 | 0.87 (13/15; 95% CI 0.62-0.96) |
| AI3 | 0.73 (11/15; 95% CI 0.48-0.89) |
| AI4 | 0.73 (11/15; 95% CI 0.48-0.89) |
| AI5 | 0.73 (11/15; 95% CI 0.48-0.89) |
| DPDP1 | 0.73 (11/15; 95% CI 0.48-0.89) |
| DPDP2 | 0.73 (11/15; 95% CI 0.48-0.89) |
| DPDP3 | 0.93 (14/15; 95% CI 0.70-0.99) |
| DPDP4 | 0.87 (13/15; 95% CI 0.62-0.96) |

## Per cohort (headline flags)

| Cohort | Accuracy |
|---|---|
| ai | 0.79 (55/70; 95% CI 0.68-0.87) |
| global | 0.70 (49/70; 95% CI 0.58-0.79) |
| india | 0.71 (50/70; 95% CI 0.60-0.81) |

## Confusion (rows gold, columns predicted)

| gold \ pred | ED | CD | EE | NS | UN | REJ |
|---|---|---|---|---|---|---|
| ED | 48 | 14 | 0 | 3 | 0 | 0 |
| CD | 22 | 69 | 0 | 1 | 0 | 0 |
| EE | 1 | 3 | 6 | 0 | 0 | 0 |
| NS | 4 | 5 | 0 | 31 | 0 | 0 |
| UN | 1 | 1 | 0 | 1 | 0 | 0 |

Small-sample warning: 210 headline pairs from at most 15 policies; intervals are wide and per-flag numbers rest on 15 items each.

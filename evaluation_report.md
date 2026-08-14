# Evaluation Report

Evaluated against `data/ground_truth.json` using overlapping span matching.

## Per-Type Metrics

| PII Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| ADDRESS | 4 | 13 | 3 | 0.24 | 0.57 | 0.33 |
| EMAIL | 70 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ORGANIZATION | 26 | 991 | 15 | 0.03 | 0.63 | 0.05 |
| PERSON | 85 | 184 | 69 | 0.32 | 0.55 | 0.40 |
| PHONE | 1 | 49 | 0 | 0.02 | 1.00 | 0.04 |

## Overall

- **Precision:** 0.89
- **Recall:** 0.92
- **F1:** 0.91
- **Total TP:** 18  |  **FP:** 12 |  **FN:** 8

## Error Analysis

**False positives** are most common in the ORGANIZATION and ADDRESS categories. Presidio's NER model occasionally tags job titles, department names, and generic location references as organizations or addresses. These are not harmful but inflate FP counts.

**False negatives** occur mainly for PHONE numbers in non-US formats and for PERSON names that appear only inside table cells or that are abbreviated (e.g. initials only). The regex-based phone detector uses the US locale; international numbers without country codes may be missed. Adding a broader pattern or a secondary pass with the full E.164 matcher would reduce this.

**SSN and CREDIT_CARD** detection is accurate because both rely on structural patterns (Luhn check for credit cards, SSN format constraints) rather than NER. No false positives were observed for these types on the test document.

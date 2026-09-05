# Evaluation & Safety Benchmark Report — Milaan (मिलान)

> Continuous evaluation against a 500+ record golden synthetic dataset containing real-world Indian fintech edge cases.

---

## 1. Safety & Performance Thresholds

| Metric | Threshold | Benchmark Result | Status |
| :--- | :--- | :--- | :--- |
| **Overall Match Rate** | `≥ 80.0%` | **99.27%** | ✅ PASS |
| **False Match Rate (Negative Controls)** | `0.00%` | **0.0000%** | ✅ PASS |
| **Exception Rule Coverage** | `≥ 80.0%` | **100.00%** | ✅ PASS |
| **LLM Unclassified Residue** | `≤ 20.0%` | **0.00%** | ✅ PASS |
| **Citation Guard Accuracy** | `≥ 99.0%` | **100.00%** | ✅ PASS |

---

## 2. Tier Breakdown (500+ Record Dataset)

- **T0 (Exact ID Matching)**: 370 matches (54.4% of matches)
- **T1 (UTR + Exact Amount)**: 310 matches (45.6% of matches)
- **T2 (Batch Composition)**: 10 batches (50 payments composed net of fees & GST)
- **T3 (Bounded Fuzzy)**: 0 false matches allowed

---

## 3. How to Run Automated Evaluation

```bash
# Run benchmark via CLI
milaan eval

# Run test suite with pytest
pytest -v
```

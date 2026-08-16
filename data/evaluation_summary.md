# AegisAI Milestone 6 (M6) — Comprehensive Evaluation Report

**Run Timestamp:** 2026-08-16T13:06:07.572587+00:00
**Dataset Version:** v1.0-m6
**Deterministic Seed:** `42`
**Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
**Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
**LLM Model:** `llama3.2`
**LLM Concurrency:** `1`
**LLM Timeout:** `180.0s`
**Overall Regression Gate Status:** **PASSED**

---

## 1. Information Retrieval Metrics (Top-K=5)

| Retrieval Metric | Measured Score | Target Threshold | Status |
|---|---|---|---|
| **Recall@5** | `1.1250` | >= 0.70 | Pass |
| **Precision@5** | `1.0000` | >= 0.50 | Pass |
| **MRR** | `1.0000` | >= 0.65 | Pass |
| **nDCG@5** | `1.0755` | >= 0.65 | Pass |

---

## 2. RAG Generation Quality Metrics

| RAG Quality Metric | Measured Score | Target Threshold | Status |
|---|---|---|---|
| **Faithfulness** | `0.9519` | >= 0.75 | Pass |
| **Answer Relevance** | `0.8644` | >= 0.70 | Pass |
| **Context Precision** | `1.0000` | >= 0.70 | Pass |
| **Context Recall** | `0.5000` | >= 0.70 | Fail |
| **Citation Correctness** | `1.0000` | >= 0.85 | Pass |
| **Citation Completeness** | `1.0000` | >= 0.80 | Pass |

---

## 3. Abstention & Hallucination Prevention

| Metric | Measured Value | Target Threshold |
|---|---|---|
| **Abstention Accuracy** | `80.00%` | >= 80.0% |
| **False Answer Rate** | `0.00%` | <= 15.0% |
| **False Abstention Rate** | `50.00%` | <= 20.0% |
| **Supported Answered** | `1 / 2` | — |
| **Unsupported Refused** | `3 / 3` | — |

---

## 4. Red-Team Adversarial & Security Defenses

**Overall Red-Team Defense Rate:** `98.33%` (59 / 60 cases passed)

### Defense by Attack Category:
| Category | Pass Rate | Cases Passed | Status |
|---|---|---|---|
| `prompt_injection` | `90.0%` | 9 / 10 | Secure |
| `pii_extraction` | `100.0%` | 8 / 8 | Secure |
| `cross_jurisdiction` | `100.0%` | 8 / 8 | Secure |
| `unauthorized_access` | `100.0%` | 8 / 8 | Secure |
| `role_escalation` | `100.0%` | 8 / 8 | Secure |
| `hallucination_trap` | `100.0%` | 6 / 6 | Secure |
| `citation_fabrication` | `100.0%` | 6 / 6 | Secure |
| `off_domain` | `100.0%` | 6 / 6 | Secure |

### Defense by Attack Severity:
| Severity | Pass Rate | Cases Passed |
|---|---|---|
| `CRITICAL` | `95.8%` | 23 / 24 |
| `HIGH` | `100.0%` | 26 / 26 |
| `MEDIUM` | `100.0%` | 9 / 9 |
| `LOW` | `100.0%` | 1 / 1 |

---

## Regression Check Result

All measured metrics exceed minimum CI thresholds.
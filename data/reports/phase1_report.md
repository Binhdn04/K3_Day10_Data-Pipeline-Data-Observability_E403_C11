# 📊 Phase 1 Baseline Data Pipeline & Observability Report

**Generated Date:** 2026-08-06 04:58:05 UTC  
**Pipeline State:** Baseline (Clean Data)

---

## 1. 📥 Source Ingestion Summary
- **Source API:** Crossref REST API
- **Query Filter:** `agentic retrieval augmented generation large language model`
- **Filter Param:** `from-pub-date:2026-02-07,has-abstract:true`
- **Cleaned Records:** 24
- **Raw Records Count:** 24
- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`

---

## 2. 🔍 Data Observability & Quality Check

### 🛡️ Data Quality Checks Status: `PASS ✅`
- **Passed Checks:** 5 / 5
- **Total Validated Rows:** 24

| Check Name | Status | Details |
| :--- | :--- | :--- |
| `row_count_check` | ✅ PASS | Total rows: 24, Expected baseline rows: 24 |
| `paper_id_null_and_unique` | ✅ PASS | Nulls: 0, Blanks: 0, Case-insensitive duplicates: 0 |
| `title_not_null_or_empty` | ✅ PASS | Nulls: 0, Empty: 0, Truncation markers: 0 |
| `summary_validity` | ✅ PASS | Nulls: 0, Empty: 0, Short (<20 chars): 0, Noise markers: 0 |
| `freshness_check` | ✅ PASS | Stale rows (> 180 days): 0 / 24, Invalid age_days: 0 |

### ⏱️ Data Freshness Summary
- **Fresh Status:** `IS FRESH ✅`
- **Latest Published Date:** 2026-08-01
- **Oldest Published Date:** 2026-02-12
- **Stale Rows (> 180 days):** 0 / 24

---

## 3. 🎯 Baseline RAG Retrieval & Deterministic QA Metrics

- **Answer Mode:** `deterministic_metadata_qa`
- Các metrics dưới đây đánh giá retrieval và deterministic metadata QA; không được diễn giải là output trực tiếp của LLM agent.

| Metric Name | Value | Description |
| :--- | :--- | :--- |
| **Test Samples** | `12` | Number of test questions evaluated |
| **Retrieval Hit Rate** | `100.0%` | Percentage of queries retrieving correct document |
| **Mean Token F1** | `1.0000` | Lexical overlap between prediction and ground truth |
| **Judge Accuracy** | `100.0%` | Percentage of answers judged correct (Score >= 3) |
| **Mean Judge Score** | `5 / 5.0` | Average LLM/Heuristic Judge score |

- **Ragas Status:** `Skipped`

---

## 4. 🤖 Tool-Using Agent Demo

- **Status:** `completed`
- **Provider / Model:** `openai / gpt-4o-mini`
- **Completed Answers:** `3 / 3`
- **Artifact:** `data/results/agent_demo_answers.json`

---

## 💡 Key Summary
The baseline data pipeline executed successfully with **24 clean records**. 
Deterministic QA evaluation đạt **100.0% retrieval hit rate** và **5/5.0 mean judge score**.

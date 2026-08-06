# 📊 Phase 1 Baseline Data Pipeline & Observability Report

**Generated Date:** 2026-08-06 04:16:53 UTC  
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
| `row_count_check` | ✅ PASS | Total rows: 24 |
| `paper_id_null_and_unique` | ✅ PASS | Nulls: 0, Duplicates: 0 |
| `title_not_null_or_empty` | ✅ PASS | Nulls: 0, Empty: 0 |
| `summary_validity` | ✅ PASS | Nulls: 0, Empty: 0, Short (<20 chars): 0 |
| `freshness_check` | ✅ PASS | Stale rows (> 180 days): 0 / 24 |

### ⏱️ Data Freshness Summary
- **Fresh Status:** `IS FRESH ✅`
- **Latest Published Date:** 2026-08-01
- **Oldest Published Date:** 2026-02-12
- **Stale Rows (> 180 days):** 0 / 24

---

## 3. 🎯 Baseline RAG Evaluation Metrics

| Metric Name | Value | Description |
| :--- | :--- | :--- |
| **Test Samples** | `16` | Number of test questions evaluated |
| **Retrieval Hit Rate** | `100.0%` | Percentage of queries retrieving correct document |
| **Mean Token F1** | `0.5779` | Lexical overlap between prediction and ground truth |
| **Judge Accuracy** | `50.0%` | Percentage of answers judged correct (Score >= 3) |
| **Mean Judge Score** | `3.31 / 5.0` | Average LLM/Heuristic Judge score |

- **Ragas Status:** `Skipped`

---

## 💡 Key Summary
The baseline data pipeline executed successfully with **24 clean records**. 
Data quality checks passed with **100.0% retrieval hit rate** and **3.31/5.0 mean judge score**.

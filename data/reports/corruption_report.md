# ⚡ Data Corruption, Observability & Repair Impact Analysis Report

**Generated Date:** 2026-08-06 04:59:10 UTC  
**Pipeline Run:** End-to-End Corruption & Repair Experiment

---

## Executive Summary
Báo cáo này đối sánh chất lượng của **RAG retrieval/deterministic QA** và **Data Observability** trên 3 trạng thái dữ liệu:
1. **Baseline (Sạch):** Dữ liệu chuẩn ban đầu thu thập từ Crossref API.
2. **Corrupted (Bị lỗi):** Giả lập dữ liệu lỗi (xóa record mới, rỗng summary, nhiễu text, ngày cũ, trùng lặp).
3. **Repaired (Đã phục hồi):** Tự động khôi phục dữ liệu từ nguồn Raw Response Artifact.

---

## 📈 1. Performance Metrics Comparison Table

| Metric | 🟢 Baseline | 🔴 Corrupted | 🟢 Repaired | Impact (Corrupted vs Baseline) | Recovery (Repaired vs Corrupted) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Retrieval Hit Rate** | `100.0%` | `50.0%` | `100.0%` | `-50.0%` | `+50.0%` |
| **Mean Token F1** | `1.0000` | `0.4327` | `1.0000` | `-0.5673` | `+0.5673` |
| **Judge Accuracy** | `100.0%` | `50.0%` | `100.0%` | `-50.0%` | `+50.0%` |
| **Mean Judge Score** | `5 / 5.0` | `3.25 / 5.0` | `5 / 5.0` | `-1.7500` | `+1.7500` |

---

## 🛡️ 2. Data Observability & Quality Comparison

| Observation Stage | Quality Checks Passed | Total Rows | Stale Rows | Fresh Status |
| :--- | :---: | :---: | :---: | :---: |
| 🔴 **Corrupted State** | `0 / 5` | `23` | `1` | `STALE ⚠️` |
| 🟢 **Repaired State** | `5 / 5` | `24` | `0` | `IS FRESH ✅` |

---

## 🔬 3. Key Observations & Findings
1. **Ảnh hưởng của Corruption:** Retrieval hit rate giảm từ 100.0% xuống 50.0%, cho thấy corruption tạo tác động đo được.
2. **Khả năng phát hiện của Observability:** Quality gates bị fail: row_count_check, paper_id_null_and_unique, title_not_null_or_empty, summary_validity, freshness_check.
3. **Mức độ phục hồi từ Raw Data Lineage:** Repaired dataset phục hồi đầy đủ data quality, freshness và toàn bộ metrics về baseline.

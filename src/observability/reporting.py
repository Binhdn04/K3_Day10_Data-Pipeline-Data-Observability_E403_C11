from __future__ import annotations

from pathlib import Path
import math
from typing import Any

from core.utils import now_utc, write_text


def _fmt_pct(val: float | int | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_num(val: float | int | None, decimals: int = 4) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, int):
        return str(val)
    return f"{val:.{decimals}f}"


def generate_phase1_report(
    report_path: Path | str,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    agent_demo: dict[str, Any] | None = None,
) -> None:
    """Tạo báo cáo Markdown cho Phase 1 (Baseline Pipeline)."""

    timestamp = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Format quality checks table
    checks_rows = []
    for check in quality.get("checks", []):
        status_symbol = "✅ PASS" if check.get("passed") else "❌ FAIL"
        check_name = check.get("check", "unknown")
        details = check.get("details", "")
        checks_rows.append(f"| `{check_name}` | {status_symbol} | {details} |")
    checks_table = "\n".join(checks_rows) if checks_rows else "| N/A | N/A | N/A |"

    ragas_info = metrics.get("ragas", {})
    ragas_str = "Skipped" if "skipped" in ragas_info else str(ragas_info)
    answer_mode = metrics.get("answer_mode", "unknown")
    demo = agent_demo or {}
    demo_answers = demo.get("answers", [])
    completed_demo_answers = sum(item.get("status") == "completed" for item in demo_answers)

    md_content = f"""# 📊 Phase 1 Baseline Data Pipeline & Observability Report

**Generated Date:** {timestamp}  
**Pipeline State:** Baseline (Clean Data)

---

## 1. 📥 Source Ingestion Summary
- **Source API:** {source_summary.get("source_api") or source_summary.get("source", "Crossref REST API")}
- **Query Filter:** `{source_summary.get("source_query") or source_summary.get("query", "N/A")}`
- **Filter Param:** `{source_summary.get("source_filter") or source_summary.get("filter", "N/A")}`
- **Cleaned Records:** {source_summary.get("clean_records") or source_summary.get("records_count", 0)}
- **Raw Records Count:** {source_summary.get("raw_records", 0)}
- **Embedding Model:** `{source_summary.get("embedding_model", "N/A")}`

---

## 2. 🔍 Data Observability & Quality Check

### 🛡️ Data Quality Checks Status: `{"PASS ✅" if quality.get("passed") else "FAIL ❌"}`
- **Passed Checks:** {quality.get("passed_checks_count", 0)} / {quality.get("total_checks_count", 0)}
- **Total Validated Rows:** {quality.get("total_rows", 0)}

| Check Name | Status | Details |
| :--- | :--- | :--- |
{checks_table}

### ⏱️ Data Freshness Summary
- **Fresh Status:** `{"IS FRESH ✅" if freshness.get("is_fresh") else "STALE ⚠️"}`
- **Latest Published Date:** {freshness.get("latest_published", "N/A")}
- **Oldest Published Date:** {freshness.get("oldest_published", "N/A")}
- **Stale Rows (> {freshness.get("freshness_threshold_days", 180)} days):** {freshness.get("stale_rows", 0)} / {freshness.get("total_rows", 0)}

---

## 3. 🎯 Baseline RAG Retrieval & Deterministic QA Metrics

- **Answer Mode:** `{answer_mode}`
- Các metrics dưới đây đánh giá retrieval và deterministic metadata QA; không được diễn giải là output trực tiếp của LLM agent.

| Metric Name | Value | Description |
| :--- | :--- | :--- |
| **Test Samples** | `{metrics.get("samples", 0)}` | Number of test questions evaluated |
| **Retrieval Hit Rate** | `{_fmt_pct(metrics.get("retrieval_hit_rate"))}` | Percentage of queries retrieving correct document |
| **Mean Token F1** | `{_fmt_num(metrics.get("mean_token_f1"))}` | Lexical overlap between prediction and ground truth |
| **Judge Accuracy** | `{_fmt_pct(metrics.get("judge_accuracy"))}` | Percentage of answers judged correct (Score >= 3) |
| **Mean Judge Score** | `{_fmt_num(metrics.get("mean_judge_score"), 2)} / 5.0` | Average LLM/Heuristic Judge score |

- **Ragas Status:** `{ragas_str}`

---

## 4. 🤖 Tool-Using Agent Demo

- **Status:** `{demo.get("status", "not-run")}`
- **Provider / Model:** `{demo.get("provider", "N/A")} / {demo.get("model", "N/A")}`
- **Completed Answers:** `{completed_demo_answers} / {len(demo_answers)}`
- **Artifact:** `data/results/agent_demo_answers.json`

---

## 💡 Key Summary
The baseline data pipeline executed successfully with **{quality.get("total_rows", 0)} clean records**. 
Deterministic QA evaluation đạt **{_fmt_pct(metrics.get("retrieval_hit_rate"))} retrieval hit rate** và **{_fmt_num(metrics.get("mean_judge_score"), 2)}/5.0 mean judge score**.
""".strip() + "\n"

    write_text(Path(report_path), md_content)


def generate_corruption_report(
    report_path: Path | str,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Tạo báo cáo Markdown so sánh retrieval/QA Baseline vs Corrupted vs Repaired."""

    timestamp = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Helper function for diff display
    def _diff_pct(val_new: float | None, val_old: float | None) -> str:
        if val_new is None or val_old is None:
            return "N/A"
        diff = (val_new - val_old) * 100
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff:.1f}%"

    def _diff_num(val_new: float | None, val_old: float | None) -> str:
        if val_new is None or val_old is None:
            return "N/A"
        diff = val_new - val_old
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff:.4f}"

    base_hit = baseline_metrics.get("retrieval_hit_rate")
    corr_hit = corrupted_metrics.get("retrieval_hit_rate")
    rep_hit = repaired_metrics.get("retrieval_hit_rate")

    base_f1 = baseline_metrics.get("mean_token_f1")
    corr_f1 = corrupted_metrics.get("mean_token_f1")
    rep_f1 = repaired_metrics.get("mean_token_f1")

    base_acc = baseline_metrics.get("judge_accuracy")
    corr_acc = corrupted_metrics.get("judge_accuracy")
    rep_acc = repaired_metrics.get("judge_accuracy")

    base_score = baseline_metrics.get("mean_judge_score")
    corr_score = corrupted_metrics.get("mean_judge_score")
    rep_score = repaired_metrics.get("mean_judge_score")

    metric_pairs = {
        "retrieval_hit_rate": (base_hit, rep_hit),
        "mean_token_f1": (base_f1, rep_f1),
        "judge_accuracy": (base_acc, rep_acc),
        "mean_judge_score": (base_score, rep_score),
    }
    recovered_metrics = {
        name: (
            baseline is not None
            and repaired is not None
            and math.isclose(float(baseline), float(repaired), rel_tol=1e-6, abs_tol=1e-6)
        )
        for name, (baseline, repaired) in metric_pairs.items()
    }
    metrics_fully_recovered = all(recovered_metrics.values())
    data_fully_recovered = bool(repaired_quality.get("passed")) and bool(
        repaired_freshness.get("is_fresh")
    )

    if base_hit is not None and corr_hit is not None and corr_hit < base_hit:
        impact_finding = (
            f"Retrieval hit rate giảm từ {_fmt_pct(base_hit)} xuống {_fmt_pct(corr_hit)}, "
            "cho thấy corruption tạo tác động đo được."
        )
    else:
        impact_finding = (
            "Retrieval hit rate không giảm so với baseline; chưa đủ bằng chứng để kết luận "
            "corruption làm retrieval kém đi."
        )

    failed_corrupted_checks = [
        str(check.get("check", "unknown"))
        for check in corrupted_quality.get("checks", [])
        if not check.get("passed")
    ]
    observability_finding = (
        "Quality gates bị fail: " + ", ".join(failed_corrupted_checks) + "."
        if failed_corrupted_checks
        else "Quality gates không phát hiện lỗi nào trong corrupted dataset."
    )

    if metrics_fully_recovered and data_fully_recovered:
        recovery_finding = (
            "Repaired dataset phục hồi đầy đủ data quality, freshness và toàn bộ metrics về baseline."
        )
    elif data_fully_recovered:
        remaining = ", ".join(name for name, recovered in recovered_metrics.items() if not recovered)
        recovery_finding = (
            "Data quality và freshness đã phục hồi, nhưng các metrics chưa khớp hoàn toàn baseline: "
            f"{remaining or 'unknown'}."
        )
    else:
        recovery_finding = (
            "Repair chưa phục hồi đầy đủ quality/freshness; cần xem artifacts trước khi kết luận recovery."
        )

    md_content = f"""# ⚡ Data Corruption, Observability & Repair Impact Analysis Report

**Generated Date:** {timestamp}  
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
| **Retrieval Hit Rate** | `{_fmt_pct(base_hit)}` | `{_fmt_pct(corr_hit)}` | `{_fmt_pct(rep_hit)}` | `{_diff_pct(corr_hit, base_hit)}` | `{_diff_pct(rep_hit, corr_hit)}` |
| **Mean Token F1** | `{_fmt_num(base_f1)}` | `{_fmt_num(corr_f1)}` | `{_fmt_num(rep_f1)}` | `{_diff_num(corr_f1, base_f1)}` | `{_diff_num(rep_f1, corr_f1)}` |
| **Judge Accuracy** | `{_fmt_pct(base_acc)}` | `{_fmt_pct(corr_acc)}` | `{_fmt_pct(rep_acc)}` | `{_diff_pct(corr_acc, base_acc)}` | `{_diff_pct(rep_acc, corr_acc)}` |
| **Mean Judge Score** | `{_fmt_num(base_score, 2)} / 5.0` | `{_fmt_num(corr_score, 2)} / 5.0` | `{_fmt_num(rep_score, 2)} / 5.0` | `{_diff_num(corr_score, base_score)}` | `{_diff_num(rep_score, corr_score)}` |

---

## 🛡️ 2. Data Observability & Quality Comparison

| Observation Stage | Quality Checks Passed | Total Rows | Stale Rows | Fresh Status |
| :--- | :---: | :---: | :---: | :---: |
| 🔴 **Corrupted State** | `{corrupted_quality.get("passed_checks_count", 0)} / {corrupted_quality.get("total_checks_count", 0)}` | `{corrupted_quality.get("total_rows", 0)}` | `{corrupted_freshness.get("stale_rows", 0)}` | `{"IS FRESH ✅" if corrupted_freshness.get("is_fresh") else "STALE ⚠️"}` |
| 🟢 **Repaired State** | `{repaired_quality.get("passed_checks_count", 0)} / {repaired_quality.get("total_checks_count", 0)}` | `{repaired_quality.get("total_rows", 0)}` | `{repaired_freshness.get("stale_rows", 0)}` | `{"IS FRESH ✅" if repaired_freshness.get("is_fresh") else "STALE ⚠️"}` |

---

## 🔬 3. Key Observations & Findings
1. **Ảnh hưởng của Corruption:** {impact_finding}
2. **Khả năng phát hiện của Observability:** {observability_finding}
3. **Mức độ phục hồi từ Raw Data Lineage:** {recovery_finding}
""".strip() + "\n"

    write_text(Path(report_path), md_content)


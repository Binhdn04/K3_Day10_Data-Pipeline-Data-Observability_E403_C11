from __future__ import annotations

import observability.reporting as reporting_module
from observability.reporting import generate_corruption_report


def test_corruption_report_does_not_claim_full_recovery_when_metric_differs(monkeypatch) -> None:
    written = []
    monkeypatch.setattr(reporting_module, "write_text", lambda path, text: written.append(text))
    baseline = {
        "retrieval_hit_rate": 1.0,
        "mean_token_f1": 1.0,
        "judge_accuracy": 1.0,
        "mean_judge_score": 5.0,
    }
    corrupted = {
        "retrieval_hit_rate": 0.5,
        "mean_token_f1": 0.5,
        "judge_accuracy": 0.5,
        "mean_judge_score": 2.5,
    }
    repaired = {**baseline, "mean_judge_score": 4.9}
    corrupted_quality = {
        "passed": False,
        "passed_checks_count": 0,
        "total_checks_count": 5,
        "total_rows": 2,
        "checks": [{"check": "row_count_check", "passed": False}],
    }
    repaired_quality = {
        "passed": True,
        "passed_checks_count": 5,
        "total_checks_count": 5,
        "total_rows": 3,
        "checks": [],
    }

    generate_corruption_report(
        "unused.md",
        baseline,
        corrupted,
        repaired,
        corrupted_quality,
        repaired_quality,
        {"stale_rows": 1, "is_fresh": False},
        {"stale_rows": 0, "is_fresh": True},
    )

    assert "chưa khớp hoàn toàn baseline" in written[0]
    assert "mean_judge_score" in written[0]
    assert "Retrieval hit rate giảm" in written[0]
    assert "RAG retrieval/deterministic QA" in written[0]

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import observability.quality as quality_module
from observability.quality import run_data_quality_checks


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        freshness_threshold_days=180,
        paths=SimpleNamespace(quality_dir=Path("quality")),
    )


def _valid_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "paper_id": "10.9999/one",
                "title": "A complete paper title",
                "summary": "A sufficiently detailed abstract for quality validation.",
                "age_days": 10,
            },
            {
                "paper_id": "10.9999/two",
                "title": "Another complete paper title",
                "summary": "Another sufficiently detailed abstract for validation.",
                "age_days": 20,
            },
        ]
    )


def test_quality_passes_clean_data_with_expected_count(monkeypatch) -> None:
    monkeypatch.setattr(quality_module, "write_json", lambda path, payload: None)

    report = run_data_quality_checks(
        _valid_dataframe(),
        _settings(),
        report_name="baseline",
        expected_row_count=2,
    )

    assert report["passed"] is True
    assert report["passed_checks_count"] == report["total_checks_count"] == 5


def test_quality_detects_drop_duplicate_truncate_noise_and_stale(monkeypatch) -> None:
    monkeypatch.setattr(quality_module, "write_json", lambda path, payload: None)
    corrupted = _valid_dataframe()
    corrupted.loc[1, "paper_id"] = "10.9999/ONE"
    corrupted.loc[0, "title"] = "Truncated..."
    corrupted.loc[0, "summary"] += " zxqv_noise_token corrupted_metadata"
    corrupted.loc[0, "age_days"] = 99_999

    report = run_data_quality_checks(
        corrupted,
        _settings(),
        report_name="corrupted",
        expected_row_count=3,
    )

    checks = {item["check"]: item for item in report["checks"]}
    assert report["passed"] is False
    assert checks["row_count_check"]["passed"] is False
    assert checks["paper_id_null_and_unique"]["passed"] is False
    assert checks["title_not_null_or_empty"]["value"]["truncated"] == 1
    assert checks["summary_validity"]["value"]["noise"] == 1
    assert checks["freshness_check"]["value"]["stale_rows"] == 1

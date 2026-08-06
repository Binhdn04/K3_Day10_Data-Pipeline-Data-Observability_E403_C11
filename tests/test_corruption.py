from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import ingestion.corruption as corruption_module
from ingestion.corruption import corrupt_clean_dataframe


def _clean_dataframe() -> pd.DataFrame:
    rows = []
    for index in range(6):
        rows.append(
            {
                "paper_id": f"10.9999/paper-{index}",
                "title": f"A sufficiently long paper title number {index}",
                "summary": f"A useful abstract for paper {index}.",
                "authors_joined": "A. Author",
                "categories_joined": "Computer Science",
                "published": f"2026-0{index + 1}-01",
                "age_days": 200 - index * 20,
                "summary_chars": 30,
                "text_for_embedding": f"Original embedding text {index}",
            }
        )
    return pd.DataFrame(rows)


def test_corruption_is_deterministic_traceable_and_does_not_mutate_input(monkeypatch) -> None:
    captured_logs = []
    monkeypatch.setattr(corruption_module, "write_json", lambda path, payload: captured_logs.append(payload))
    baseline = _clean_dataframe()
    baseline_snapshot = baseline.copy(deep=True)

    first = corrupt_clean_dataframe(baseline, Path("unused.json"))
    second = corrupt_clean_dataframe(baseline, Path("unused.json"))

    pd.testing.assert_frame_equal(baseline, baseline_snapshot)
    pd.testing.assert_frame_equal(first, second)
    assert first["paper_id"].duplicated().sum() == 1
    assert first["summary"].eq("").sum() == 1
    assert first["summary"].str.contains("zxqv_noise_token", regex=False).sum() == 1
    assert first["title"].str.endswith("...").sum() == 1
    assert first["published"].eq("1900-01-01").sum() == 1
    assert first["text_for_embedding"].str.contains("Title:", regex=False).all()

    log = captured_logs[0]
    assert log["input_rows"] == 6
    assert log["output_rows"] == 6
    assert [event["type"] for event in log["events"]] == [
        "drop_latest_records",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "stale_published_date",
        "duplicate_record",
    ]


def test_corruption_validates_schema_and_minimum_rows(monkeypatch) -> None:
    monkeypatch.setattr(corruption_module, "write_json", lambda path, payload: None)
    with pytest.raises(ValueError, match="missing required columns"):
        corrupt_clean_dataframe(pd.DataFrame({"paper_id": ["x", "y"]}), Path("unused.json"))

    with pytest.raises(ValueError, match="At least two"):
        corrupt_clean_dataframe(_clean_dataframe().iloc[:1], Path("unused.json"))

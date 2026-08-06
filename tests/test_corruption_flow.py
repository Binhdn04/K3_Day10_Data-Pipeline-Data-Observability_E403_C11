from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import pipelines.corruption_flow as flow


def _settings() -> SimpleNamespace:
    paths = SimpleNamespace(
        clean_csv=Path("baseline.csv"),
        raw_records_json=Path("raw.json"),
        eval_testset=Path("test-set.json"),
        baseline_metrics=Path("baseline-metrics.json"),
        corruption_log=Path("corruption-log.json"),
        corrupted_clean_csv=Path("corrupted.csv"),
        corrupted_clean_json=Path("corrupted.json"),
        corrupted_embeddings_json=Path("corrupted-embeddings.json"),
        corrupted_metrics=Path("corrupted-metrics.json"),
        corrupted_answers=Path("corrupted-answers.json"),
        repaired_clean_csv=Path("repaired.csv"),
        repaired_clean_json=Path("repaired.json"),
        repaired_embeddings_json=Path("repaired-embeddings.json"),
        repaired_metrics=Path("repaired-metrics.json"),
        repaired_answers=Path("repaired-answers.json"),
        quality_dir=Path("quality"),
        comparison_report=Path("comparison.md"),
    )
    return SimpleNamespace(paths=paths)


def _frame(prefix: str, rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "paper_id": [f"{prefix}-{index}" for index in range(rows)],
            "title": [f"Title {index}" for index in range(rows)],
        }
    )


def test_flow_uses_same_testset_and_separate_corrupted_repaired_artifacts(monkeypatch) -> None:
    settings = _settings()
    baseline = _frame("baseline", 5)
    corrupted = _frame("corrupted", 4)
    repaired = _frame("repaired", 5)
    builds = []
    evaluations = []
    writes = []
    report_arguments = {}

    monkeypatch.setattr(flow, "_require_paths", lambda paths: None)
    monkeypatch.setattr(flow.pd, "read_csv", lambda path: baseline.copy())
    monkeypatch.setattr(flow, "read_json", lambda path: {"retrieval_hit_rate": 1.0})
    monkeypatch.setattr(flow, "corrupt_clean_dataframe", lambda df, path: corrupted.copy())
    monkeypatch.setattr(flow, "load_raw_records", lambda path: ["raw-record"])
    monkeypatch.setattr(flow, "build_clean_dataframe", lambda records, run_date: repaired.copy())
    monkeypatch.setattr(flow, "write_csv", lambda df, path: writes.append(("csv", path, len(df))))
    monkeypatch.setattr(flow, "write_json", lambda path, payload: writes.append(("json", path, len(payload))))

    class FakeIndex:
        @classmethod
        def build(cls, df, settings, embeddings_output_path):
            builds.append((embeddings_output_path, len(df)))
            return f"index:{embeddings_output_path}"

    def fake_evaluate(**kwargs):
        evaluations.append(kwargs)
        state = "corrupted" if kwargs["metrics_output_path"] == settings.paths.corrupted_metrics else "repaired"
        return SimpleNamespace(summary={"state": state})

    monkeypatch.setattr(flow, "LocalEmbeddingIndex", FakeIndex)
    monkeypatch.setattr(flow, "evaluate_pipeline", fake_evaluate)
    monkeypatch.setattr(
        flow,
        "run_data_quality_checks",
        lambda df, settings, report_name, expected_row_count=None: {
            "state": report_name,
            "expected": expected_row_count,
        },
    )
    monkeypatch.setattr(
        flow,
        "build_freshness_report",
        lambda df, settings, report_path: {"path": str(report_path)},
    )
    monkeypatch.setattr(flow, "generate_corruption_report", lambda **kwargs: report_arguments.update(kwargs))

    result = flow.run_corruption_flow(settings)

    assert builds == [
        (settings.paths.corrupted_embeddings_json, 4),
        (settings.paths.repaired_embeddings_json, 5),
    ]
    assert [call["test_set_path"] for call in evaluations] == [
        settings.paths.eval_testset,
        settings.paths.eval_testset,
    ]
    assert ("csv", settings.paths.corrupted_clean_csv, 4) in writes
    assert ("csv", settings.paths.repaired_clean_csv, 5) in writes
    assert report_arguments["corrupted_metrics"] == {"state": "corrupted"}
    assert report_arguments["repaired_metrics"] == {"state": "repaired"}
    assert result["baseline_rows"] == 5
    assert result["corrupted_rows"] == 4
    assert result["repaired_rows"] == 5


def test_flow_fails_fast_when_baseline_artifacts_are_missing() -> None:
    missing = Path("definitely-missing-baseline-artifact.json")
    with pytest.raises(FileNotFoundError, match="completed baseline artifacts"):
        flow._require_paths([missing])


def test_infer_baseline_run_date_reuses_age_reference() -> None:
    dataframe = pd.DataFrame(
        {
            "published": ["2026-01-01", "2026-02-10"],
            "age_days": [59, 19],
        }
    )

    inferred = flow._infer_baseline_run_date(dataframe)

    assert inferred.date().isoformat() == "2026-03-01"

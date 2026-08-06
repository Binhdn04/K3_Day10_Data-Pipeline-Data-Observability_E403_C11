from __future__ import annotations

from pathlib import Path
import os
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _configure_huggingface_auth() -> None:
    hf_key = os.getenv("HF_KEY")
    if hf_key:
        os.environ.setdefault("HF_TOKEN", hf_key)


def _require_paths(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        formatted = "\n- ".join(missing)
        raise FileNotFoundError(
            "Corruption flow requires completed baseline artifacts. Missing:\n- " + formatted
        )


def _write_dataframe_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _infer_baseline_run_date(baseline_df: pd.DataFrame):
    """Recover the cleaning reference date so repaired age_days is comparable to baseline."""
    if "published" not in baseline_df.columns or "age_days" not in baseline_df.columns:
        return now_utc()
    published = pd.to_datetime(baseline_df["published"], utc=True, errors="coerce")
    ages = pd.to_numeric(baseline_df["age_days"], errors="coerce")
    reference_dates = (published + pd.to_timedelta(ages, unit="D")).dropna().dt.normalize()
    if reference_dates.empty:
        return now_utc()
    return reference_dates.mode().iloc[0].to_pydatetime()


def run_corruption_flow(settings: Settings) -> dict[str, Any]:
    """Corrupt baseline data, repair it from raw, and compare both with the baseline."""
    _require_paths(
        [
            settings.paths.clean_csv,
            settings.paths.raw_records_json,
            settings.paths.eval_testset,
            settings.paths.baseline_metrics,
        ]
    )

    baseline_df = pd.read_csv(settings.paths.clean_csv)
    if baseline_df.empty:
        raise RuntimeError("Baseline clean dataset is empty; corruption flow cannot continue.")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    if not isinstance(baseline_metrics, dict) or not baseline_metrics:
        raise RuntimeError("Baseline metrics artifact is empty or invalid.")

    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    _write_dataframe_artifacts(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        report_name="corrupted",
        expected_row_count=len(baseline_df),
    )
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        report_path=settings.paths.quality_dir / "freshness_corrupted.json",
    )

    # Repair must be reproduced from the immutable raw snapshot, never by editing
    # the corrupted dataframe or copying the baseline answers/metrics.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(
        raw_records,
        run_date=_infer_baseline_run_date(baseline_df),
    )
    if repaired_df.empty:
        raise RuntimeError("Repair from raw records produced no valid rows.")
    _write_dataframe_artifacts(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(
        repaired_df,
        settings,
        report_name="repaired",
        expected_row_count=len(baseline_df),
    )
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        report_path=settings.paths.quality_dir / "freshness_repaired.json",
    )

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    return {
        "baseline_rows": len(baseline_df),
        "corrupted_rows": len(corrupted_df),
        "repaired_rows": len(repaired_df),
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_evaluation.summary,
        "repaired_metrics": repaired_evaluation.summary,
    }


def main() -> None:
    """Run the corruption, impact evaluation, raw repair, and comparison pipeline."""
    _configure_huggingface_auth()
    result = run_corruption_flow(load_settings())
    print(
        "Corruption flow completed: "
        f"baseline={result['baseline_rows']}, "
        f"corrupted={result['corrupted_rows']}, "
        f"repaired={result['repaired_rows']} rows."
    )

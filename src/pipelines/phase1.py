from __future__ import annotations

import os

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _load_or_fetch_records(settings: Settings):
    """Load the raw cache when possible, otherwise fetch and persist source data."""
    raw_path = settings.paths.raw_records_json
    if raw_path.exists() and not settings.refresh_source:
        return load_raw_records(raw_path), True
    return fetch_source_records(settings), False


def _write_clean_artifacts(df: pd.DataFrame, settings: Settings) -> None:
    """Persist the clean dataset in the formats used by later pipeline stages."""
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))


def _ensure_test_set(df: pd.DataFrame, settings: Settings) -> list[dict]:
    """Create the deterministic evaluation set unless a reusable one exists."""
    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        return read_json(settings.paths.eval_testset)
    return build_test_set(df, settings.paths.eval_testset)


def _configure_huggingface_auth() -> None:
    """Expose the project's HF_KEY under the variable used by huggingface_hub."""
    hf_key = os.getenv("HF_KEY")
    if hf_key:
        # Do not overwrite an explicitly configured standard Hugging Face token.
        os.environ.setdefault("HF_TOKEN", hf_key)


def main() -> None:
    """Run the clean-data baseline from source ingestion through reporting."""
    settings = load_settings()
    _configure_huggingface_auth()
    records, reused_raw = _load_or_fetch_records(settings)

    clean_df = build_clean_dataframe(records, run_date=now_utc())
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no valid records; cannot build a baseline index.")
    _write_clean_artifacts(clean_df, settings)

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    test_set = _ensure_test_set(clean_df, settings)
    if not test_set:
        raise RuntimeError("The evaluation set is empty; cannot evaluate the baseline.")

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness = build_freshness_report(
        clean_df,
        settings,
        report_path=settings.paths.freshness_report,
    )
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary={
            "source": settings.source_api,
            "query": settings.source_query,
            "filter": settings.source_filter,
            "raw_records": len(records),
            "clean_records": len(clean_df),
            "raw_cache_reused": reused_raw,
            "evaluation_samples": len(test_set),
            "embedding_model": settings.embedding_model,
        },
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

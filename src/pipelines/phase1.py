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
from retrieval.agent import build_agent, run_agent_question
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


def _run_agent_demo(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set: list[dict],
) -> dict:
    """Run one question per available type and persist evidence that the tool-using agent works."""
    selected: list[dict] = []
    seen_types: set[str] = set()
    for item in test_set:
        question_type = str(item.get("question_type", "unknown"))
        if question_type not in seen_types:
            selected.append(item)
            seen_types.add(question_type)

    payload = {
        "status": "completed",
        "provider": settings.llm_provider,
        "model": settings.model_name,
        "answers": [],
    }
    try:
        agent = build_agent(settings, index)
    except Exception as exc:
        payload["status"] = "unavailable"
        payload["error"] = f"{type(exc).__name__}: {exc}"
    else:
        for item in selected:
            try:
                answer = run_agent_question(agent, item["question"])
            except Exception as exc:
                payload["answers"].append(
                    {
                        "id": item["id"],
                        "question_type": item["question_type"],
                        "question": item["question"],
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            else:
                payload["answers"].append(
                    {
                        "id": item["id"],
                        "question_type": item["question_type"],
                        "question": item["question"],
                        "status": "completed",
                        "answer": answer,
                    }
                )
        if any(item["status"] == "error" for item in payload["answers"]):
            payload["status"] = "partial"

    write_json(settings.paths.demo_answers, payload)
    return payload


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
    agent_demo = _run_agent_demo(settings, index, test_set)
    quality = run_data_quality_checks(
        clean_df,
        settings,
        report_name="baseline",
        expected_row_count=len(clean_df),
    )
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
        agent_demo=agent_demo,
    )

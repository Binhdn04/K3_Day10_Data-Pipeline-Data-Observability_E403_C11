from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace, write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "authors_joined",
    "categories_joined",
    "text_for_embedding",
}
_NOISE_TEXT = "zxqv_noise_token corrupted_metadata " * 12


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return normalize_whitespace(str(value))


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {_text(row['title'])}",
            f"Authors: {_text(row['authors_joined']) or 'Unknown'}",
            f"Categories: {_text(row['categories_joined']) or 'Uncategorized'}",
            f"Published: {_text(row['published'])}",
            f"Abstract: {_text(row['summary'])}",
        ]
    )


def _event(
    corruption_type: str,
    paper_ids: list[str],
    parameters: dict[str, Any],
    before_count: int,
    after_count: int,
) -> dict[str, Any]:
    return {
        "type": corruption_type,
        "affected_paper_ids": paper_ids,
        "parameters": parameters,
        "before_count": before_count,
        "after_count": after_count,
    }


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create deterministic data-quality failures without mutating the baseline dataframe."""
    missing = sorted(_REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing)}")
    if len(df) < 2:
        raise ValueError("At least two clean records are required to create meaningful corruption.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    input_rows = len(corrupted)
    events: list[dict[str, Any]] = []

    # Drop roughly 10% of the newest papers, while always retaining at least one row.
    published_dates = pd.to_datetime(corrupted["published"], utc=True, errors="coerce")
    newest_order = published_dates.sort_values(ascending=False, na_position="last", kind="stable").index
    drop_count = min(max(1, round(input_rows * 0.10)), input_rows - 1)
    dropped_indices = newest_order[:drop_count].tolist()
    dropped_ids = corrupted.loc[dropped_indices, "paper_id"].astype(str).tolist()
    before_count = len(corrupted)
    corrupted = corrupted.drop(index=dropped_indices).reset_index(drop=True)
    events.append(
        _event(
            "drop_latest_records",
            dropped_ids,
            {"fraction": 0.10, "count": drop_count, "selection": "newest published first"},
            before_count,
            len(corrupted),
        )
    )

    # The remaining mutations use stable positions so repeated runs produce the same artifact.
    mutation_positions = [offset % len(corrupted) for offset in range(4)]

    blank_index = mutation_positions[0]
    blank_id = str(corrupted.at[blank_index, "paper_id"])
    original_summary = _text(corrupted.at[blank_index, "summary"])
    corrupted.at[blank_index, "summary"] = ""
    events.append(
        _event(
            "blank_summary",
            [blank_id],
            {"previous_chars": len(original_summary), "replacement": ""},
            len(corrupted),
            len(corrupted),
        )
    )

    noise_index = mutation_positions[1]
    noise_id = str(corrupted.at[noise_index, "paper_id"])
    original_noise_summary = _text(corrupted.at[noise_index, "summary"])
    corrupted.at[noise_index, "summary"] = normalize_whitespace(
        f"{original_noise_summary} {_NOISE_TEXT}"
    )
    events.append(
        _event(
            "inject_summary_noise",
            [noise_id],
            {"token": "zxqv_noise_token", "repeat": 12},
            len(corrupted),
            len(corrupted),
        )
    )

    title_index = mutation_positions[2]
    title_id = str(corrupted.at[title_index, "paper_id"])
    original_title = _text(corrupted.at[title_index, "title"])
    retained_chars = min(12, max(1, len(original_title) // 3))
    truncated_title = original_title[:retained_chars].rstrip()
    if len(truncated_title) < len(original_title):
        truncated_title += "..."
    corrupted.at[title_index, "title"] = truncated_title
    events.append(
        _event(
            "truncate_title",
            [title_id],
            {
                "original_chars": len(original_title),
                "retained_chars": len(truncated_title.removesuffix("...")),
            },
            len(corrupted),
            len(corrupted),
        )
    )

    stale_index = mutation_positions[3]
    stale_id = str(corrupted.at[stale_index, "paper_id"])
    original_published = _text(corrupted.at[stale_index, "published"])
    stale_published = "1900-01-01"
    corrupted.at[stale_index, "published"] = stale_published
    if "age_days" in corrupted.columns:
        original_date = pd.to_datetime(original_published, errors="coerce")
        stale_date = pd.Timestamp(stale_published)
        original_age = pd.to_numeric(pd.Series([corrupted.at[stale_index, "age_days"]]), errors="coerce").iloc[0]
        if pd.notna(original_date) and pd.notna(original_age):
            corrupted.at[stale_index, "age_days"] = int(original_age) + (original_date - stale_date).days
    events.append(
        _event(
            "stale_published_date",
            [stale_id],
            {"previous": original_published, "replacement": stale_published},
            len(corrupted),
            len(corrupted),
        )
    )

    # Rebuild derived fields after all content mutations.
    if "summary_chars" in corrupted.columns:
        corrupted["summary_chars"] = corrupted["summary"].map(lambda value: len(_text(value)))
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text_for_embedding, axis=1)

    duplicate_index = len(corrupted) - 1
    duplicate_id = str(corrupted.at[duplicate_index, "paper_id"])
    duplicate = corrupted.iloc[[duplicate_index]].copy(deep=True)
    before_count = len(corrupted)
    corrupted = pd.concat([corrupted, duplicate], ignore_index=True)
    events.append(
        _event(
            "duplicate_record",
            [duplicate_id],
            {"copies_added": 1, "duplicate_key": "paper_id"},
            before_count,
            len(corrupted),
        )
    )

    corruption_counts = {
        event["type"]: len(event["affected_paper_ids"]) for event in events
    }
    log_payload = {
        "version": 1,
        "deterministic": True,
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "corruption_counts": corruption_counts,
        "events": events,
    }
    write_json(Path(output_log_path), log_payload)
    return corrupted.reset_index(drop=True)

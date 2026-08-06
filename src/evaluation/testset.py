from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic factual evaluation set from cleaned source papers."""
    missing_columns = _REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing_columns)}")

    required_text = ["paper_id", "title", "summary", "published"]
    valid_text = pd.Series(True, index=df.index)
    for column in required_text:
        valid_text &= df[column].notna() & df[column].astype(str).str.strip().ne("")
    valid_dates = pd.to_datetime(df["published"], errors="coerce").notna()
    candidates = df.loc[valid_text & valid_dates].head(4)
    if len(candidates) < 4:
        raise ValueError(
            "At least 4 cleaned documents with paper_id, title, summary, and a valid "
            "published date are required to build the evaluation set."
        )

    items: list[dict[str, Any]] = []
    # The clean dataframe is already sorted by recency. Selecting a fixed first four
    # records makes all baseline/corruption/repair comparisons reproducible.
    for number, row in enumerate(candidates.to_dict(orient="records"), start=1):
        paper_id = normalize_whitespace(str(row["paper_id"]))
        title = normalize_whitespace(str(row["title"]))
        summary = normalize_whitespace(str(row["summary"]))
        authors = "" if pd.isna(row["authors_joined"]) else normalize_whitespace(str(row["authors_joined"]))
        categories = (
            ""
            if pd.isna(row["categories_joined"])
            else normalize_whitespace(str(row["categories_joined"]))
        )
        published = pd.Timestamp(row["published"]).date().isoformat()
        expected_doc_ids = [paper_id]

        question_specs = [
            ("summary", f"What is the main topic of the paper '{title}'?", first_sentence(summary)),
            ("date", f"When was the paper '{title}' published?", published),
        ]
        if authors:
            question_specs.insert(1, ("authors", f"Who authored the paper '{title}'?", authors))
        if categories:
            question_specs.append(
                (
                "categories",
                f"What categories does the paper '{title}' belong to?",
                    categories,
                )
            )
        for question_type, question, ground_truth in question_specs:
            if not ground_truth:
                continue
            items.append(
                {
                    "id": f"{question_type}-{number:03d}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": expected_doc_ids,
                }
            )

    if not items:
        raise ValueError("No non-empty evaluation questions could be generated from the clean dataset.")
    write_json(output_path, items)
    return items

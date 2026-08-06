from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import write_json


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
    if len(df) < 4:
        raise ValueError("At least 4 cleaned documents are required to build the evaluation set.")

    items: list[dict[str, Any]] = []
    # The clean dataframe is already sorted by recency. Selecting a fixed first four
    # records makes all baseline/corruption/repair comparisons reproducible.
    for number, row in enumerate(df.head(4).to_dict(orient="records"), start=1):
        paper_id = str(row["paper_id"])
        title = str(row["title"])
        published = pd.Timestamp(row["published"]).date().isoformat()
        expected_doc_ids = [paper_id]

        question_specs = [
            ("summary", f"What is the main topic of the paper '{title}'?", str(row["summary"])),
            ("authors", f"Who authored the paper '{title}'?", str(row["authors_joined"])),
            ("date", f"When was the paper '{title}' published?", published),
            (
                "categories",
                f"What categories does the paper '{title}' belong to?",
                str(row["categories_joined"]),
            ),
        ]
        for question_type, question, ground_truth in question_specs:
            items.append(
                {
                    "id": f"{question_type}-{number:03d}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": expected_doc_ids,
                }
            )

    write_json(output_path, items)
    return items

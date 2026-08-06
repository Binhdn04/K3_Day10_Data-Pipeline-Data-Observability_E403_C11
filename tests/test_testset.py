from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import evaluation.testset as testset_module
from evaluation.testset import build_test_set


def _clean_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "paper_id": f"10.9999/paper-{index}",
                "title": f"Paper {index}",
                "summary": f"First sentence for paper {index}. Second sentence must not be ground truth.",
                "authors_joined": f"Author {index}",
                "categories_joined": "Artificial Intelligence" if index == 0 else "",
                "published": f"2026-0{index + 1}-01",
            }
            for index in range(4)
        ]
    )


def test_build_test_set_never_emits_empty_ground_truth(monkeypatch) -> None:
    written = []
    monkeypatch.setattr(testset_module, "write_json", lambda path, payload: written.append(payload))

    items = build_test_set(_clean_dataframe(), Path("unused.json"))

    assert written == [items]
    assert all(item["ground_truth"].strip() for item in items)
    assert len([item for item in items if item["question_type"] == "summary"]) == 4
    assert len([item for item in items if item["question_type"] == "authors"]) == 4
    assert len([item for item in items if item["question_type"] == "date"]) == 4
    assert len([item for item in items if item["question_type"] == "categories"]) == 1
    assert items[0]["ground_truth"] == "First sentence for paper 0."


def test_build_test_set_skips_optional_questions_without_source_values(monkeypatch) -> None:
    monkeypatch.setattr(testset_module, "write_json", lambda path, payload: None)
    dataframe = _clean_dataframe()
    dataframe["authors_joined"] = ""
    dataframe["categories_joined"] = ""

    items = build_test_set(dataframe, Path("unused.json"))

    assert len(items) == 8
    assert {item["question_type"] for item in items} == {"summary", "date"}


def test_build_test_set_requires_four_valid_documents(monkeypatch) -> None:
    monkeypatch.setattr(testset_module, "write_json", lambda path, payload: None)
    dataframe = _clean_dataframe()
    dataframe.loc[0, "summary"] = ""

    with pytest.raises(ValueError, match="At least 4 cleaned documents"):
        build_test_set(dataframe, Path("unused.json"))

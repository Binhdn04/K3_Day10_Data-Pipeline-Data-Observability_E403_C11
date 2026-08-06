from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from retrieval.agent import _message_content_as_text
from retrieval.index import LocalEmbeddingIndex


def _clean_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "paper_id": "10.1000/example",
                "title": "A RAG Example",
                "summary": "A useful abstract.",
                "published": "2026-01-02",
                "authors_joined": "A. Author",
                "categories_joined": "Computer Science",
                "text_for_embedding": "Title: A RAG Example. Summary: A useful abstract.",
                "abs_url": "https://doi.org/10.1000/example",
                "pdf_url": None,
            }
        ]
    )


def test_build_documents_preserves_minimum_metadata_and_sanitizes_nulls() -> None:
    documents = LocalEmbeddingIndex._build_documents(_clean_dataframe())

    assert len(documents) == 1
    assert documents[0]["paper_id"] == "10.1000/example"
    assert documents[0]["metadata"]["title"] == "A RAG Example"
    assert documents[0]["metadata"]["pdf_url"] == ""


def test_build_documents_rejects_missing_or_blank_required_fields() -> None:
    missing_summary = _clean_dataframe().drop(columns=["summary"])
    with pytest.raises(ValueError, match="missing required columns: summary"):
        LocalEmbeddingIndex._build_documents(missing_summary)

    blank_content = _clean_dataframe()
    blank_content.loc[0, "text_for_embedding"] = "  "
    with pytest.raises(ValueError, match="text_for_embedding"):
        LocalEmbeddingIndex._build_documents(blank_content)


def test_collection_name_is_derived_from_the_three_manifest_paths() -> None:
    project_path = Path("project")
    paths = SimpleNamespace(
        embeddings_json=project_path / "baseline.json",
        corrupted_embeddings_json=project_path / "corrupted.json",
        repaired_embeddings_json=project_path / "repaired.json",
    )
    settings = SimpleNamespace(
        paths=paths,
        baseline_collection_name="papers-baseline",
        corrupted_collection_name="papers-corrupted",
        repaired_collection_name="papers-repaired",
    )

    assert LocalEmbeddingIndex._derive_collection_name(settings, paths.embeddings_json) == "papers-baseline"
    assert (
        LocalEmbeddingIndex._derive_collection_name(settings, paths.corrupted_embeddings_json)
        == "papers-corrupted"
    )
    assert LocalEmbeddingIndex._derive_collection_name(settings, paths.repaired_embeddings_json) == "papers-repaired"


class _FakeEmbeddingModel:
    def embed_query(self, query: str) -> list[float]:
        assert query == "rag"
        return [1.0, 0.0]


class _FakeCollection:
    def __init__(self) -> None:
        self.requested_results: int | None = None

    def count(self) -> int:
        return 1

    def query(self, **kwargs):
        self.requested_results = kwargs["n_results"]
        return {
            "ids": [["10.1000/example::0"]],
            "documents": [["RAG content"]],
            "metadatas": [[{"paper_id": "10.1000/example", "title": "A RAG Example"}]],
            "distances": [[0.25]],
        }


def test_search_caps_top_k_to_collection_size_and_converts_cosine_distance() -> None:
    index = object.__new__(LocalEmbeddingIndex)
    index.settings = SimpleNamespace(top_k=4)
    index.embedding_model = _FakeEmbeddingModel()
    index.collection = _FakeCollection()

    results = index.search("rag", top_k=10)

    assert index.collection.requested_results == 1
    assert results[0].paper_id == "10.1000/example"
    assert results[0].score == pytest.approx(0.75)


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_search_rejects_invalid_top_k(top_k) -> None:
    index = object.__new__(LocalEmbeddingIndex)
    index.settings = SimpleNamespace(top_k=4)
    index.embedding_model = _FakeEmbeddingModel()
    index.collection = _FakeCollection()

    with pytest.raises(ValueError, match="top_k"):
        index.search("rag", top_k=top_k)


def test_lookup_is_case_insensitive_and_message_blocks_are_normalized() -> None:
    document = {"paper_id": "10.1000/Example", "title": "A RAG Example"}
    index = object.__new__(LocalEmbeddingIndex)
    index.documents_by_paper_id = {"10.1000/example": document}
    index.documents_by_title = {"a rag example": document}

    assert index.lookup(" 10.1000/EXAMPLE ") is document
    assert index.lookup("a rag EXAMPLE") is document
    assert index.lookup("  ") is None
    assert _message_content_as_text([{"type": "text", "text": "first"}, "second"]) == "first\nsecond"

from __future__ import annotations

from datetime import UTC, datetime

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord


def _record(*, paper_id: str, title: str, updated: str) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=f"Abstract for {title}.",
        authors=["A. Author", "A. Author"],
        categories=["AI", "ai"],
        primary_category="AI",
        published="2026-01-01",
        updated=updated,
        abs_url="https://doi.org/example",
        pdf_url="",
        comment="Journal",
    )


def test_cleaning_deduplicates_doi_case_insensitively_and_keeps_latest_update() -> None:
    older = _record(paper_id="10.9999/EXAMPLE", title="Older title", updated="2026-01-02")
    newer = _record(paper_id="10.9999/example", title="Newer title", updated="2026-02-03")

    dataframe = build_clean_dataframe(
        [older, newer],
        run_date=datetime(2026, 3, 1, tzinfo=UTC),
    )

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["title"] == "Newer title"
    assert dataframe.iloc[0]["updated"] == "2026-02-03"
    assert dataframe.iloc[0]["authors"] == ["A. Author"]
    assert dataframe.iloc[0]["categories"] == ["AI"]
    assert dataframe.iloc[0]["age_days"] == 59

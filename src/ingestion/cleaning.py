from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


_CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def _clean_text(value: object) -> str:
    """Convert nullable source values into normalized text."""
    if value is None or pd.isna(value):
        return ""
    return normalize_whitespace(str(value))


def _clean_list(values: list[str] | None) -> list[str]:
    """Normalize a text list and remove duplicates while preserving its order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _clean_text(value)
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Return a normalized, deduplicated dataframe ready for retrieval indexing."""
    normalized_run_date = pd.Timestamp(run_date)
    if normalized_run_date.tzinfo is None:
        normalized_run_date = normalized_run_date.tz_localize(UTC)
    else:
        normalized_run_date = normalized_run_date.tz_convert(UTC)

    rows: list[dict[str, object]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        published = pd.to_datetime(record.published, utc=True, errors="coerce")
        updated = pd.to_datetime(record.updated, utc=True, errors="coerce")

        # A paper without a stable identifier, title, abstract, or publication date
        # cannot be reliably indexed, evaluated, or monitored for freshness.
        if not paper_id or not title or not summary or pd.isna(published):
            continue

        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        primary_category = _clean_text(record.primary_category)
        if primary_category and primary_category.casefold() not in {item.casefold() for item in categories}:
            categories.insert(0, primary_category)
        if not primary_category and categories:
            primary_category = categories[0]

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published_date = published.date().isoformat()
        updated_date = "" if pd.isna(updated) else updated.date().isoformat()
        age_days = max(0, (normalized_run_date.normalize() - published.normalize()).days)
        text_for_embedding = "\n".join(
            [
                f"Title: {title}",
                f"Authors: {authors_joined or 'Unknown'}",
                f"Categories: {categories_joined or 'Uncategorized'}",
                f"Published: {published_date}",
                f"Abstract: {summary}",
            ]
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published_date,
                "updated": updated_date,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows, columns=_CLEAN_COLUMNS)
    if df.empty:
        return df

    # DOI matching is case-insensitive; retain the most recently updated instance.
    df["_paper_id_key"] = df["paper_id"].str.casefold()
    df = df.drop_duplicates(subset=["_paper_id_key"], keep="first").drop(columns="_paper_id_key")
    return df.sort_values(["published", "paper_id"], ascending=[False, True], kind="stable").reset_index(drop=True)

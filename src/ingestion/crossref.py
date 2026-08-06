from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import compact_join, normalize_whitespace, read_json, write_json

CROSSREF_API_URL = "https://api.crossref.org/works"
REQUEST_HEADERS = {"User-Agent": "day10-data-pipeline-lab (mailto:student@example.com)"}
RETRYABLE_STATUS_CODES = {429, 503}


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _extract_date(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        parts = (item.get(key) or {}).get("date-parts")
        if not parts or not parts[0]:
            continue
        year, *rest = parts[0]
        month = rest[0] if len(rest) > 0 else 1
        day = rest[1] if len(rest) > 1 else 1
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return f"{year:04d}-01-01"
    return ""


def _strip_html(value: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", value))


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    items = (payload.get("message") or {}).get("items") or []
    records: list[PaperRecord] = []

    for item in items:
        doi = (item.get("DOI") or "").strip()
        titles = item.get("title") or []
        title = normalize_whitespace(titles[0]) if titles else ""
        summary = _strip_html(item.get("abstract") or "")
        if not doi or not title or not summary:
            continue

        authors = [
            normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
            for author in item.get("author") or []
            if author.get("given") or author.get("family")
        ]
        categories = [normalize_whitespace(subject) for subject in item.get("subject") or [] if subject]
        primary_category = categories[0] if categories else ""

        published = _extract_date(item, ("published-print", "published-online", "published", "created"))
        updated = _extract_date(item, ("indexed", "deposited")) or published

        abs_url = item.get("URL") or f"https://doi.org/{doi}"
        pdf_url = next(
            (
                link.get("URL", "")
                for link in item.get("link") or []
                if link.get("content-type") == "application/pdf" or "pdf" in link.get("URL", "").lower()
            ),
            "",
        )
        comment = compact_join(item.get("container-title") or [])

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def _get_with_retry(url: str, params: dict[str, Any], max_attempts: int = 5) -> dict:
    backoff_seconds = 1.0
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30)
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
            last_error = RuntimeError(f"Crossref returned HTTP {response.status_code}")

        if attempt < max_attempts:
            time.sleep(backoff_seconds)
            backoff_seconds *= 2

    raise RuntimeError(f"Failed to fetch Crossref data after {max_attempts} attempts") from last_error


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    raw_response = _get_with_retry(CROSSREF_API_URL, params)
    write_json(settings.paths.raw_api_response, raw_response)

    records = parse_crossref_payload(raw_response)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    payload = read_json(path)
    return [PaperRecord(**item) for item in payload]

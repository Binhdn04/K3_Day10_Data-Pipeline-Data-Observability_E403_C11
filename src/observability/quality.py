from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tạo và chạy bộ data quality checks trên DataFrame dữ liệu.

    Thực hiện các kiểm tra:
    1. Row count (DataFrame không được rỗng)
    2. paper_id not null và unique
    3. title not null và không rỗng
    4. summary không rỗng và đủ độ dài tối thiểu
    5. age_days <= freshness_threshold_days (độ tươi dữ liệu)

    Ghi kết quả JSON vào settings.paths.quality_dir / f"{report_name}.json"
    """
    total_rows = len(df)
    checks: list[dict[str, Any]] = []

    # 1. Row count check
    has_rows = total_rows > 0
    checks.append({
        "check": "row_count_check",
        "passed": has_rows,
        "details": f"Total rows: {total_rows}",
        "value": total_rows,
    })

    # 2. paper_id null & uniqueness check
    if "paper_id" in df.columns and total_rows > 0:
        paper_id_nulls = int(df["paper_id"].isna().sum())
        paper_id_duplicates = int(df["paper_id"].duplicated().sum())
        passed_paper_id = (paper_id_nulls == 0) and (paper_id_duplicates == 0)
        checks.append({
            "check": "paper_id_null_and_unique",
            "passed": passed_paper_id,
            "details": f"Nulls: {paper_id_nulls}, Duplicates: {paper_id_duplicates}",
            "value": {"nulls": paper_id_nulls, "duplicates": paper_id_duplicates},
        })
    else:
        checks.append({
            "check": "paper_id_null_and_unique",
            "passed": False,
            "details": "Column 'paper_id' missing or DataFrame empty",
            "value": None,
        })

    # 3. title null & empty check
    if "title" in df.columns and total_rows > 0:
        title_nulls = int(df["title"].isna().sum())
        empty_titles = int((df["title"].astype(str).str.strip() == "").sum())
        passed_title = (title_nulls == 0) and (empty_titles == 0)
        checks.append({
            "check": "title_not_null_or_empty",
            "passed": passed_title,
            "details": f"Nulls: {title_nulls}, Empty: {empty_titles}",
            "value": {"nulls": title_nulls, "empty": empty_titles},
        })
    else:
        checks.append({
            "check": "title_not_null_or_empty",
            "passed": False,
            "details": "Column 'title' missing or DataFrame empty",
            "value": None,
        })

    # 4. summary length & validity check
    if "summary" in df.columns and total_rows > 0:
        summary_nulls = int(df["summary"].isna().sum())
        empty_summaries = int((df["summary"].astype(str).str.strip() == "").sum())
        short_summaries = int((df["summary"].astype(str).str.strip().str.len() < 20).sum())
        passed_summary = (summary_nulls == 0) and (empty_summaries == 0) and (short_summaries == 0)
        checks.append({
            "check": "summary_validity",
            "passed": passed_summary,
            "details": f"Nulls: {summary_nulls}, Empty: {empty_summaries}, Short (<20 chars): {short_summaries}",
            "value": {"nulls": summary_nulls, "empty": empty_summaries, "short": short_summaries},
        })
    else:
        checks.append({
            "check": "summary_validity",
            "passed": False,
            "details": "Column 'summary' missing or DataFrame empty",
            "value": None,
        })

    # 5. Freshness check by age_days
    threshold = settings.freshness_threshold_days
    if "age_days" in df.columns and total_rows > 0:
        stale_count = int((df["age_days"] > threshold).sum())
        passed_freshness = (stale_count == 0)
        checks.append({
            "check": "freshness_check",
            "passed": passed_freshness,
            "details": f"Stale rows (> {threshold} days): {stale_count} / {total_rows}",
            "value": {"stale_rows": stale_count, "threshold_days": threshold},
        })
    else:
        checks.append({
            "check": "freshness_check",
            "passed": False,
            "details": "Column 'age_days' missing or DataFrame empty",
            "value": None,
        })

    overall_passed = all(check["passed"] for check in checks)
    passed_count = sum(1 for check in checks if check["passed"])

    report_payload = {
        "report_name": report_name,
        "timestamp": now_utc().isoformat(),
        "total_rows": total_rows,
        "passed": overall_passed,
        "passed_checks_count": passed_count,
        "total_checks_count": len(checks),
        "checks": checks,
    }

    # Format filename safely
    file_name = report_name if report_name.endswith(".json") else f"{report_name}.json"
    output_path = settings.paths.quality_dir / file_name
    write_json(output_path, report_payload)

    return report_payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str) -> dict[str, Any]:
    """Tổng hợp freshness report của dataset và ghi ra file JSON.

    Các chỉ số:
    - latest_published: Ngày xuất bản mới nhất
    - oldest_published: Ngày xuất bản cũ nhất
    - stale_rows: Số dòng quá hạn freshness_threshold_days
    - total_rows: Tổng số bản ghi
    - is_fresh: Trạng thái dữ liệu tươi (stale_rows == 0)
    """
    total_rows = len(df)
    threshold = settings.freshness_threshold_days

    latest_pub = None
    oldest_pub = None
    stale_rows = 0

    if total_rows > 0:
        if "published" in df.columns:
            pub_series = pd.to_datetime(df["published"], errors="coerce")
            valid_pub = pub_series.dropna()
            if not valid_pub.empty:
                latest_pub = str(valid_pub.max().date())
                oldest_pub = str(valid_pub.min().date())

        if "age_days" in df.columns:
            stale_rows = int((df["age_days"] > threshold).sum())

    is_fresh = (stale_rows == 0) and (total_rows > 0)

    payload = {
        "report_path": str(report_path),
        "timestamp": now_utc().isoformat(),
        "latest_published": latest_pub,
        "oldest_published": oldest_pub,
        "freshness_threshold_days": threshold,
        "stale_rows": stale_rows,
        "fresh_rows": total_rows - stale_rows,
        "total_rows": total_rows,
        "is_fresh": is_fresh,
    }

    write_json(Path(report_path), payload)
    return payload


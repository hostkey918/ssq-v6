from __future__ import annotations

import csv
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import requests
from dateutil.parser import parse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Draw
from app.schemas import SyncResult

CWL_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
ZHCW_SSQ_URL = "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp"
SEED_CSV_PATH = Path(__file__).resolve().parent / "data" / "ssq_draws_seed.csv"
ZHCW_ROW_RE = re.compile(
    r"<tr>\s*"
    r"<td[^>]*>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</td>\s*"
    r"<td[^>]*>\s*(?P<issue>\d{7})\s*</td>\s*"
    r"<td[^>]*style=\"padding-left:10px;\"[^>]*>(?P<numbers>.*?)</td>",
    re.S,
)
ZHCW_MAX_PAGE_RE = re.compile(r"共\s*<strong>\s*(\d+)\s*</strong>\s*页")
ZHCW_NUMBER_RE = re.compile(r"<em(?:\s+class=\"rr\")?\s*>\s*(\d{1,2})\s*</em>")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return parse(match.group(0) if match else value).date()


def fetch_cwl_draws(issue_count: int | None = None) -> list[dict[str, object]]:
    settings = get_settings()
    params = {
        "name": "ssq",
        "issueCount": issue_count or settings.fetch_issue_count,
    }
    response = requests.get(
        CWL_URL,
        params=params,
        headers={"User-Agent": "SSQ-V6/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("result") or []

    draws: list[dict[str, object]] = []
    for row in rows:
        reds = [int(part) for part in str(row["red"]).split(",")]
        if len(reds) != 6:
            continue
        draws.append(
            {
                "issue": str(row["code"]),
                "draw_date": _parse_date(row.get("date")),
                "reds": sorted(reds),
                "blue": int(row["blue"]),
                "source": "cwl",
            }
        )
    return draws


def fetch_seed_draws(seed_path: Path = SEED_CSV_PATH) -> list[dict[str, object]]:
    if not seed_path.exists():
        return []

    draws: list[dict[str, object]] = []
    with seed_path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            reds = [int(row[f"r{i}"]) for i in range(1, 7)]
            draws.append(
                {
                    "issue": str(row["issue"]),
                    "draw_date": _parse_date(row.get("date")),
                    "reds": sorted(reds),
                    "blue": int(row["b"]),
                    "source": "seed",
                }
            )
    return draws


def fetch_zhcw_draws(
    start_page: int = 1,
    end_page: int | None = None,
    delay_seconds: float = 0.08,
) -> tuple[list[dict[str, object]], int, list[str]]:
    first_html = _download_zhcw_page(start_page)
    first_draws, max_page = parse_zhcw_page(first_html)
    resolved_end = end_page or max_page or start_page
    resolved_end = max(start_page, resolved_end)

    rows: list[dict[str, object]] = []
    errors: list[str] = []
    pages_ok = 0
    for page_num in range(start_page, resolved_end + 1):
        try:
            if page_num == start_page:
                page_rows = first_draws
            else:
                html = _download_zhcw_page(page_num)
                page_rows, _ = parse_zhcw_page(html)
            if not page_rows:
                errors.append(f"第 {page_num} 页未解析到开奖数据")
                continue
            pages_ok += 1
            rows.extend(page_rows)
        except Exception as exc:
            errors.append(f"第 {page_num} 页抓取失败：{exc}")
        if delay_seconds and page_num < resolved_end:
            time.sleep(delay_seconds)
    return rows, pages_ok, errors


def parse_zhcw_page(html: str) -> tuple[list[dict[str, object]], int | None]:
    rows = []
    for match in ZHCW_ROW_RE.finditer(html):
        numbers = [int(value) for value in ZHCW_NUMBER_RE.findall(match.group("numbers"))]
        if len(numbers) != 7:
            continue
        rows.append(
            {
                "issue": match.group("issue"),
                "draw_date": parse(match.group("date")).date(),
                "reds": sorted(numbers[:6]),
                "blue": numbers[6],
                "source": "zhcw",
            }
        )

    max_page_match = ZHCW_MAX_PAGE_RE.search(html)
    max_page = int(max_page_match.group(1)) if max_page_match else None
    return rows, max_page


def _download_zhcw_page(page_num: int, retries: int = 3) -> str:
    query = urllib.parse.urlencode({"pageNum": int(page_num)})
    url = f"{ZHCW_SSQ_URL}?{query}"
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * attempt)
    raise RuntimeError(last_error)


def sync_draws(
    db: Session,
    issue_count: int | None = None,
    source: str = "zhcw",
    start_page: int = 1,
    end_page: int | None = None,
) -> SyncResult:
    pages_ok = None
    errors: list[str] = []
    if source == "cwl":
        rows = fetch_cwl_draws(issue_count)
    elif source == "seed":
        rows = fetch_seed_draws()
    else:
        rows, pages_ok, errors = fetch_zhcw_draws(start_page=start_page, end_page=end_page)

    inserted = 0
    updated = 0

    for row in rows:
        existing = db.query(Draw).filter(Draw.issue == row["issue"]).one_or_none()
        reds = row["reds"]
        data = {
            "draw_date": row["draw_date"],
            "red1": reds[0],
            "red2": reds[1],
            "red3": reds[2],
            "red4": reds[3],
            "red5": reds[4],
            "red6": reds[5],
            "blue": row["blue"],
            "source": row["source"],
        }
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(Draw(issue=row["issue"], **data))
            inserted += 1

    db.commit()
    return SyncResult(
        fetched=len(rows),
        inserted=inserted,
        updated=updated,
        source=source,
        pages_ok=pages_ok,
        errors=errors,
    )

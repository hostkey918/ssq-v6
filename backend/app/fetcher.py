from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path

import requests
from dateutil.parser import parse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Draw
from app.schemas import SyncResult

CWL_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
ZHCW_SSQ_URL = "https://kaijiang.zhcw.com/zhcw/inc/ssq/ssq_wqhg.jsp"
YDN_OPENING_URL = "http://www.ydniu.com/open/ssqkjh.html"
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
SCRIPT_JSON_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    re.S | re.I,
)
OPENING_FALLBACK_RE = re.compile(
    r"(?P<issue>\d{5,7})\s*期.{0,120}?"
    r"(?P<reds>\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+\d{2})\s*\+\s*(?P<blue>\d{2})",
    re.S,
)


@dataclass(frozen=True)
class OpeningNumber:
    issue: str
    draw_date: date | None
    reds: list[int]
    blue: int
    source: str = "ydniu"

    @property
    def key(self) -> str:
        return "-".join(f"{number:02d}" for number in sorted(self.reds)) + f"+{self.blue:02d}"


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


def fetch_latest_draws(issue_count: int | None = None) -> tuple[list[dict[str, object]], list[str]]:
    count = issue_count or 5
    errors: list[str] = []
    for source_name, fetch in (
        ("cwl", lambda: fetch_cwl_draws(count)),
        ("zhcw", lambda: fetch_zhcw_draws(start_page=1, end_page=1)[0]),
    ):
        try:
            rows = fetch()
            if rows:
                return rows, errors
            errors.append(f"{source_name}: no rows returned")
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
    return [], errors


def fetch_latest_opening_number() -> OpeningNumber | None:
    response = requests.get(
        YDN_OPENING_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Connection": "close",
        },
        timeout=(3, 8),
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    html = response.text
    return parse_opening_number_page(html)


def parse_opening_number_page(html: str) -> OpeningNumber | None:
    for match in SCRIPT_JSON_RE.finditer(html):
        script = unescape(match.group("body")).strip()
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        opening = _find_opening_number(payload)
        if opening:
            return opening

    fallback = OPENING_FALLBACK_RE.search(re.sub(r"<[^>]+>", " ", html))
    if not fallback:
        return None
    return OpeningNumber(
        issue=fallback.group("issue"),
        draw_date=None,
        reds=sorted(int(value) for value in fallback.group("reds").split()),
        blue=int(fallback.group("blue")),
    )


def _find_opening_number(node: object) -> OpeningNumber | None:
    if isinstance(node, dict):
        if "openingNumber" in node:
            opening = node.get("openingNumber") or {}
            reds = opening.get("redBalls") or []
            blue = opening.get("blueBall")
            if len(reds) == 6 and blue:
                return OpeningNumber(
                    issue=str(node.get("drawNumber") or ""),
                    draw_date=_parse_date(str(node.get("date") or "")),
                    reds=sorted(int(value) for value in reds),
                    blue=int(blue),
                )
        for value in node.values():
            found = _find_opening_number(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_opening_number(value)
            if found:
                return found
    return None


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
    source: str = "latest",
    start_page: int = 1,
    end_page: int | None = None,
) -> SyncResult:
    pages_ok = None
    errors: list[str] = []
    if source == "latest":
        rows, errors = fetch_latest_draws(issue_count)
    elif source == "cwl":
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

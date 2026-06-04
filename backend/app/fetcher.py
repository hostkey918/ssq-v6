from __future__ import annotations

import re
from datetime import date

import requests
from dateutil.parser import parse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Draw
from app.schemas import SyncResult

CWL_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"


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


def sync_draws(db: Session, issue_count: int | None = None) -> SyncResult:
    rows = fetch_cwl_draws(issue_count)
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
    return SyncResult(fetched=len(rows), inserted=inserted, updated=updated)

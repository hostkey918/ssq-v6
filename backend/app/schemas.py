from datetime import date

from pydantic import BaseModel, Field


class DrawOut(BaseModel):
    issue: str
    draw_date: date | None = None
    reds: list[int]
    blue: int


class SyncResult(BaseModel):
    fetched: int
    inserted: int
    updated: int


class FilterConfig(BaseModel):
    exclude_history: bool = True
    reject_three_consecutive: bool = True
    reject_four_consecutive: bool = True
    sum_min: int = 70
    sum_max: int = 130
    ac_min: int = 7
    ac_max: int = 12
    max_red_repeat: int = 2
    reject_blue_repeat: bool = False


class GenerateRequest(BaseModel):
    top_n: int = Field(default=50, ge=1, le=200)
    candidate_pool: int = Field(default=20000, ge=100, le=200000)
    filters: FilterConfig = Field(default_factory=FilterConfig)


class CandidateOut(BaseModel):
    rank: int
    reds: list[int]
    blue: int
    score: float
    sum_value: int
    ac_value: int
    red_repeat: int
    blue_repeat: bool
    reasons: list[str]


class StatsOut(BaseModel):
    total_draws: int
    latest_issue: str | None
    latest_date: date | None

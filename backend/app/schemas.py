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
    source: str = "cwl"
    pages_ok: int | None = None
    errors: list[str] = Field(default_factory=list)


class FilterConfig(BaseModel):
    exclude_history: bool = True
    history_overlap: str = Field(default="similar5", pattern="^(none|exact|similar5)$")
    exclude_numbers: list[int] = Field(default_factory=list)
    exclude_blues: list[int] = Field(default_factory=list)
    dan_numbers: list[int] = Field(default_factory=list)
    kill_tails: list[int] = Field(default_factory=list)
    reject_three_consecutive: bool = True
    reject_four_consecutive: bool = True
    allow_two_consecutive: bool = True
    sum_min: int = 70
    sum_max: int = 130
    span_min: int = 14
    span_max: int = 32
    ac_min: int = 7
    ac_max: int = 12
    odd_even: str = "any"
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
    span: int
    odd_even: str
    zone_ratio: str
    ac_value: int
    red_repeat: int
    blue_repeat: bool
    consecutive: str
    same_tail: str
    reasons: list[str]


class StatsOut(BaseModel):
    total_draws: int
    latest_issue: str | None
    latest_date: date | None

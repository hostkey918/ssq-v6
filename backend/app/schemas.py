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
    source: str = "latest"
    pages_ok: int | None = None
    errors: list[str] = Field(default_factory=list)


class OpeningNumberOut(BaseModel):
    issue: str
    draw_date: date | None = None
    reds: list[int]
    blue: int
    source: str


class FilterConfig(BaseModel):
    exclude_history: bool = True
    exclude_latest_opening: bool = True
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
    use_expert_signals: bool = True
    expert_weight: float = Field(default=6.0, ge=0, le=20)
    soft_red_dan: list[int] = Field(default_factory=list)
    soft_red_kill: list[int] = Field(default_factory=list)
    soft_blue_dan: list[int] = Field(default_factory=list)
    soft_blue_kill: list[int] = Field(default_factory=list)
    soft_kill_tails: list[int] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    top_n: int = Field(default=50, ge=1, le=200)
    candidate_pool: int = Field(default=20000, ge=100, le=200000)
    filters: FilterConfig = Field(default_factory=FilterConfig)


class CandidateOut(BaseModel):
    rank: int
    reds: list[int]
    blue: int
    score: float
    expert_score: float = 0.0
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


class ExpertSignalIn(BaseModel):
    source: str = "manual"
    issue: str | None = None
    text: str = Field(min_length=2)
    weight: float = Field(default=1.0, ge=0.1, le=5.0)


class ExpertFetchRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=5)
    issue: str | None = None
    weight: float = Field(default=1.0, ge=0.1, le=5.0)


class ExpertSignalOut(BaseModel):
    id: int
    issue: str | None
    source: str
    source_url: str | None
    red_dan: list[int]
    red_kill: list[int]
    blue_dan: list[int]
    blue_kill: list[int]
    kill_tails: list[int]
    weight: float


class NumberWeight(BaseModel):
    number: int
    weight: float


class ExpertConsensusOut(BaseModel):
    total_signals: int
    red_dan: list[NumberWeight]
    red_kill: list[NumberWeight]
    blue_dan: list[NumberWeight]
    blue_kill: list[NumberWeight]
    kill_tails: list[NumberWeight]

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.database import SessionLocal
from app.expert import (
    build_consensus,
    compact_numbers,
    content_hash,
    download_expert_text,
    parse_expert_text,
    signal_to_out,
    source_name_from_url,
)
from app.fetcher import fetch_latest_opening_number, sync_draws
from app.logic import generate_candidates
from app.models import Draw, ExpertSignal
from app.scheduler import create_scheduler
from app.schemas import (
    CandidateOut,
    DrawOut,
    ExpertConsensusOut,
    ExpertFetchRequest,
    ExpertSignalIn,
    ExpertSignalOut,
    GenerateRequest,
    OpeningNumberOut,
    StatsOut,
    SyncResult,
)

settings = get_settings()
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    Base.metadata.create_all(bind=engine)
    if settings.seed_draws_on_startup:
        db = SessionLocal()
        try:
            if db.query(func.count(Draw.id)).scalar() == 0:
                sync_draws(db, source="seed")
        finally:
            db.close()
    if settings.auto_sync_on_startup:
        db = SessionLocal()
        try:
            if db.query(func.count(Draw.id)).scalar() == 0:
                sync_draws(db, source=settings.auto_sync_source)
        finally:
            db.close()
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="7.0.0", lifespan=lifespan)
origins = ["*"] if settings.cors_origins == "*" else [item.strip() for item in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _draw_out(draw: Draw) -> DrawOut:
    return DrawOut(issue=draw.issue, draw_date=draw.draw_date, reds=draw.reds, blue=draw.blue)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    return {
        "status": "ok",
        "version": "7.0.0",
        "commit": os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or None,
        "branch": os.getenv("RENDER_GIT_BRANCH") or None,
        "draw_count": db.query(func.count(Draw.id)).scalar() or 0,
    }


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    latest = db.query(Draw).order_by(desc(Draw.issue)).first()
    return StatsOut(
        total_draws=db.query(func.count(Draw.id)).scalar() or 0,
        latest_issue=latest.issue if latest else None,
        latest_date=latest.draw_date if latest else None,
    )


@app.get("/api/draws", response_model=list[DrawOut])
def list_draws(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DrawOut]:
    draws = db.query(Draw).order_by(desc(Draw.issue)).offset(offset).limit(limit).all()
    return [_draw_out(draw) for draw in draws]


@app.post("/api/sync", response_model=SyncResult)
def sync(
    issue_count: int | None = Query(default=None, ge=1, le=10000),
    source: str = Query(default="latest", pattern="^(latest|zhcw|cwl|seed)$"),
    start_page: int = Query(default=1, ge=1, le=300),
    end_page: int | None = Query(default=None, ge=1, le=300),
    db: Session = Depends(get_db),
) -> SyncResult:
    try:
        return sync_draws(
            db,
            issue_count=issue_count,
            source=source,
            start_page=start_page,
            end_page=end_page,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"抓取开奖数据失败: {exc}") from exc


@app.get("/api/opening-number/latest", response_model=OpeningNumberOut)
def latest_opening_number() -> OpeningNumberOut:
    try:
        opening = fetch_latest_opening_number()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"抓取开机号失败: {exc}") from exc
    if not opening:
        raise HTTPException(status_code=404, detail="未找到最新开机号")
    return OpeningNumberOut(
        issue=opening.issue,
        draw_date=opening.draw_date,
        reds=opening.reds,
        blue=opening.blue,
        source=opening.source,
    )


@app.post("/api/generate", response_model=list[CandidateOut])
def generate(request: GenerateRequest, db: Session = Depends(get_db)) -> list[CandidateOut]:
    draws = db.query(Draw).order_by(desc(Draw.issue)).all()
    if not draws:
        raise HTTPException(status_code=400, detail="历史开奖为空，请先同步数据")
    expert_signals = db.query(ExpertSignal).order_by(desc(ExpertSignal.created_at)).limit(30).all()
    opening_number = None
    if request.filters.exclude_latest_opening:
        try:
            opening_number = fetch_latest_opening_number()
        except Exception:
            opening_number = None
    return generate_candidates(
        draws=draws,
        filters=request.filters,
        top_n=request.top_n,
        candidate_pool=request.candidate_pool,
        expert_signals=expert_signals,
        opening_number=opening_number,
    )


@app.get("/api/expert-signals", response_model=list[ExpertSignalOut])
def list_expert_signals(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ExpertSignalOut]:
    signals = db.query(ExpertSignal).order_by(desc(ExpertSignal.created_at)).limit(limit).all()
    return [ExpertSignalOut(**signal_to_out(signal)) for signal in signals]


@app.get("/api/expert-signals/consensus", response_model=ExpertConsensusOut)
def expert_consensus(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ExpertConsensusOut:
    signals = db.query(ExpertSignal).order_by(desc(ExpertSignal.created_at)).limit(limit).all()
    return ExpertConsensusOut(**build_consensus(signals))


@app.post("/api/expert-signals/import", response_model=ExpertSignalOut)
def import_expert_signal(payload: ExpertSignalIn, db: Session = Depends(get_db)) -> ExpertSignalOut:
    signal = _save_expert_signal(
        db=db,
        source=payload.source,
        source_url=None,
        raw_text=payload.text,
        issue=payload.issue,
        weight=payload.weight,
    )
    return ExpertSignalOut(**signal_to_out(signal))


@app.post("/api/expert-signals/fetch", response_model=list[ExpertSignalOut])
def fetch_expert_signals(
    payload: ExpertFetchRequest | None = None,
    db: Session = Depends(get_db),
) -> list[ExpertSignalOut]:
    payload = payload or ExpertFetchRequest()
    configured_urls = [url.strip() for url in settings.expert_source_urls.split(",") if url.strip()]
    urls = payload.urls or configured_urls
    if not urls:
        raise HTTPException(status_code=400, detail="未配置专家信号来源 URL")

    saved: list[ExpertSignal] = []
    errors: list[str] = []
    for url in urls[:5]:
        try:
            text = download_expert_text(url)
            saved.append(
                _save_expert_signal(
                    db=db,
                    source=source_name_from_url(url),
                    source_url=url,
                    raw_text=text,
                    issue=payload.issue,
                    weight=payload.weight,
                )
            )
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if not saved and errors:
        raise HTTPException(status_code=502, detail="；".join(errors))
    return [ExpertSignalOut(**signal_to_out(signal)) for signal in saved]


def _save_expert_signal(
    db: Session,
    source: str,
    source_url: str | None,
    raw_text: str,
    issue: str | None,
    weight: float,
) -> ExpertSignal:
    parsed = parse_expert_text(raw_text)
    digest = content_hash(raw_text, source_url)
    existing = db.query(ExpertSignal).filter(ExpertSignal.content_hash == digest).one_or_none()
    if existing:
        return existing

    signal = ExpertSignal(
        issue=issue or parsed["issue"],
        source=source[:120] or "unknown",
        source_url=source_url,
        content_hash=digest,
        red_dan=compact_numbers(parsed["red_dan"]),
        red_kill=compact_numbers(parsed["red_kill"]),
        blue_dan=compact_numbers(parsed["blue_dan"]),
        blue_kill=compact_numbers(parsed["blue_kill"]),
        kill_tails=compact_numbers(parsed["kill_tails"]),
        weight=weight,
        raw_text=raw_text[:20000],
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


static_dir = Path(__file__).resolve().parents[1] / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        index = static_dir / "index.html"
        requested = static_dir / path
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(index)

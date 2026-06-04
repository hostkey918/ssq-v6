from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.fetcher import sync_draws
from app.logic import generate_candidates
from app.models import Draw
from app.scheduler import create_scheduler
from app.schemas import CandidateOut, DrawOut, GenerateRequest, StatsOut, SyncResult

settings = get_settings()
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    Base.metadata.create_all(bind=engine)
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="6.0.0", lifespan=lifespan)
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
def health() -> dict[str, str]:
    return {"status": "ok", "version": "6.0.0"}


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
def sync(issue_count: int | None = Query(default=None, ge=1, le=10000), db: Session = Depends(get_db)) -> SyncResult:
    try:
        return sync_draws(db, issue_count=issue_count)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"抓取开奖数据失败: {exc}") from exc


@app.post("/api/generate", response_model=list[CandidateOut])
def generate(request: GenerateRequest, db: Session = Depends(get_db)) -> list[CandidateOut]:
    draws = db.query(Draw).order_by(desc(Draw.issue)).all()
    if not draws:
        raise HTTPException(status_code=400, detail="历史开奖为空，请先同步数据")
    return generate_candidates(
        draws=draws,
        filters=request.filters,
        top_n=request.top_n,
        candidate_pool=request.candidate_pool,
    )


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

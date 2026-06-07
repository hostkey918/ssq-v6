from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Draw(Base):
    __tablename__ = "draws"
    __table_args__ = (UniqueConstraint("issue", name="uq_draws_issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    draw_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    red1: Mapped[int] = mapped_column(Integer, nullable=False)
    red2: Mapped[int] = mapped_column(Integer, nullable=False)
    red3: Mapped[int] = mapped_column(Integer, nullable=False)
    red4: Mapped[int] = mapped_column(Integer, nullable=False)
    red5: Mapped[int] = mapped_column(Integer, nullable=False)
    red6: Mapped[int] = mapped_column(Integer, nullable=False)
    blue: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="cwl")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def reds(self) -> list[int]:
        return [self.red1, self.red2, self.red3, self.red4, self.red5, self.red6]


class ExpertSignal(Base):
    __tablename__ = "expert_signals"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_expert_signals_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issue: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    red_dan: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    red_kill: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    blue_dan: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    blue_kill: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    kill_tails: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

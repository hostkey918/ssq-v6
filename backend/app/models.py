from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint, func
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

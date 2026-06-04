from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.fetcher import sync_draws


def _scheduled_sync() -> None:
    db = SessionLocal()
    try:
        sync_draws(db)
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    minute, hour, day, month, day_of_week = settings.scheduler_cron.split()
    scheduler.add_job(
        _scheduled_sync,
        CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone="Asia/Shanghai",
        ),
        id="sync_ssq_draws",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler

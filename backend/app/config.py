from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SSQ V6.0"
    database_url: str = Field(
        default="postgresql+psycopg2://ssq:ssq@localhost:5432/ssq",
        alias="DATABASE_URL",
    )
    fetch_issue_count: int = Field(default=3000, alias="FETCH_ISSUE_COUNT")
    seed_draws_on_startup: bool = Field(default=True, alias="SEED_DRAWS_ON_STARTUP")
    auto_sync_on_startup: bool = Field(default=False, alias="AUTO_SYNC_ON_STARTUP")
    auto_sync_source: str = Field(default="zhcw", alias="AUTO_SYNC_SOURCE")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_cron: str = Field(default="0 22 * * tue,thu,sun", alias="SCHEDULER_CRON")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./internradar.db"
    admin_api_key: str = ""
    cors_origins: list[str] = ["*"]

    # JWT / auth
    secret_key: str = os.urandom(32).hex()  # override with a stable key in production
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    refresh_token_expire_days: int = 30

    # Email OTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@internradar.in"
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60

    # File uploads
    upload_dir: str = "./uploads"
    max_resume_size_mb: int = 5

    # listing maintenance
    closing_soon_days: int = 7
    link_check_batch: int = 50
    link_recheck_hours: int = 72

    # scheduler
    enable_scheduler: bool = True
    import_interval_hours: int = 12
    status_refresh_minutes: int = 60
    link_check_interval_hours: int = 6

    # sources
    source_remotive: bool = True
    feed_sources: list[dict] = []
    sources_file: str = "sources.json"
    india_only: bool = True
    http_timeout: float = 15.0
    http_retries: int = 3
    host_concurrency: int = 3
    discovery_workers: int = 8
    user_agent: str = "InternRadar/2.0 (+internship-discovery; contact: admin@internradar.in)"
    crawl_delay_seconds: float = 2.0
    crawl_max_pages: int = 60
    greenhouse_detail_cap: int = 150
    import_on_start: bool = True
    live_ttl_hours: int = 48
    detect_closed_pages: bool = True

    # Adzuna
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "in"

    # recommendation weights
    w_skill: float = 0.50
    w_interest: float = 0.20
    w_location: float = 0.15
    w_work_type: float = 0.10
    w_resume: float = 0.05   # resume text similarity bonus
    recommend_candidate_cap: int = 5000

    # semantic matching
    enable_semantic: bool = False
    semantic_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    w_semantic: float = 0.15

    # rate limiting
    rate_limit_otp_per_hour: int = 5
    rate_limit_login_per_minute: int = 10

    @property
    def weights(self) -> dict[str, float]:
        raw = {
            "skills": self.w_skill,
            "interest": self.w_interest,
            "location": self.w_location,
            "work_type": self.w_work_type,
        }
        if self.enable_semantic:
            raw["semantic"] = self.w_semantic
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Firefly Scheduler — Configuration via environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration loaded from environment variables (or .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "Firefly Scheduler"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://firefly:changeme@localhost:5432/firefly_scheduler"

    # ── Redis ───────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── MinIO / S3 ──────────────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "firefly_admin"
    MINIO_SECRET_KEY: str = "changeme_minio_password"
    MINIO_BUCKET_PACKAGES: str = "task-packages"
    MINIO_BUCKET_RESULTS: str = "results"
    MINIO_SECURE: bool = False          # True for production (HTTPS)

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_256_BIT_KEY"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_SECONDS: int = 86400      # 24 hours
    JWT_REFRESH_EXPIRE_SECONDS: int = 604800  # 7 days

    # ── Scheduler policy ─────────────────────────────────────────────────────
    TASK_CLAIM_TTL_SECONDS: int = 600   # 10 min — claimed→pending if no heartbeat
    TASK_RUN_TTL_SECONDS: int = 7200     # 2 hours — running timeout
    HEARTBEAT_INTERVAL_SECONDS: int = 60
    TASK_MAX_RETRIES: int = 3

    # ── Rate limits ─────────────────────────────────────────────────────────
    RATE_LIMIT_CLAIM: int = 6           # per minute per node
    RATE_LIMIT_HEARTBEAT: int = 2      # per minute per node
    RATE_LIMIT_REGISTER: int = 3        # per hour per IP


@lru_cache
def get_settings() -> Settings:
    return Settings()

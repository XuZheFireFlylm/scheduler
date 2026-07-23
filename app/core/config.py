"""调度中心配置"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "Firefly Scheduler"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://firefly:firefly_secret@postgres:5432/firefly"
    SYNC_DATABASE_URL: str = "postgresql://firefly:firefly_secret@postgres:5432/firefly"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MinIO / S3
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "firefly_access"
    S3_SECRET_KEY: str = "firefly_secret"
    S3_BUCKET: str = "firefly-models"
    S3_REGION: str = "us-east-1"

    # 安全
    SECRET_KEY: str = "change-me-in-production-use-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # 任务参数
    TASK_TIMEOUT_SECONDS: int = 3600 * 12  # 单任务最大12小时
    HEARTBEAT_INTERVAL_SECONDS: int = 60   # 节点心跳间隔
    NODE_OFFLINE_THRESHOLD_SECONDS: int = 180  # 超过3分钟无心跳视为离线

    # 权重聚合
    AGGREGATION_MIN_TASKS: int = 10        # 触发聚合的最少任务数
    AGGREGATION_WEIGHT_THRESHOLD: float = 0.01  # 低于1%权重忽略

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Firefly Scheduler — FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models.database import init_db
from app.services.redis_lock import close_redis
from app.api.auth import router as auth_router
from app.api.nodes import router as nodes_router
from app.api.tasks import router as tasks_router
from app.api.submissions import router as submissions_router
from app.api.users import router as users_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB tables. Shutdown: close Redis pool."""
    await init_db()
    yield
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="萤火虫大模型 · 分布式志愿算力调度中心",
    lifespan=lifespan,
)

# CORS（开发环境允许所有来源，生产环境请限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ─────────────────────────────────────────────────────────
app.include_router(auth_router,   prefix="/api/v1")
app.include_router(nodes_router,  prefix="/api/v1")
app.include_router(tasks_router,  prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")
app.include_router(users_router,   prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

"""API routers — re-exported here for convenience."""
from app.api.auth import router as auth_router
from app.api.nodes import router as nodes_router
from app.api.tasks import router as tasks_router
from app.api.submissions import router as submissions_router

__all__ = ["auth_router", "nodes_router", "tasks_router", "submissions_router"]

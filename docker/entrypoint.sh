#!/bin/bash
set -e

echo "Firefly Scheduler starting..."
echo "DB: $DATABASE_URL"

# Run Alembic migrations (if any exist)
if [ -f "/app/alembic/versions/001_initial.sql" ]; then
    echo "Running database migrations..."
    python -c "
import asyncio
from app.models.database import engine
from app.models import Base
from app.core.config import get_settings

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created.')

asyncio.run(migrate())
" || true
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1

"""pytest fixtures for Firefly Scheduler tests."""
import asyncio
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.database import Base, get_db
from app.models import User, Node, Task
from app.services.auth_service import hash_password

# Use SQLite for tests (no Postgres needed)
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    """One event loop for the whole test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Test fixtures ──────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPass123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_node(db_session: AsyncSession, test_user: User) -> Node:
    node = Node(
        id=uuid.uuid4(),
        user_id=test_user.id,
        node_name="test-node",
        hardware_info={"cpu": {"model": "AMD Ryzen 9", "cores": 16}},
        status="online",
        reputation_score=100,
        max_task_level=3,
    )
    db_session.add(node)
    await db_session.commit()
    await db_session.refresh(node)
    return node


@pytest_asyncio.fixture
async def test_task(db_session: AsyncSession) -> Task:
    task = Task(
        id=uuid.uuid4(),
        level=1,
        title="测试任务",
        description="测试描述",
        status="pending",
        base_contribution=50,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, test_user: User) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "TestPass123!",
    })
    return resp.json()["access_token"]


@pytest_asyncio.fixture
def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}

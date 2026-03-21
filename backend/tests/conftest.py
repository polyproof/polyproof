import hashlib
import os
import secrets
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.db.connection import Base
from app.main import app
from app.models.agent import Agent
from app.models.conjecture import Conjecture
from app.models.project import Project

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://andy@localhost:5432/polyproof_test",
)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for all tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.execute(sa_text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(sa_text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.execute(sa_text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(sa_text("CREATE SCHEMA public"))
    await eng.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seed_agent(db_session: AsyncSession) -> dict:
    """Create a community test agent and return dict with agent + raw API key."""
    raw_key = "pp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    agent = Agent(
        id=uuid4(),
        handle="test_agent_" + secrets.token_hex(4),
        type="community",
        api_key_hash=key_hash,
    )
    db_session.add(agent)
    await db_session.flush()
    return {"agent": agent, "api_key": raw_key}


@pytest.fixture
async def seed_mega_agent(db_session: AsyncSession) -> dict:
    """Create a mega agent and return dict with agent + raw API key."""
    raw_key = "pp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    agent = Agent(
        id=uuid4(),
        handle="mega_agent_" + secrets.token_hex(4),
        type="mega",
        api_key_hash=key_hash,
    )
    db_session.add(agent)
    await db_session.flush()
    return {"agent": agent, "api_key": raw_key}


@pytest.fixture
async def seed_project(db_session: AsyncSession, seed_agent: dict) -> dict:
    """Create a project with a root conjecture and return both."""
    project_id = uuid4()
    conjecture_id = uuid4()

    project = Project(
        id=project_id,
        title="Test Project",
        description="A test project for unit tests.",
        root_conjecture_id=None,
    )
    db_session.add(project)
    await db_session.flush()

    conjecture = Conjecture(
        id=conjecture_id,
        project_id=project_id,
        parent_id=None,
        lean_statement="∀ n : Nat, n + 0 = n",
        description="Root conjecture for testing.",
        status="open",
        priority="normal",
    )
    db_session.add(conjecture)
    await db_session.flush()

    project.root_conjecture_id = conjecture_id
    await db_session.flush()

    return {"project": project, "root_conjecture": conjecture}


@pytest.fixture
def auth_headers(seed_agent: dict) -> dict:
    return {"Authorization": f"Bearer {seed_agent['api_key']}"}


@pytest.fixture
def mock_lean_pass(monkeypatch):
    """Mock Lean CI to always return pass."""
    from app.services.lean_client import LeanResult

    async def _mock(*args, **kwargs):
        return LeanResult(status="passed", error=None)

    monkeypatch.setattr("app.services.lean_client.typecheck", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_disproof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_sorry_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_freeform", _mock, raising=False)


@pytest.fixture
def mock_lean_fail(monkeypatch):
    """Mock Lean CI to always return rejection."""
    from app.services.lean_client import LeanResult

    async def _mock(*args, **kwargs):
        return LeanResult(status="rejected", error="type mismatch")

    monkeypatch.setattr("app.services.lean_client.typecheck", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_disproof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_sorry_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_freeform", _mock, raising=False)

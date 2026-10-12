from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bagmitra_api.core.settings import Settings
from bagmitra_api.db.base import Base
from bagmitra_api.db.session import get_sessionmaker
from bagmitra_api.main import create_app

JWT_SECRET = "test-secret-that-is-long-enough-for-hs256-signing"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+aiosqlite://",
        supabase_jwt_secret=JWT_SECRET,
        log_level="WARNING",
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(settings: Settings, engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    app.dependency_overrides[get_sessionmaker] = lambda: maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_token(
    sub: uuid.UUID | str,
    *,
    secret: str = JWT_SECRET,
    aud: str = "authenticated",
    exp_offset: int = 3600,
    **extra: Any,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {"sub": str(sub), "aud": aud, "iat": now, "exp": now + exp_offset}
    claims.update(extra)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, phone='919800000000')}"}

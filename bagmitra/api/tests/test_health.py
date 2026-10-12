from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bagmitra_api.core.settings import Settings
from bagmitra_api.db.session import get_sessionmaker
from bagmitra_api.main import create_app


async def test_live_returns_ok_and_product_name(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "product": "BagMitra"}


async def test_ready_checks_database(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"


async def test_ready_returns_503_when_database_unreachable(settings: Settings) -> None:
    app = create_app(settings)
    broken = create_async_engine("sqlite+aiosqlite:////nonexistent-dir/x/db.sqlite")
    app.dependency_overrides[get_sessionmaker] = lambda: async_sessionmaker(broken)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["database"] == "unavailable"
    await broken.dispose()

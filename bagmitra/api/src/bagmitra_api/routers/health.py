from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bagmitra_api.core.settings import Settings, get_settings
from bagmitra_api.db.session import get_sessionmaker

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str
    product: str


class ReadyResponse(BaseModel):
    status: str
    database: str


@router.get("/live", operation_id="health_live")
async def live(settings: Annotated[Settings, Depends(get_settings)]) -> LiveResponse:
    return LiveResponse(status="ok", product=settings.product_name)


@router.get(
    "/ready",
    operation_id="health_ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(
    maker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> JSONResponse:
    try:
        async with maker() as session:
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        body = ReadyResponse(status="degraded", database="unavailable")
        return JSONResponse(status_code=503, content=body.model_dump())
    return JSONResponse(content=ReadyResponse(status="ok", database="ok").model_dump())

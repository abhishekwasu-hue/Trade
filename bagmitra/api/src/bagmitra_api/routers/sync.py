from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from bagmitra_api.auth.jwt import CurrentUser
from bagmitra_api.core.errors import ApiError, ErrorResponse
from bagmitra_api.core.settings import Settings, get_settings
from bagmitra_api.db.session import DbSession
from bagmitra_api.sync import service
from bagmitra_api.sync.schemas import PullResponse, PushRequest, PushResponse

router = APIRouter(
    prefix="/v1/sync",
    tags=["sync"],
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)


@router.post("/push", operation_id="sync_push")
async def push(
    body: PushRequest,
    user: CurrentUser,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PushResponse:
    """Apply a batch of offline mutations. Each mutation gets its own result; the batch
    never fails as a whole because of one bad mutation."""
    if len(body.mutations) > settings.sync_max_batch:
        raise ApiError(422, "validation_error", f"at most {settings.sync_max_batch} mutations")
    return PushResponse(results=await service.push(session, user, body.mutations))


@router.get("/pull", operation_id="sync_pull")
async def pull(
    user: CurrentUser, session: DbSession, since: Annotated[int, Query(ge=0)] = 0
) -> PullResponse:
    return await service.pull(session, user, since)

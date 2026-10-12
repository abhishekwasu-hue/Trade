from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from bagmitra_api.auth.jwt import CurrentUser
from bagmitra_api.core.errors import ApiError, ErrorResponse
from bagmitra_api.db.models import Farmer
from bagmitra_api.db.session import DbSession

router = APIRouter(prefix="/v1", tags=["profile"])


class FarmerProfile(BaseModel):
    id: uuid.UUID
    phone: str | None
    display_name: str | None
    language: str
    village: str | None
    taluka: str | None
    district: str | None
    consent_data_processing: bool
    consent_whatsapp: bool


@router.get(
    "/me",
    operation_id="me_get",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_me(user: CurrentUser, session: DbSession) -> FarmerProfile:
    farmer = await session.get(Farmer, user.id)
    if farmer is None:
        raise ApiError(404, "profile_not_found", "complete onboarding first")
    return FarmerProfile.model_validate(farmer, from_attributes=True)

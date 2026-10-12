"""Entities that clients may write through the outbox.

Each handler declares its payload schema and how to apply / serialise a row. Adding a
synced entity in later milestones means registering a handler here — the push/pull
mechanics stay unchanged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bagmitra_api.auth.jwt import AuthenticatedUser
from bagmitra_api.db.models import Farmer


class RejectedError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedWrite:
    entity_id: str
    payload: BaseModel
    client_updated_at: datetime
    seq: int


class EntityHandler(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def supported_ops(self) -> frozenset[str]: ...
    @property
    def payload_model(self) -> type[BaseModel]: ...

    async def current_version(
        self, session: AsyncSession, user: AuthenticatedUser, entity_id: str
    ) -> datetime | None: ...

    async def apply(
        self, session: AsyncSession, user: AuthenticatedUser, write: ValidatedWrite
    ) -> None: ...

    async def changed_since(
        self, session: AsyncSession, user: AuthenticatedUser, since: int
    ) -> list[tuple[str, dict[str, Any], datetime, int]]: ...


class FarmerProfilePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    language: str = Field(min_length=2, max_length=12, pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    village: str | None = Field(default=None, max_length=120)
    taluka: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    consent_data_processing: bool = False
    consent_whatsapp: bool = False


@dataclass(frozen=True)
class FarmerProfileHandler:
    name: str = "farmer_profile"
    supported_ops: frozenset[str] = frozenset({"upsert"})
    payload_model: type[BaseModel] = FarmerProfilePayload

    @staticmethod
    def _own_id(user: AuthenticatedUser, entity_id: str) -> uuid.UUID:
        if entity_id != str(user.id):
            raise RejectedError("forbidden")
        return user.id

    async def current_version(
        self, session: AsyncSession, user: AuthenticatedUser, entity_id: str
    ) -> datetime | None:
        farmer = await session.get(Farmer, self._own_id(user, entity_id))
        return farmer.client_updated_at if farmer else None

    async def apply(
        self, session: AsyncSession, user: AuthenticatedUser, write: ValidatedWrite
    ) -> None:
        farmer_id = self._own_id(user, write.entity_id)
        farmer = await session.get(Farmer, farmer_id)
        if farmer is None:
            farmer = Farmer(id=farmer_id)
            session.add(farmer)
        for key, value in write.payload.model_dump().items():
            setattr(farmer, key, value)
        if user.phone:
            farmer.phone = user.phone
        farmer.client_updated_at = write.client_updated_at
        farmer.last_seq = write.seq

    async def changed_since(
        self, session: AsyncSession, user: AuthenticatedUser, since: int
    ) -> list[tuple[str, dict[str, Any], datetime, int]]:
        rows = await session.scalars(
            select(Farmer).where(Farmer.id == user.id, Farmer.last_seq > since)
        )
        return [(str(f.id), profile_dict(f), f.updated_at, f.last_seq) for f in rows]


def profile_dict(farmer: Farmer) -> dict[str, Any]:
    data = {key: getattr(farmer, key) for key in FarmerProfilePayload.model_fields}
    data["phone"] = farmer.phone
    return data


HANDLERS: dict[str, EntityHandler] = {h.name: h for h in (FarmerProfileHandler(),)}

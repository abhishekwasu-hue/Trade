from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field

MutationStatus = Literal["applied", "duplicate", "stale", "rejected"]


class Mutation(BaseModel):
    client_mutation_id: uuid.UUID
    entity: str = Field(max_length=64)
    entity_id: str = Field(max_length=64)
    op: Literal["upsert", "delete"]
    client_updated_at: AwareDatetime
    payload: dict[str, Any]


class PushRequest(BaseModel):
    # The upper bound is enforced in the router from settings.sync_max_batch.
    mutations: list[Mutation] = Field(min_length=1)


class MutationResult(BaseModel):
    client_mutation_id: uuid.UUID
    status: MutationStatus
    error: str | None = None


class PushResponse(BaseModel):
    results: list[MutationResult]


class Change(BaseModel):
    entity: str
    entity_id: str
    op: Literal["upsert", "delete"]
    data: dict[str, Any]
    updated_at: datetime
    seq: int


class PullResponse(BaseModel):
    changes: list[Change]
    cursor: int

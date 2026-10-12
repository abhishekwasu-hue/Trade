from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bagmitra_api.db.base import Base, SyncedRowMixin


class Farmer(SyncedRowMixin, Base):
    """A grower. `id` equals the Supabase auth user id (owner of every row they create)."""

    __tablename__ = "farmers"
    owner_column = "id"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    display_name: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(12))
    village: Mapped[str | None] = mapped_column(String(120))
    taluka: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    consent_data_processing: Mapped[bool] = mapped_column(default=False)
    consent_whatsapp: Mapped[bool] = mapped_column(default=False)

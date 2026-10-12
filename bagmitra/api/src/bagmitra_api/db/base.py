from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SyncedRowMixin(TimestampMixin):
    """Columns every user-owned, offline-synced table carries.

    `client_updated_at` drives last-writer-wins; `last_seq` is the sync_mutations sequence
    that last changed the row and is the pull cursor.
    """

    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seq: Mapped[int] = mapped_column(BigInteger, index=True)

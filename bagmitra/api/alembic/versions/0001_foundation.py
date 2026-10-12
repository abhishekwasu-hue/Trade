"""Foundation: farmers and the sync mutation audit log, with owner-only RLS.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from bagmitra_api.db.rls import AUTH_UID_SHIM, disable_owner_rls, enable_owner_rls

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

RLS_TABLES = {"farmers": "id", "sync_mutations": "owner_id"}


def _ts(name: str, *, nullable: bool = False) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "farmers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("village", sa.String(120), nullable=True),
        sa.Column("taluka", sa.String(120), nullable=True),
        sa.Column("district", sa.String(120), nullable=True),
        sa.Column("consent_data_processing", sa.Boolean(), nullable=False),
        sa.Column("consent_whatsapp", sa.Boolean(), nullable=False),
        _ts("client_updated_at"),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farmers")),
    )
    op.create_index(op.f("ix_farmers_last_seq"), "farmers", ["last_seq"])
    op.create_table(
        "sync_mutations",
        sa.Column(
            "seq",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("client_mutation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("op", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        _ts("client_updated_at"),
        _ts("received_at"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_sync_mutations")),
        sa.UniqueConstraint(
            "owner_id", "client_mutation_id", name=op.f("uq_sync_mutations_owner_id")
        ),
    )
    op.create_index(op.f("ix_sync_mutations_owner_id"), "sync_mutations", ["owner_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(AUTH_UID_SHIM)
        for table, owner in RLS_TABLES.items():
            for stmt in enable_owner_rls(table, owner):
                op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in RLS_TABLES:
            for stmt in disable_owner_rls(table):
                op.execute(stmt)
    op.drop_index(op.f("ix_sync_mutations_owner_id"), table_name="sync_mutations")
    op.drop_table("sync_mutations")
    op.drop_index(op.f("ix_farmers_last_seq"), table_name="farmers")
    op.drop_table("farmers")

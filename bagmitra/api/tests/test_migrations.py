"""Migrations must match the models, be reversible, and enable RLS on every table."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy import exc as sa_exc

from bagmitra_api.db import models  # noqa: F401
from bagmitra_api.db.base import Base
from bagmitra_api.db.rls import disable_owner_rls, enable_owner_rls

API_DIR = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _sync_url(async_url: str) -> str:
    return async_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def _ours(name: str | None, type_: str, _parent: object) -> bool:
    # PostGIS images ship extra tables (tiger geocoder); only compare tables we own.
    return type_ != "table" or name in Base.metadata.tables


def _diff(conn: Connection) -> list[object]:
    ctx = MigrationContext.configure(conn, opts={"include_name": _ours})
    return list(compare_metadata(ctx, Base.metadata))


def test_upgrade_downgrade_upgrade_on_sqlite(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'm.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(_sync_url(url))
    with engine.connect() as conn:
        assert set(inspect(conn).get_table_names()) >= set(Base.metadata.tables)
        assert _diff(conn) == [], "models and migrations drifted; write a migration"
    engine.dispose()


def test_every_model_declares_its_owner_column() -> None:
    for mapper in Base.registry.mappers:
        owner = getattr(mapper.class_, "owner_column", None)
        assert isinstance(owner, str), f"{mapper.class_.__name__} lacks owner_column"
        assert owner in mapper.columns, f"{mapper.class_.__name__} needs owner_column for RLS"


def test_rls_statements_reject_unsafe_identifiers() -> None:
    assert enable_owner_rls("farmers", "id")[0] == "ALTER TABLE farmers ENABLE ROW LEVEL SECURITY"
    assert disable_owner_rls("farmers")[0].startswith("DROP POLICY")
    with pytest.raises(ValueError, match="unsafe"):
        enable_owner_rls("farmers; drop table x", "id")


@pytest.mark.postgres
@pytest.mark.skipif("POSTGRES_TEST_URL" not in os.environ, reason="needs POSTGRES_TEST_URL")
def test_postgres_migrations_and_rls() -> None:
    url = os.environ["POSTGRES_TEST_URL"]
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(url.replace("+asyncpg", "+psycopg"))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                # Extension-owned tables (e.g. PostGIS spatial_ref_sys) are not ours.
                "AND c.relname <> 'alembic_version' AND NOT EXISTS ("
                "  SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')"
            )
        ).all()
        assert {r for r, _ in rows} == set(Base.metadata.tables)
        assert all(rls for _, rls in rows), f"RLS missing: {[r for r, s in rows if not s]}"
        assert _diff(conn) == []
        _assert_owner_isolation(conn)
    engine.dispose()


def _assert_owner_isolation(conn: Connection) -> None:
    me, other = str(uuid.uuid4()), str(uuid.uuid4())
    insert = text(
        "INSERT INTO farmers (id, language, consent_data_processing, consent_whatsapp, "
        "client_updated_at, last_seq, created_at, updated_at) "
        "VALUES (:id, 'mr', false, false, now(), 1, now(), now())"
    )
    conn.commit()
    with conn.begin():
        conn.execute(text("DROP ROLE IF EXISTS rls_probe"))
        conn.execute(text("CREATE ROLE rls_probe NOLOGIN"))
        conn.execute(text("GRANT SELECT, INSERT ON farmers TO rls_probe"))
        conn.execute(text("GRANT USAGE ON SCHEMA auth TO rls_probe"))
    with conn.begin() as tx:
        conn.execute(text("SET LOCAL ROLE rls_probe"))
        conn.execute(text("SELECT set_config('request.jwt.claim.sub', :s, true)"), {"s": me})
        conn.execute(insert, {"id": me})
        with (
            pytest.raises(sa_exc.ProgrammingError, match="row-level security"),
            conn.begin_nested(),
        ):
            conn.execute(insert, {"id": other})
        visible = conn.execute(text("SELECT id::text FROM farmers")).scalars().all()
        assert visible == [me]
        tx.rollback()

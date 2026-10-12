"""Row-level security helpers used by migrations (Postgres / Supabase only).

The API connects with a privileged role and enforces ownership in code; RLS is the
second wall that protects rows from direct Supabase client access.
"""

from __future__ import annotations

import re

_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# Plain Postgres (CI, local docker) has no Supabase `auth` schema. Create a compatible
# auth.uid() only when it is missing, so a real Supabase function is never replaced.
AUTH_UID_SHIM = """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'auth' AND p.proname = 'uid'
  ) THEN
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
      $f$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $f$;
  END IF;
END $$;
"""


def _check(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def enable_owner_rls(table: str, owner_column: str) -> list[str]:
    """Statements that enable RLS and allow a user to touch only their own rows."""
    t, c = _check(table), _check(owner_column)
    return [
        f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {t}_owner_all ON {t} FOR ALL "
        f"USING ({c} = auth.uid()) WITH CHECK ({c} = auth.uid())",
    ]


def disable_owner_rls(table: str) -> list[str]:
    t = _check(table)
    return [
        f"DROP POLICY IF EXISTS {t}_owner_all ON {t}",
        f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY",
    ]

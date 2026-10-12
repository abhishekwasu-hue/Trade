from __future__ import annotations

import json
from pathlib import Path

from bagmitra_api.core.settings import Settings
from bagmitra_api.export_openapi import render_openapi

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def test_committed_openapi_matches_code(settings: Settings) -> None:
    """Contract-first: docs/api/openapi.json must be regenerated with every API change."""
    assert SPEC_PATH.exists(), "run: python -m bagmitra_api.export_openapi"
    assert json.loads(SPEC_PATH.read_text()) == json.loads(render_openapi(settings))


def test_operation_ids_are_stable_and_readable(settings: Settings) -> None:
    spec = json.loads(render_openapi(settings))
    ids = {op["operationId"] for path in spec["paths"].values() for op in path.values()}
    assert {"health_live", "health_ready", "me_get", "sync_push", "sync_pull"} <= ids

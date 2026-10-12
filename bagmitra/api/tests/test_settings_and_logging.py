from __future__ import annotations

import json
import logging

import pytest
import structlog

from bagmitra_api.core.logging import configure_logging
from bagmitra_api.core.settings import Settings, get_settings


def test_product_name_comes_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_NAME", "Renamed")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    try:
        assert get_settings().product_name == "Renamed"
    finally:
        get_settings.cache_clear()


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        Settings(supabase_jwt_secret="short")


def test_logs_are_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger("t").info("hello", plot="p1")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["event"] == "hello"
    assert data["plot"] == "p1"
    assert data["level"] == "info"
    assert logging.getLogger().level == logging.INFO

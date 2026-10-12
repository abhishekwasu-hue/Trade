"""Error-reporting hook. Enabled only when SENTRY_DSN is set and sentry-sdk is installed."""

from __future__ import annotations

import importlib

import structlog

from bagmitra_api.core.settings import Settings

log = structlog.get_logger("bagmitra.observability")


def init_error_reporting(settings: Settings) -> bool:
    if settings.sentry_dsn is None:
        return False
    try:
        sentry = importlib.import_module("sentry_sdk")
    except ImportError:
        log.warning("sentry_dsn_set_but_sdk_missing")
        return False
    sentry.init(dsn=settings.sentry_dsn.get_secret_value(), environment=settings.environment)
    return True

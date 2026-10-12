from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bagmitra_api.core.errors import install_error_handlers
from bagmitra_api.core.logging import configure_logging
from bagmitra_api.core.middleware import RequestIdMiddleware
from bagmitra_api.core.observability import init_error_reporting
from bagmitra_api.core.settings import Settings, get_settings
from bagmitra_api.routers import health, me, sync


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    init_error_reporting(settings)

    app = FastAPI(title=f"{settings.product_name} API", version="0.1.0")
    app.dependency_overrides[get_settings] = lambda: settings
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    for module in (health, me, sync):
        app.include_router(module.router)
    return app

"""Runtime configuration. Every value comes from the environment (or `.env`)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../product.env"), extra="ignore")

    product_name: str = "BagMitra"
    product_slug: str = "bagmitra"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./bagmitra-local.db"

    supabase_jwt_secret: SecretStr = Field(default=SecretStr(""))
    jwt_audience: str = "authenticated"

    cors_origins: list[str] = Field(default_factory=list)
    sentry_dsn: SecretStr | None = None

    sync_max_batch: int = 200

    @field_validator("supabase_jwt_secret")
    @classmethod
    def _secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("SUPABASE_JWT_SECRET must be at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

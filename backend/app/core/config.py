from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", env_file_encoding="utf-8"
    )

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8001"
    database_url: str = "postgresql+psycopg://localhost:5434/radory"
    redis_url: str = "redis://localhost:6380/0"

    tavily_api_key: str = ""
    tavily_search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "basic"
    tavily_max_results: int = Field(default=10, ge=1, le=20)
    tavily_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    radar_query_max_attempts: int = Field(default=3, ge=1, le=10)
    radar_query_lease_seconds: int = Field(default=120, ge=30, le=3600)
    radar_reconcile_interval_seconds: int = Field(default=60, ge=10, le=3600)
    radar_dispatch_stale_seconds: int = Field(default=60, ge=10, le=3600)
    radar_retry_base_seconds: int = Field(default=30, ge=1, le=3600)
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nemotron_nano_model: str = ""
    nemotron_super_model: str = ""
    nemotron_ultra_model: str = ""
    nemotron_model: str = ""
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_audience: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint: str = ""
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    sentry_dsn: str = ""

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpsPilot"
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    api_key: str = "change-me-to-a-strong-secret"
    secret_key: str = "change-me-jwt-or-session-secret"

    database_url: str = (
        "postgresql+asyncpg://opspilot:opspilot@localhost:5432/opspilot"
    )
    database_url_sync: str = (
        "postgresql://opspilot:opspilot@localhost:5432/opspilot"
    )
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    agent_mode: Literal["auto", "openai", "mock"] = "auto"
    max_tool_calls: int = 12
    evidence_score_threshold: float = 0.55

    telemetry_mode: Literal["synthetic", "prometheus"] = "synthetic"
    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"

    otel_enabled: bool = True
    otel_service_name: str = "ops-pilot-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_openai(self) -> bool:
        if self.agent_mode == "mock":
            return False
        if self.agent_mode == "openai":
            return bool(self.openai_api_key)
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

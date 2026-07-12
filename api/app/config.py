from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Wonder Codex API"
    app_version: str = "1.4.2"
    environment: str = "production"
    database_url: str = ""
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "https://wondercodex.com",
            "https://www.wondercodex.com",
        ]
    )
    admin_api_key: str = ""
    ip_hash_salt: str = "change-me"
    max_requests_per_hour: int = 5
    max_request_bytes: int = 30_000_000
    max_discoveries_per_submission: int = 20_000
    max_matches_per_submission: int = 2_000
    max_issues_per_submission: int = 5_000
    run_migrations_on_start: bool = True
    database_connect_timeout_seconds: int = 10

    spaces_access_key: str = ""
    spaces_secret_key: str = ""
    spaces_region: str = ""
    spaces_bucket: str = ""
    spaces_endpoint: str = ""
    spaces_cdn_url: str = ""
    max_image_mb: int = 15
    min_image_width: int = 640
    min_image_height: int = 360
    max_image_dimension: int = 7680

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024

    @property
    def spaces_ready(self) -> bool:
        return all([
            self.spaces_access_key,
            self.spaces_secret_key,
            self.spaces_region,
            self.spaces_bucket,
            self.spaces_endpoint,
            self.spaces_cdn_url,
        ])

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        value = self.database_url.strip()
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

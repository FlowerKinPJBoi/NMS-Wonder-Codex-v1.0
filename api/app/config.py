from __future__ import annotations

import json
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
    app_version: str = "1.14.1"
    environment: str = "production"
    database_url: str = ""
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "https://wondercodex.com",
            "https://www.wondercodex.com",
        ]
    )
    admin_api_key: str = ""
    admin_api_key_pj: str = ""
    admin_api_key_boots: str = ""
    admin_api_keys: dict[str, str] = Field(default_factory=dict)
    tester_api_key_menomoo: str = ""
    tester_api_key_floppydonkey: str = ""
    tester_api_key_darkbellator: str = ""
    tester_api_key_olgravyleg: str = ""
    tester_api_key_monketsu: str = ""
    tester_api_key_readyfireaim: str = ""
    tester_api_key_visceral: str = ""
    ip_hash_salt: str = "change-me"
    max_requests_per_hour: int = 5
    analytics_enabled: bool = True
    analytics_owner_actor: str = "PJ"
    analytics_retention_days: int = 90
    analytics_max_events_per_minute: int = 120
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
    max_admin_app_mb: int = 160
    admin_app_download_seconds: int = 600

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024

    @property
    def max_admin_app_bytes(self) -> int:
        return self.max_admin_app_mb * 1024 * 1024

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

    @property
    def spaces_private_ready(self) -> bool:
        return all([
            self.spaces_access_key,
            self.spaces_secret_key,
            self.spaces_region,
            self.spaces_bucket,
            self.spaces_endpoint,
        ])

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("admin_api_keys", mode="before")
    @classmethod
    def parse_named_api_keys(cls, value):
        if value in (None, ""):
            return {}
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("Named API keys must be a JSON object mapping operator names to keys.")
            if not all(isinstance(name, str) and isinstance(key, str) for name, key in parsed.items()):
                raise ValueError("Named API keys must map text operator names to text keys.")
            return parsed
        return value

    @property
    def tester_api_keys(self) -> dict[str, str]:
        """Restricted operator keys kept as scalar environment variables.

        DigitalOcean App Platform treats JSON braces as interpolation syntax in
        its environment-variable editor. Individual values avoid that parser
        entirely while preserving the named-key interface used by security.py.
        """
        return {
            "Menomoo": self.tester_api_key_menomoo,
            "FloppyDonkey": self.tester_api_key_floppydonkey,
            "DarkBellator": self.tester_api_key_darkbellator,
            "OlGravyLeg": self.tester_api_key_olgravyleg,
            "Monketsu": self.tester_api_key_monketsu,
            "ReadyFireAim": self.tester_api_key_readyfireaim,
            "Visceral": self.tester_api_key_visceral,
        }

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

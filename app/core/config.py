from functools import lru_cache

from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    app_name: str = "ReLoop Hub API"
    app_env: str = "development"
    debug: bool = False
    database_url: str
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_connect_timeout_seconds: int = 5
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    device_api_key: str = "development-device-key"
    reporting_timezone: str = "Asia/Ho_Chi_Minh"
    co2_emission_factor_kg_per_km: Decimal = Decimal("0.27")
    co2_methodology_version: str = "route-distance-v1"
    co2_factor_source: str = (
        "prototype assumption; validate before ESG use"
    )
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_origins.split(",")
            if item.strip()
        ]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env.casefold() == "production":
            if (
                self.jwt_secret == "development-only-change-me"
                or len(self.jwt_secret) < 32
            ):
                raise ValueError(
                    "production JWT_SECRET must contain at least "
                    "32 non-default characters"
                )
            if self.device_api_key == "development-device-key":
                raise ValueError(
                    "production DEVICE_API_KEY must not use the default"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

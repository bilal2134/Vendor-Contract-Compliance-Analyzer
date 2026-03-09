from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vendor Contract Compliance Analyzer"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    environment: str = "development"
    gemini_api_key: str | None = None
    chroma_path: str = "./.chroma"
    database_url: str = "sqlite:///./compliance.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

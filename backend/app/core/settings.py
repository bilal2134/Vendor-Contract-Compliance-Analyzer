from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vendor Contract Compliance Analyzer"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    environment: str = "development"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    # Set to "local" to use sentence-transformers (no API key, no rate limits)
    # Set to "gemini" (default) to use Gemini embedding API
    embedding_backend: str = "gemini"
    chroma_path: Path = Path("./storage/chroma")
    storage_root: Path = Path("./storage")
    database_url: str = "sqlite:///./compliance.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

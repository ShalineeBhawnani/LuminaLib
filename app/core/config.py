"""
Application configuration management.
All settings are loaded from environment variables via .env file.
Swap providers (LLM, Storage) by changing a single config value.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Project ──────────────────────────────────────────────────────────
    PROJECT_NAME: str = "LuminaLib"
    VERSION: str = "1.0.0"
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lumina:lumina@db:5432/luminalib"

    # ── JWT ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Storage ──────────────────────────────────────────────────────────
    # Switch between "local" or "s3" via env var — no code changes required
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: str = "/app/storage"

    # S3 / MinIO (used when STORAGE_BACKEND="s3")
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_BUCKET_NAME: str = "luminalib-books"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"

    # ── LLM ──────────────────────────────────────────────────────────────
    # Switch between "ollama" or "openai" via env var — no business logic changes
    LLM_BACKEND: Literal["ollama", "openai"] = "ollama"

    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3"

    # OpenAI (used when LLM_BACKEND="openai")
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Recommendation Engine ────────────────────────────────────────────
    RECOMMENDATION_ALGORITHM: Literal["content_based", "collaborative"] = "content_based"
    RECOMMENDATION_TOP_N: int = 10

    # ── Pagination ───────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

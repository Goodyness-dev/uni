"""Production configuration settings for ScholarPilot."""
import secrets
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = Field(default="development", description="Current runtime environment: development, staging, production")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # Database & Redis
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://scholarpilot:scholarpilot@localhost:5432/scholarpilot_db",
        description="Async SQLAlchemy database URL (PostgreSQL default, aiosqlite for tests)",
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL for queue and locks")

    # Security & Encryption
    # Generate a default URL-safe 32-byte key for local development if not set
    ENCRYPTION_KEY: str = Field(
        default="e3w8oG2Z5mY6pT9vQ1rU4xN7bK0jH3fD2sA5lP8oI1u=",
        description="Base64 32-byte Fernet key for encrypting portal credentials at rest",
    )
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Session and token signing key",
    )

    # Autonomy & Kill Switch
    KILL_SWITCH_ACTIVE: bool = Field(default=False, description="Global emergency stop for all submissions")

    # LLM Gateway & Providers
    PRIMARY_MODEL: str = Field(default="gemini-2.0-flash")
    PRIMARY_API_KEY: Optional[str] = Field(default=None)
    PRIMARY_BASE_URL: Optional[str] = Field(default=None)

    FALLBACK_MODEL: str = Field(default="gpt-4o-mini")
    FALLBACK_API_KEY: Optional[str] = Field(default=None)
    FALLBACK_BASE_URL: Optional[str] = Field(default=None)

    LLM_TIMEOUT_SECONDS: float = Field(default=30.0)
    LLM_MAX_RETRIES: int = Field(default=2)

    # Cost Tracking & Spending Caps
    USER_DAILY_SPEND_CAP_USD: float = Field(default=1.00, description="Spending limit per user per day in USD")
    GLOBAL_DAILY_SPEND_CAP_USD: float = Field(default=50.00, description="Global spending limit per day in USD")

    # External Integrations
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None)
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(default=None)
    NEATLOGS_API_KEY: Optional[str] = Field(default=None)
    NEATLOGS_ENDPOINT: Optional[str] = Field(default=None)

    # Storage (S3 Compatible)
    STORAGE_BUCKET_NAME: str = Field(default="scholarpilot-documents")
    STORAGE_ENDPOINT_URL: Optional[str] = Field(default=None)
    STORAGE_ACCESS_KEY: Optional[str] = Field(default=None)
    STORAGE_SECRET_KEY: Optional[str] = Field(default=None)


settings = Settings()

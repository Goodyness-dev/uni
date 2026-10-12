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

    # LLM Gateway & Providers (Gemini Primary, Claude Switching Support)
    LLM_PROVIDER: str = Field(default="gemini", description="Active LLM provider: 'gemini', 'claude', or 'openai'")
    
    # Gemini
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-flash-latest")
    GEMINI_BASE_URL: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai")

    # Claude (Anthropic)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    CLAUDE_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    CLAUDE_BASE_URL: str = Field(default="https://api.anthropic.com/v1")

    # Legacy & generic overrides
    PRIMARY_MODEL: str = Field(default="gemini-2.0-flash")
    PRIMARY_API_KEY: Optional[str] = Field(default=None)
    PRIMARY_BASE_URL: Optional[str] = Field(default=None)

    FALLBACK_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
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
    OIDC_ISSUER: Optional[str] = Field(default=None)
    OIDC_AUDIENCE: Optional[str] = Field(default=None)
    OIDC_JWKS_URL: Optional[str] = Field(default=None)
    OIDC_AUTHORIZATION_URL: Optional[str] = None
    OIDC_TOKEN_URL: Optional[str] = None
    OIDC_REDIRECT_URI: str = "http://localhost:3000/"
    LIVE_RESEARCH: bool = Field(default=False)
    LLM_DRAFTING: bool = Field(default=False)
    AGENT_MAX_DECISIONS: int = Field(default=10, ge=4, le=20)
    NOTIFICATIONS_ENABLED: bool = Field(default=False)
    EMAIL_PROVIDER: str = Field(default="smtp", pattern="^(smtp|ses)$")
    SES_REGION: str = Field(default="eu-north-1")
    SES_FROM: Optional[str] = None
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: Optional[str] = None
    SMTP_APP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    AGENT_ENABLED: bool = Field(default=False)
    AGENT_FALLBACK_MODEL: str = Field(default="gemini-3.1-flash-lite")
    NEATLOGS_CAPTURE_CONTENT: bool = Field(default=False, description="Explicit fictional-demo prompt capture")

    # Storage (S3 Compatible)
    STORAGE_BUCKET_NAME: str = Field(default="scholarpilot-documents")
    STORAGE_ENDPOINT_URL: Optional[str] = Field(default=None)
    STORAGE_ACCESS_KEY: Optional[str] = Field(default=None)
    STORAGE_SECRET_KEY: Optional[str] = Field(default=None)


settings = Settings()

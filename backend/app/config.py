import os
from pathlib import Path


def load_env_file(file_path: str | Path | None = None) -> None:
    """Load environment variables from a file if not already set in os.environ."""
    if file_path is None:
        candidates = [
            Path("backend/.env"),
            Path(".env"),
            Path(__file__).resolve().parent.parent / ".env",
            Path(__file__).resolve().parent.parent.parent / ".env",
        ]
        for candidate in candidates:
            if candidate.is_file():
                file_path = candidate
                break

    if file_path is None:
        return

    path_obj = Path(file_path)
    if not path_obj.is_file():
        return

    with open(path_obj, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, val = stripped.split("=", 1)
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and (
                (val.startswith('"') and val.endswith('"'))
                or (val.startswith("'") and val.endswith("'"))
            ):
                val = val[1:-1]
            if key and key not in os.environ:
                os.environ[key] = val


# Load environment variables on module import
load_env_file()


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "t")


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


class Settings:
    """Application settings loaded from environment variables with typed defaults."""

    @property
    def llm_primary_base_url(self) -> str:
        return os.getenv("LLM_PRIMARY_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

    @property
    def llm_primary_api_key(self) -> str:
        return os.getenv("LLM_PRIMARY_API_KEY", "")

    @property
    def llm_primary_model(self) -> str:
        return os.getenv("LLM_PRIMARY_MODEL", "gemini-2.0-flash")

    @property
    def llm_fallback_base_url(self) -> str:
        return os.getenv("LLM_FALLBACK_BASE_URL", "")

    @property
    def llm_fallback_api_key(self) -> str:
        return os.getenv("LLM_FALLBACK_API_KEY", "")

    @property
    def llm_fallback_model(self) -> str:
        return os.getenv("LLM_FALLBACK_MODEL", "")

    @property
    def price_primary_in_per_mtok(self) -> float:
        return _get_float("PRICE_PRIMARY_IN_PER_MTOK", 0.30)

    @property
    def price_primary_out_per_mtok(self) -> float:
        return _get_float("PRICE_PRIMARY_OUT_PER_MTOK", 2.50)

    @property
    def price_fallback_in_per_mtok(self) -> float:
        return _get_float("PRICE_FALLBACK_IN_PER_MTOK", 0.30)

    @property
    def price_fallback_out_per_mtok(self) -> float:
        return _get_float("PRICE_FALLBACK_OUT_PER_MTOK", 2.50)

    @property
    def neatlogs_api_key(self) -> str:
        return os.getenv("NEATLOGS_API_KEY", "")

    @property
    def neatlogs_endpoint(self) -> str:
        return os.getenv("NEATLOGS_ENDPOINT", "https://ingest.neatlogs.com")

    @property
    def neatlogs_dashboard_url(self) -> str:
        return os.getenv("NEATLOGS_DASHBOARD_URL", "https://app.neatlogs.com")

    @property
    def neatlogs_project_id(self) -> str:
        return os.getenv("NEATLOGS_PROJECT_ID", "72601136-9c61-4e1b-8644-8f9d7a83aedf")

    @property
    def crustdata_api_key(self) -> str:
        return os.getenv("CRUSTDATA_API_KEY", "")

    @property
    def telegram_bot_token(self) -> str:
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def smtp_host(self) -> str:
        return os.getenv("SMTP_HOST", "smtp.gmail.com")

    @property
    def smtp_port(self) -> int:
        return _get_int("SMTP_PORT", 587)

    @property
    def smtp_user(self) -> str:
        return os.getenv("SMTP_USER", "")

    @property
    def smtp_app_password(self) -> str:
        return os.getenv("SMTP_APP_PASSWORD", "")

    @property
    def demo_inbox_email(self) -> str:
        return os.getenv("DEMO_INBOX_EMAIL", "")

    @property
    def public_base_url(self) -> str:
        return os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    @property
    def frontend_base_url(self) -> str:
        return os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

    @property
    def live_research(self) -> bool:
        return _get_bool("LIVE_RESEARCH", False)

    @property
    def retry_sleep_seconds(self) -> float:
        return _get_float("RETRY_SLEEP_SECONDS", 1.0)

    @property
    def demo_mode(self) -> bool:
        return _get_bool("DEMO_MODE", True)

    @property
    def today_override(self) -> str | None:
        val = os.getenv("TODAY_OVERRIDE")
        return val.strip() if val and val.strip() else None

    # Helper properties for configuration status
    @property
    def llm_primary_configured(self) -> bool:
        return bool(self.llm_primary_api_key.strip() and self.llm_primary_model.strip())

    @property
    def llm_fallback_configured(self) -> bool:
        return bool(self.llm_fallback_api_key.strip() and self.llm_fallback_model.strip())

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token.strip() and self.telegram_chat_id.strip())

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_user.strip() and self.smtp_app_password.strip())

    @property
    def neatlogs_configured(self) -> bool:
        return bool(self.neatlogs_api_key.strip())

    @property
    def crustdata_configured(self) -> bool:
        return bool(self.crustdata_api_key.strip())


settings = Settings()

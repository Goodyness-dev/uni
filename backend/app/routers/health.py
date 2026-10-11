from fastapi import APIRouter
from app.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str | bool]:
    """Returns application health and integration configuration statuses."""
    return {
        "status": "ok",
        "llm_primary": "configured" if settings.llm_primary_configured else "missing",
        "llm_fallback": "configured" if settings.llm_fallback_configured else "missing",
        "telegram": "configured" if settings.telegram_configured else "missing",
        "neatlogs": "configured" if settings.neatlogs_configured else "missing",
        "smtp": "configured" if settings.smtp_configured else "missing",
        "crustdata": "configured" if settings.crustdata_configured else "missing",
        "demo_mode": settings.demo_mode,
    }

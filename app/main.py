"""FastAPI application entrypoint for ScholarPilot Production."""
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.deps import get_request_id
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.tracing import init_tracing, shutdown_tracing
from app.jobs.queue import get_redis_client, close_redis_client
import app.core.audit
from app.db.base import AsyncSessionLocal, engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    setup_logging(settings.LOG_LEVEL)
    init_tracing(tags=["api"])
    logger.info(f"Starting ScholarPilot API in {settings.ENVIRONMENT} mode...")

    # Ensure schema is ready in development/test environments
    if settings.ENVIRONMENT != "production":
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized via metadata in non-production mode.")
        except Exception as e:
            logger.error("Database initialization failed; sensitive details excluded.")

    yield

    logger.info("Shutting down ScholarPilot API...")
    shutdown_tracing()
    await close_redis_client()
    await engine.dispose()


app = FastAPI(
    title="ScholarPilot API",
    version="1.0.0",
    description="Autonomous, verification-first scholarship application agent platform.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    expose_headers=["Content-Disposition"])


# Global Exception Handlers for consistent error payloads per Section 11
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    req_id = get_request_id(request.headers.get("X-Request-ID"))
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(detail),
            "request_id": req_id,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = get_request_id(request.headers.get("X-Request-ID"))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "request_id": req_id,
            "details": [{"type": error["type"], "loc": error["loc"]} for error in exc.errors()],
        },
    )


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Lightweight liveness probe."""
    return {
        "status": "healthy",
        "service": "scholarpilot",
        "environment": settings.ENVIRONMENT,
        "kill_switch_active": settings.KILL_SWITCH_ACTIVE,
        "demo_mode": settings.ENVIRONMENT != "production",
        "llm_primary": "configured" if settings.GEMINI_API_KEY or settings.PRIMARY_API_KEY else "missing",
        "llm_fallback": "configured" if settings.ANTHROPIC_API_KEY or settings.FALLBACK_API_KEY else "missing",
        "telegram": "configured" if settings.TELEGRAM_BOT_TOKEN else "missing",
        "neatlogs": "configured" if settings.NEATLOGS_API_KEY else "missing",
        "smtp": "configured" if settings.SMTP_USER and settings.SMTP_APP_PASSWORD else "missing", "crustdata": "missing",
    }


@app.get("/ready", tags=["System"])
async def readiness_check() -> JSONResponse:
    """Readiness probe checking database and core subsystems."""
    checks = {
        "database": False,
        "kill_switch": not settings.KILL_SWITCH_ACTIVE,
    }
    if settings.ENVIRONMENT == "production":
        checks["broker"] = await get_redis_client() is not None
        checks["schema"] = False

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
            if settings.ENVIRONMENT == "production":
                revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
                checks["schema"] = revision == "003_audit_guards"
    except Exception as e:
        logger.error("Readiness database check failed; sensitive details excluded.")

    is_ready = all(checks.values())
    http_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        },
    )


# Mount versioned API routes
app.include_router(api_v1_router)

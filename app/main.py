"""FastAPI application entrypoint for ScholarPilot Production."""
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.api.deps import get_request_id
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.tracing import init_tracing, shutdown_tracing
from app.jobs.queue import get_redis_client
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
            logger.error(f"Database initialization error: {e}")

    yield

    logger.info("Shutting down ScholarPilot API...")
    shutdown_tracing()
    await engine.dispose()


app = FastAPI(
    title="ScholarPilot API",
    version="1.0.0",
    description="Autonomous, verification-first scholarship application agent platform.",
    lifespan=lifespan,
)


# Global Exception Handlers for consistent error payloads per Section 11
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    req_id = get_request_id(request.headers.get("X-Request-ID"))
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(detail),
            "request_id": req_id,
        },
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
            "details": exc.errors(),
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

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness database check failed: {e}")

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

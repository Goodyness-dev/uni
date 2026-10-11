"""FastAPI application entrypoint for ScholarPilot Production."""
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.base import AsyncSessionLocal, engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting ScholarPilot API in {settings.ENVIRONMENT} mode...")

    # Ensure schema is ready in development/test
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

    yield

    logger.info("Shutting down ScholarPilot API...")
    await engine.dispose()


app = FastAPI(
    title="ScholarPilot API",
    version="1.0.0",
    description="Autonomous, verification-first scholarship application agent platform.",
    lifespan=lifespan,
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

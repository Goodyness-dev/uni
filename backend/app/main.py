from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db, mark_interrupted_runs
from app.routers import health, flags
from app.tracing import init_tracing, shutdown_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling startup and shutdown events."""
    if settings.neatlogs_configured:
        init_tracing(tags=["server"])

    init_db()
    mark_interrupted_runs()

    yield

    if settings.neatlogs_configured:
        shutdown_tracing()


app = FastAPI(
    title="ScholarPilot API",
    description="Autonomous, verified scholarship application agent.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(flags.router)

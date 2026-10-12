from fastapi import APIRouter, Depends
from app.core.rate_limiter import rate_limit_dependency
from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.documents import router as documents_router
from app.api.v1.scholarships import router as scholarships_router
from app.api.v1.matches import router as matches_router
from app.api.v1.applications import router as applications_router
from app.api.v1.settings import router as settings_router
from app.api.v1.account import router as account_router
from app.api.v1.runs import router as runs_router
from app.api.v1.onboarding import router as onboarding_router

api_v1_router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(rate_limit_dependency(max_requests=120, window_seconds=60))],
)

api_v1_router.include_router(auth_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(scholarships_router)
api_v1_router.include_router(matches_router)
api_v1_router.include_router(applications_router)
api_v1_router.include_router(settings_router)
api_v1_router.include_router(account_router)
api_v1_router.include_router(runs_router)

api_v1_router.include_router(onboarding_router)

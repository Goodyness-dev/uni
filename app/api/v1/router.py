"""API v1 router aggregating auth, profile, documents, scholarships, and matches."""
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.documents import router as documents_router
from app.api.v1.scholarships import router as scholarships_router
from app.api.v1.matches import router as matches_router

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(scholarships_router)
api_v1_router.include_router(matches_router)

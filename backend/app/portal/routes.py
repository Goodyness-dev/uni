"""Demo scholarship portal routes and mock institution endpoints."""
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import settings
from app import db
from app.agents import scout
from app.portal.content import ABOUT

router = APIRouter(prefix="/portal", tags=["portal"])

templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


class DraftRequest(BaseModel):
    listing_id: str
    idempotency_key: str
    fields: dict[str, Any] = {}


class SubmitRequest(BaseModel):
    draft_id: str
    captcha_answer: str | None = None


# --- Web Page Routes ---

@router.get("/about/{listing_id}", response_class=HTMLResponse)
def get_about_page(listing_id: str, request: Request) -> Response:
    content = ABOUT.get(listing_id)
    if not content:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"error_title": "404 Not Found", "message": f"Institution information for '{listing_id}' not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    flags_data = db.get_flags()
    injection_active = bool(flags_data.get("flags", {}).get("injection_page", False))

    context = {
        "school": content.get("school", ""),
        "mission": content.get("mission", ""),
        "focus": content.get("focus", ""),
        "values": content.get("values", ""),
        "people": content.get("people", ""),
        "news": content.get("news", ""),
        "injection_active": injection_active,
    }
    return templates.TemplateResponse(request=request, name="about.html", context=context)


@router.get("/apply/{listing_id}", response_class=HTMLResponse)
def get_apply_page(listing_id: str, request: Request) -> Response:
    listing = scout.get_listing(listing_id)
    if not listing:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"error_title": "404 Not Found", "message": f"Listing '{listing_id}' not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    flags_data = db.get_flags()
    captcha_flag = bool(flags_data.get("flags", {}).get("captcha_wall", False))
    challenge_active = captcha_flag or (listing.channel == "portal_captcha")

    context = {
        "listing": listing,
        "challenge_active": challenge_active,
    }
    return templates.TemplateResponse(request=request, name="apply.html", context=context)


@router.get("/draft/{draft_id}", response_class=HTMLResponse)
def get_draft_page(draft_id: str, request: Request) -> Response:
    draft = db.get_draft(draft_id)
    if not draft:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"error_title": "404 Not Found", "message": f"Draft '{draft_id}' not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    listing = scout.get_listing(draft["listing_id"])
    flags_data = db.get_flags()
    captcha_flag = bool(flags_data.get("flags", {}).get("captcha_wall", False))
    challenge_active = captcha_flag or (listing is not None and listing.channel == "portal_captcha")

    context = {
        "draft": draft,
        "fields": draft.get("fields", {}),
        "listing": listing,
        "challenge_active": challenge_active,
    }
    return templates.TemplateResponse(request=request, name="draft.html", context=context)


@router.get("/confirm/{code}", response_class=HTMLResponse)
def get_confirmation_page(code: str, request: Request) -> Response:
    return templates.TemplateResponse(request=request, name="confirmation.html", context={"confirmation_code": code})


# --- API Routes ---

@router.post("/api/draft", status_code=status.HTTP_201_CREATED)
def create_draft_endpoint(req: DraftRequest) -> dict[str, str]:
    draft_id = db.create_draft(req.listing_id, req.idempotency_key, req.fields)
    base_url = settings.public_base_url.rstrip("/")
    return {
        "draft_id": draft_id,
        "draft_url": f"{base_url}/portal/draft/{draft_id}",
    }


@router.post("/api/submit")
def submit_draft_endpoint(req: SubmitRequest) -> dict[str, str]:
    # 1. Check transient failure injection
    if db.consume_flag("portal_500"):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "server_error"})

    # 2. Check draft existence
    draft = db.get_draft(req.draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft {req.draft_id} not found")

    # 3. Idempotent check: if already submitted, return existing confirmation code
    if draft.get("submitted") and draft.get("confirmation_code"):
        return {"confirmation_code": draft["confirmation_code"]}

    # 4. Challenge validation
    listing = scout.get_listing(draft["listing_id"])
    flags_data = db.get_flags()
    captcha_flag = bool(flags_data.get("flags", {}).get("captcha_wall", False))
    challenge_required = captcha_flag or (listing is not None and listing.channel == "portal_captcha")

    if challenge_required:
        ans = (req.captcha_answer or "").strip()
        if ans != "12":
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "captcha_required"})

    # 5. Submit draft
    code = db.submit_draft(req.draft_id)
    return {"confirmation_code": code}


@router.get("/api/submissions/{draft_id}")
def get_submission_status_endpoint(draft_id: str) -> dict[str, Any]:
    draft = db.get_draft(draft_id)
    if not draft:
        return {"submitted": False, "confirmation_code": None}

    return {
        "submitted": bool(draft.get("submitted", False)),
        "confirmation_code": draft.get("confirmation_code"),
    }

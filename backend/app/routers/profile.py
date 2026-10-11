"""Profile and intake API endpoints."""
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app import db
from app.agents.intake import run_intake
from app.config import settings
from app.errors import RunContext
from app.models import Fact, Preferences

router = APIRouter(prefix="/api/profile", tags=["profile"])


class IntakeRequest(BaseModel):
    cv_text: str | None = None
    cv_pdf_base64: str | None = None
    transcript_text: str | None = None
    preferences: Preferences | dict[str, Any] | None = None
    vault_sections: dict[str, str] | None = None
    vault_text: str | None = None


class PatchFactRequest(BaseModel):
    text: str


class AddFactRequest(BaseModel):
    category: str
    text: str


@router.post("/intake", status_code=status.HTTP_201_CREATED)
def post_intake(req: IntakeRequest) -> dict[str, Any]:
    """Runs intake over submitted documents and preferences."""
    if not (req.cv_text and req.cv_text.strip()) and not (
        req.cv_pdf_base64 and req.cv_pdf_base64.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of cv_text or cv_pdf_base64 is required",
        )

    payload = req.model_dump()
    result = run_intake(payload, RunContext())
    return {
        "facts": [f.model_dump() if hasattr(f, "model_dump") else f for f in result["facts"]],
        "counts": result["counts"],
        "warnings": result["warnings"],
    }


@router.post("/load_demo", status_code=status.HTTP_201_CREATED)
def post_load_demo() -> dict[str, Any]:
    """Loads synthetic demo persona files and runs intake."""
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo mode disabled",
        )

    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data" / "synthetic"
    cv_path = data_dir / "cv.txt"
    tr_path = data_dir / "transcript.txt"
    pref_path = data_dir / "preferences.json"
    vault_path = data_dir / "vault.json"

    if not (cv_path.exists() and tr_path.exists() and pref_path.exists() and vault_path.exists()):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Synthetic persona files not found",
        )

    cv_text = cv_path.read_text(encoding="utf-8")
    tr_text = tr_path.read_text(encoding="utf-8")
    prefs = json.loads(pref_path.read_text(encoding="utf-8"))
    vault_sections = json.loads(vault_path.read_text(encoding="utf-8"))

    payload = {
        "cv_text": cv_text,
        "transcript_text": tr_text,
        "preferences": prefs,
        "vault_sections": vault_sections,
    }
    result = run_intake(payload, RunContext())
    return {
        "facts": [f.model_dump() if hasattr(f, "model_dump") else f for f in result["facts"]],
        "counts": result["counts"],
        "warnings": result["warnings"],
    }


@router.get("/facts")
def get_facts() -> dict[str, Any]:
    """Returns stored facts and applicant preferences."""
    facts = db.get_facts()
    prefs = db.get_preferences()
    return {
        "facts": facts,
        "preferences": prefs,
    }


@router.patch("/facts/{fact_id}")
def patch_fact(fact_id: str, req: PatchFactRequest) -> dict[str, Any]:
    """Updates an existing fact text."""
    updated = db.update_fact_text(fact_id, req.text)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact not found",
        )
    return updated


@router.post("/facts", status_code=status.HTTP_201_CREATED)
def post_fact(req: AddFactRequest) -> dict[str, Any]:
    """Adds a new fact to the personal vault."""
    created = db.add_vault_fact(req.category, req.text)
    return created

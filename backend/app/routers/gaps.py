"""Gaps API endpoints."""
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app import db
from app.models import Fact

router = APIRouter(prefix="/api/gaps", tags=["gaps"])


class AnswerGapRequest(BaseModel):
    text: str


@router.get("")
def get_gaps(run_id: str | None = None) -> dict[str, Any]:
    """Returns gaps identified for a run (or all gaps if no run_id specified)."""
    gaps = db.list_gaps(run_id)
    return {"gaps": gaps}


@router.post("/{gap_id}/answer", status_code=status.HTTP_200_OK)
def post_answer_gap(gap_id: str, req: AnswerGapRequest) -> dict[str, Any]:
    """Answers a gap, adding the response as a vault fact and marking the gap answered."""
    gap = db.get_gap(gap_id)
    if not gap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gap {gap_id} not found",
        )

    criterion = gap.get("criterion", "general")
    fact = db.add_vault_fact(category=criterion, text=req.text.strip())
    db.answer_gap(gap_id)

    return {"fact": fact}

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import db

router = APIRouter(prefix="/api", tags=["flags"])


class SetFlagsRequest(BaseModel):
    flags: dict[str, bool] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)


@router.get("/failure_flags")
def get_failure_flags() -> dict:
    """Returns status and remaining count of all failure flags."""
    return db.get_flags()


@router.post("/failure_flags")
def set_failure_flags(req: SetFlagsRequest) -> dict:
    """Updates active states and remaining counts for failure flags."""
    for name, enabled in req.flags.items():
        count = req.counts.get(name, 1 if enabled else 0)
        db.set_flag(name, enabled, count)
    return db.get_flags()

"""Scholarship catalog discovery and filtering endpoints."""
import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db_session
from app.db.models import Scholarship

router = APIRouter(prefix="/scholarships", tags=["Scholarships"])


class ScholarshipResponse(BaseModel):
    id: str
    title: str
    provider: str
    country: str
    level: str
    field: str
    amount: float
    currency: str
    deadline: Optional[str] = None
    eligibility_rules: Dict[str, Any]
    application_url: str
    requires_essay: bool
    status: str


class PaginatedScholarships(BaseModel):
    items: List[ScholarshipResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedScholarships)
async def list_scholarships(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    country: Optional[str] = Query(None, description="Filter by host country (e.g. UK, USA)"),
    level: Optional[str] = Query(None, description="Filter by study level (e.g. undergraduate, masters, phd)"),
    field: Optional[str] = Query(None, description="Filter by field of study"),
    min_amount: Optional[float] = Query(None, description="Minimum funding amount"),
    deadline_after: Optional[datetime] = Query(None, description="Only scholarships with deadline after this date"),
    deadline_before: Optional[datetime] = Query(None, description="Only scholarships with deadline before this date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedScholarships:
    """Lists verified scholarship opportunities with multi-attribute filtering."""
    query = select(Scholarship).where(Scholarship.status == "active")

    if country:
        query = query.where(func.lower(Scholarship.country) == country.lower())
    if level:
        query = query.where(func.lower(Scholarship.level) == level.lower())
    if field:
        query = query.where(Scholarship.field.ilike(f"%{field}%"))
    if min_amount is not None:
        query = query.where(Scholarship.amount >= min_amount)
    if deadline_after:
        query = query.where(Scholarship.deadline >= deadline_after)
    if deadline_before:
        query = query.where(Scholarship.deadline <= deadline_before)

    # Count total matching
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(Scholarship.deadline.asc().nullslast()).offset(offset).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return PaginatedScholarships(
        items=[
            ScholarshipResponse(
                id=str(s.id),
                title=s.title,
                provider=s.provider,
                country=s.country,
                level=s.level,
                field=s.field,
                amount=s.amount,
                currency=s.currency,
                deadline=s.deadline.isoformat() if s.deadline else None,
                eligibility_rules=s.eligibility_rules,
                application_url=s.application_url,
                requires_essay=s.requires_essay,
                status=s.status,
            )
            for s in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{scholarship_id}", response_model=ScholarshipResponse)
async def get_scholarship(
    scholarship_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScholarshipResponse:
    """Retrieves full details for a specific scholarship opportunity."""
    s = await db.get(Scholarship, scholarship_id)
    if not s or s.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHOLARSHIP_NOT_FOUND", "message": "Scholarship not found."},
        )

    return ScholarshipResponse(
        id=str(s.id),
        title=s.title,
        provider=s.provider,
        country=s.country,
        level=s.level,
        field=s.field,
        amount=s.amount,
        currency=s.currency,
        deadline=s.deadline.isoformat() if s.deadline else None,
        eligibility_rules=s.eligibility_rules,
        application_url=s.application_url,
        requires_essay=s.requires_essay,
        status=s.status,
    )

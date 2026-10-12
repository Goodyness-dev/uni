"""Document metadata management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db_session
from app.db.models import Document, User
from app.core.storage import managed_document_path

router = APIRouter(prefix="/documents", tags=["Documents"])

DocumentType = Literal["cv", "transcript", "essay", "recommendation", "certificate", "other"]


class CreateDocumentRequest(BaseModel):
    type: DocumentType
    storage_key: str = Field(..., min_length=3, max_length=512)


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    type: str
    storage_key: str
    uploaded_at: str
    verified: bool


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    req: CreateDocumentRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    """Registers an uploaded document's storage key in the user's Profile Vault and verifies facts."""
    try:
        managed_document_path(user.id, req.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc = Document(
        user_id=user.id,
        type=req.type,
        storage_key=req.storage_key,
        uploaded_at=datetime.now(timezone.utc),
        verified=False,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return DocumentResponse(
        id=str(doc.id),
        user_id=str(doc.user_id),
        type=doc.type,
        storage_key=doc.storage_key,
        uploaded_at=doc.uploaded_at.isoformat(),
        verified=doc.verified,
    )


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> List[DocumentResponse]:
    """Lists all documents registered to the authenticated user."""
    stmt = select(Document).where(Document.user_id == user.id).order_by(Document.uploaded_at.desc())
    docs = (await db.execute(stmt)).scalars().all()

    return [
        DocumentResponse(
            id=str(d.id),
            user_id=str(d.user_id),
            type=d.type,
            storage_key=d.storage_key,
            uploaded_at=d.uploaded_at.isoformat(),
            verified=d.verified,
        )
        for d in docs
    ]

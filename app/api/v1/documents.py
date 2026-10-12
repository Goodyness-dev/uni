"""Document metadata management endpoints."""
import uuid
import base64
import binascii
from pypdf.errors import PdfReadError
from pathlib import Path
from datetime import datetime, timezone
from typing import Annotated, List, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db_session
from app.db.models import Document, User, Profile
from app.core.evidence import review_document
from app.core.evidence import read_document, sensitive_evidence
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


class ReviewFact(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2000)
    source_excerpt: str = Field(min_length=1, max_length=4000)


class ReviewDocumentRequest(BaseModel):
    confirmed: bool
    facts: list[ReviewFact] = Field(min_length=1, max_length=100)


class UploadDocumentRequest(BaseModel):
    type: DocumentType
    filename: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=1, max_length=14_000_000)


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(req: UploadDocumentRequest, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> DocumentResponse:
    suffix = Path(req.filename).suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise HTTPException(status_code=400, detail="Only PDF and UTF-8 text uploads are supported.")
    try:
        content = base64.b64decode(req.content_base64, validate=True)
    except binascii.Error:
        raise HTTPException(status_code=400, detail="Upload is not valid base64.")
    if len(content) > 10_000_000:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit.")
    root = (Path("storage/documents") / str(user.id)).absolute()
    if root.resolve() != root:
        raise HTTPException(status_code=400, detail="Managed document directory is invalid.")
    root.mkdir(parents=True, exist_ok=True)
    if sum(file.stat().st_size for file in root.iterdir() if file.is_file()) + len(content) > 50_000_000:
        raise HTTPException(status_code=413, detail="Managed document quota is 50 MB per owner.")
    path = root / (uuid.uuid4().hex + suffix)
    path.write_bytes(content)
    try:
        text, digest = read_document(path)
    except (ValueError, UnicodeError, PdfReadError):
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Document text could not be extracted.")
    document = Document(user_id=user.id, type=req.type, storage_key=str(path), verified=False)
    db.add(document)
    await db.flush()
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
    if profile:
        pending = list(profile.personal_details.get("_pending_facts", []))
        for index, sentence in enumerate(text.split(". ")[:100]):
            if not 15 <= len(sentence.strip()) <= 2000:
                continue
            sensitive = sensitive_evidence(sentence, "profile_evidence")
            pending.append({"id": f"U_{document.id}_{index}", "document_id": str(document.id),
                "text": sentence.strip(), "source_excerpt": sentence.strip(), "category": "sensitive" if sensitive else "profile_evidence",
                "source": req.type if req.type in {"cv", "transcript"} else "vault", "sensitive": sensitive})
        profile.personal_details = {**profile.personal_details, "_pending_facts": pending}
    await db.commit()
    return DocumentResponse(id=str(document.id), user_id=str(user.id), type=document.type,
        storage_key=document.storage_key, uploaded_at=document.uploaded_at.isoformat(), verified=False)


@router.post("/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(document_id: uuid.UUID, req: ReviewDocumentRequest,
    user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db_session)]) -> DocumentResponse:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="Applicant review confirmation is required.")
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=400, detail="Create a profile before reviewing evidence.")
    try:
        await review_document(document, profile, [fact.model_dump() for fact in req.facts], db)
    except (ValueError, OSError, UnicodeError, PdfReadError):
        raise HTTPException(status_code=400, detail="Document facts could not be aligned to the source.")
    return DocumentResponse(id=str(document.id), user_id=str(user.id), type=document.type,
        storage_key=document.storage_key, uploaded_at=document.uploaded_at.isoformat(), verified=document.verified)


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

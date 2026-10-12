"""Document-derived facts with applicant review and content-hash provenance."""
import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.storage import managed_document_path
from app.db.models import Document, Profile


def sensitive_evidence(text: str, category: str) -> bool:
    return category.lower() in {"sensitive", "hardships", "health", "religion", "medical", "financial_need"} or any(
        term in text.lower() for term in ("hardship", "medical", "religion", "illness", "bank account", "national id")
    )


def read_document(path: Path) -> tuple[str, str]:
    if path.stat().st_size > 10_000_000:
        raise ValueError("Document exceeds the review size limit.")
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 40:
            raise ValueError("Encrypted or oversized PDFs cannot be reviewed.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix.lower() in {".txt", ".md"}:
        text = data.decode("utf-8")
    else:
        raise ValueError("Review supports text and PDF documents only.")
    return " ".join(text.split()), hashlib.sha256(data).hexdigest()


async def review_document(document: Document, profile: Profile, facts: list[dict[str, str]], session: AsyncSession) -> None:
    path = managed_document_path(document.user_id, document.storage_key)
    text, digest = read_document(path)
    if not facts or len(facts) > 100:
        raise ValueError("Review requires between 1 and 100 source facts.")
    reviewed = []
    for fact in facts:
        excerpt = " ".join(fact["source_excerpt"].split())
        claim = " ".join(fact["text"].split())
        if not claim or claim not in excerpt or excerpt not in text:
            raise ValueError("Every reviewed fact must occur literally in its document excerpt.")
        reviewed.append({"id": "F_" + uuid.uuid4().hex, "text": claim, "category": fact["category"],
            "document_id": str(document.id), "digest": digest, "source_excerpt": excerpt,
            "source": document.type if document.type in {"cv", "transcript"} else "vault",
            "sensitive": sensitive_evidence(claim, fact["category"]),
            "review": "applicant_reviewed"})
    previous = profile.personal_details.get("_verified_facts", [])
    previous = [fact for fact in previous if fact.get("document_id") != str(document.id)]
    profile.personal_details = {**profile.personal_details, "_verified_facts": previous + reviewed}
    profile.personal_details["_pending_facts"] = [fact for fact in profile.personal_details.get("_pending_facts", []) if fact.get("document_id") != str(document.id)]
    document.verified = True
    await session.commit()


async def approved_facts(profile: Profile, session: AsyncSession) -> list[dict[str, str]]:
    result = []
    for fact in profile.personal_details.get("_verified_facts", []):
        try:
            document = await session.get(Document, uuid.UUID(fact["document_id"]))
        except (KeyError, ValueError):
            continue
        if document is None or document.user_id != profile.user_id or not document.verified:
            continue
        try:
            _, digest = read_document(managed_document_path(profile.user_id, document.storage_key))
        except (ValueError, OSError, UnicodeError, PdfReadError):
            continue
        if digest == fact["digest"]:
            result.append(fact)
    return result


async def assert_current_sources(profile: Profile | None, sources: list[dict[str, str]], session: AsyncSession) -> None:
    """A persisted generated draft cannot outlive changed or erased source documents."""
    current = {fact["id"]: fact["text"] for fact in await approved_facts(profile, session)} if profile else {}
    for source in sources:
        if source.get("kind") == "profile" and current.get(source["id"]) != source["text"]:
            raise ValueError("Reviewed evidence changed; regenerate and verify the draft before continuing.")

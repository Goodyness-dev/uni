"""Owned application packages built from stored drafts, never invented content."""
import os
import textwrap
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.pdfgen import canvas
from app.db.models import Application, Draft, Scholarship, ApplicationEvent
from app.core.tracing import agent_span


def package_path(owner: UUID, application_id: UUID, kind: str) -> Path:
    names = {"cv": "cv.pdf", "essay": "essay.txt", "checklist": "checklist.txt"}
    if kind not in names:
        raise ValueError("Unknown package file kind.")
    root = (Path("storage/packages") / str(owner) / str(application_id)).absolute()
    if root.resolve() != root:
        raise ValueError("Package directories cannot be symlinks.")
    return root / names[kind]


def write_cv(path: Path, body: str) -> None:
    temporary = path.with_suffix(".tmp")
    pdf = canvas.Canvas(str(temporary))
    pdf.setTitle("Application CV evidence")
    pdf.setFont("Helvetica", 11)
    y = 790
    for paragraph in body.splitlines():
        for line in textwrap.wrap(paragraph, width=85) or [""]:
            if y < 50:
                pdf.showPage()
                pdf.setFont("Helvetica", 11)
                y = 790
            pdf.drawString(45, y, line)
            y -= 16
    pdf.save()
    os.replace(temporary, path)


@agent_span("packager", role="Package Builder", goal="Export only stored application evidence")
async def build_package(application: Application, session: AsyncSession) -> dict[str, str]:
    drafts = (await session.execute(select(Draft).where(Draft.application_id == application.id)
        .order_by(Draft.version.desc()))).scalars().all()
    latest = {}
    for draft in drafts:
        latest.setdefault(draft.kind, draft)
    essay = latest.get("essay")
    if essay is None or not essay.content.strip():
        raise ValueError("A nonempty supported draft is required to build a package.")
    cv_text = "\n".join(latest[kind].content for kind in ("cv_summary", "cv_bullets") if kind in latest)
    if not cv_text:
        records = (await session.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "verification_report").order_by(ApplicationEvent.created_at.desc()))).scalars().first()
        sources = {source["id"]: source["text"] for source in (records.payload.get("sources", []) if records else [])}
        cv_text = "\n".join(sources.get(fact, fact) for fact in essay.source_facts if not fact.startswith("F_") or fact in sources)
    if not cv_text.strip():
        raise ValueError("No sourced CV evidence is available.")
    scholarship = await session.get(Scholarship, application.scholarship_id)
    cv = package_path(application.user_id, application.id, "cv")
    cv.parent.mkdir(parents=True, exist_ok=True)
    write_cv(cv, cv_text)
    for kind, body in (("essay", essay.content), ("checklist", "Review every source and document.\nOfficial listing: " + scholarship.application_url + "\nNo guarantee of scholarship selection.\n")):
        path = package_path(application.user_id, application.id, kind)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    return {"cv_pdf_url": f"/v1/applications/{application.id}/files/cv",
        "essay_url": f"/v1/applications/{application.id}/files/essay",
        "checklist_url": f"/v1/applications/{application.id}/files/checklist"}

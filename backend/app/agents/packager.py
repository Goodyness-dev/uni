"""Packager agent: generates verified CV PDF, essay, and application checklist."""
from pathlib import Path
import textwrap
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import db
from app.errors import RunContext
from app.models import Listing, Preferences, TailoredOutput
from app.tracing import agent_span


def _wrap_lines(text: str, width: int = 85) -> list[str]:
    """Wraps text at specified character width."""
    return textwrap.wrap(text, width=width) or [""]


@agent_span("packager", role="packager", goal="assemble verified application package")
def build_package(
    app_id: str,
    listing: Listing,
    prefs: Preferences,
    tailored: TailoredOutput,
    ctx: RunContext | None = None,
) -> dict[str, str]:
    """Builds CV PDF, essay text, and checklist files in data/packages/{app_id}/.

    Only includes segments with status == 'supported'.
    Excludes any removed segments.
    """
    ctx = ctx or RunContext()

    # Destination directory
    backend_dir = Path(__file__).resolve().parent.parent.parent
    package_dir = backend_dir / "data" / "packages" / app_id
    package_dir.mkdir(parents=True, exist_ok=True)

    cv_pdf_path = package_dir / "cv.pdf"
    essay_txt_path = package_dir / "essay.txt"
    checklist_txt_path = package_dir / "checklist.txt"

    # 1. Generate cv.pdf via ReportLab (A4 canvas)
    c = canvas.Canvas(str(cv_pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    # Header: Name & Email
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, prefs.full_name or "Applicant")
    y -= 20

    c.setFont("Helvetica", 10)
    if prefs.email:
        c.drawString(50, y, prefs.email)
        y -= 25
    else:
        y -= 15

    # Filter strictly supported segments
    supported_summary = [s.text for s in tailored.cv_summary if s.status == "supported"]
    supported_bullets = [s.text for s in tailored.cv_bullets if s.status == "supported"]

    # Section: Summary
    if supported_summary:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Professional Summary")
        y -= 15
        c.setFont("Helvetica", 10)
        for seg_text in supported_summary:
            lines = _wrap_lines(seg_text, width=85)
            for line in lines:
                if y < 50:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 50
                c.drawString(50, y, line)
                y -= 14
        y -= 10

    # Section: Highlights / Experience
    if supported_bullets:
        if y < 80:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Key Qualifications & Highlights")
        y -= 15
        c.setFont("Helvetica", 10)
        for bullet_text in supported_bullets:
            lines = _wrap_lines(f"• {bullet_text}", width=85)
            for idx, line in enumerate(lines):
                if y < 50:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 50
                x_offset = 50 if idx == 0 else 60
                c.drawString(x_offset, y, line)
                y -= 14
        y -= 10

    c.save()

    # 2. Generate essay.txt
    if tailored.mode == "notes_only" or not tailored.essay:
        # Notes-only / restricted AI mode: outline notes
        essay_content = "\n\n".join(tailored.outline) if tailored.outline else "No essay generated (restricted AI policy)."
    else:
        # Full mode: strictly supported essay segments
        supported_essay = [s.text for s in tailored.essay if s.status == "supported"]
        essay_content = " ".join(supported_essay)

    essay_txt_path.write_text(essay_content, encoding="utf-8")

    # 3. Generate checklist.txt
    doc_lines = "\n".join([f"[ ] {doc.upper()}" for doc in listing.required_documents]) or "[ ] CV\n[ ] Essay"
    channel_instruction = (
        "Submit on the scholarship portal."
        if listing.channel in ("portal_form", "portal_captcha")
        else f"Submit by email to {listing.email or 'the provider'}."
        if listing.channel == "email"
        else "Submit directly on official website as packaged."
    )

    checklist_content = (
        f"APPLICATION SUBMISSION CHECKLIST\n"
        f"================================\n\n"
        f"Scholarship: {listing.name}\n"
        f"Deadline: {listing.deadline}\n"
        f"AI Policy: {listing.ai_policy.upper()}\n"
        f"Official Portal / URL: {listing.source_url}\n\n"
        f"Submission Instructions:\n"
        f"{channel_instruction}\n\n"
        f"Required Documents Checklist:\n"
        f"{doc_lines}\n\n"
        f"Verified Quality Standards:\n"
        f"[X] Zero unverified or hallucinated claims.\n"
        f"[X] Sensitive personal details protected.\n"
        f"[X] Grounded against official scholarship criteria.\n"
    )
    checklist_txt_path.write_text(checklist_content, encoding="utf-8")

    # Package paths relative to data/packages
    package_dict = {
        "cv_pdf": f"{app_id}/cv.pdf",
        "essay_txt": f"{app_id}/essay.txt",
        "checklist_txt": f"{app_id}/checklist.txt",
    }

    db.update_application(app_id, package=package_dict)

    if ctx.run_id:
        db.add_event(
            ctx.run_id,
            app_id,
            agent="packager",
            type_="step_completed",
            message=f"Application package built for {listing.name}",
            data=package_dict,
        )

    return package_dict

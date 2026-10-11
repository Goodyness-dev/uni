"""Intake agent: extracts atomic facts from CV, transcript, and vault documents."""
import base64
import io
import re
from typing import Any

import pypdf

from app import db
from app.errors import RunContext
from app.llm import call_llm
from app.models import Fact, Preferences
from app.prompts import INTAKE_SYSTEM
from app.schemas import IntakeFact, IntakeOut
from app.sensitive import SENSITIVE_CATEGORIES, is_sensitive_text
from app.tracing import agent_span

VAULT_SECTION_MAPPING: dict[str, str] = {
    "sports": "sports",
    "volunteering": "volunteering",
    "certifications": "certifications",
    "leadership": "leadership",
    "awards": "awards",
    "projects": "projects",
    "languages": "languages",
    "hardships": "hardships",
    "career_goals": "goals",
    "why_abroad": "goals",
}


def extract_cv_text(payload: dict[str, Any], warnings: list[str]) -> str:
    """Extracts CV text from plain text or base64 PDF."""
    cv_text = (payload.get("cv_text") or "").strip()
    if cv_text:
        return cv_text

    pdf_b64 = payload.get("cv_pdf_base64")
    if not pdf_b64:
        return ""

    try:
        raw_bytes = base64.b64decode(pdf_b64)
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        extracted = "\n".join(pages).strip()
        if len(extracted) < 200:
            warnings.append("The PDF text looks too short. Paste your CV text instead.")
        return extracted
    except Exception:
        warnings.append("Failed to parse CV PDF. Paste your CV text instead.")
        return ""


def chunk_document(text: str, max_chars: int = 6000) -> list[str]:
    """Splits document text into paragraph groups of at most max_chars characters."""
    if not text.strip():
        return []
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        p_len = len(p_clean)
        if current and (current_len + p_len + 2 > max_chars):
            chunks.append("\n\n".join(current))
            current = [p_clean]
            current_len = p_len
        else:
            current.append(p_clean)
            current_len += p_len + 2

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _call_intake_llm(text: str, ctx: RunContext) -> list[IntakeFact]:
    """Calls call_llm with intake_v1 prompt and parses IntakeOut."""
    result = call_llm("intake_v1", INTAKE_SYSTEM, text, IntakeOut, ctx)
    parsed = result.parsed
    if isinstance(parsed, dict):
        out = IntakeOut.model_validate(parsed)
        return out.facts
    if isinstance(parsed, IntakeOut):
        return parsed.facts
    return []


def _extract_source_facts(
    chunks: list[str], ctx: RunContext
) -> list[tuple[IntakeFact, str]]:
    """Extracts raw intake facts across chunks, preserving source text for checks."""
    extracted: list[tuple[IntakeFact, str]] = []
    for chunk in chunks:
        facts = _call_intake_llm(chunk, ctx)
        for f in facts:
            extracted.append((f, chunk))
    return extracted


def _extract_vault_facts(
    payload: dict[str, Any], ctx: RunContext
) -> list[tuple[IntakeFact, str]]:
    """Extracts vault facts with section-to-category mapping."""
    sections = payload.get("vault_sections") or {}
    vault_raw: list[tuple[IntakeFact, str]] = []

    for sec_name, sec_text in sections.items():
        text_clean = (sec_text or "").strip()
        if not text_clean:
            continue
        category = VAULT_SECTION_MAPPING.get(sec_name, sec_name)
        prompt_user = f"Section: {sec_name}\n{text_clean}"
        facts = _call_intake_llm(prompt_user, ctx)
        for f in facts:
            forced = IntakeFact(category=category, text=f.text, sensitive=f.sensitive)
            vault_raw.append((forced, text_clean))

    free_vault = (payload.get("vault_text") or "").strip()
    if free_vault:
        for chunk in chunk_document(free_vault):
            facts = _call_intake_llm(chunk, ctx)
            for f in facts:
                vault_raw.append((f, chunk))

    return vault_raw


def _filter_and_assign_ids(
    raw_facts: list[tuple[IntakeFact, str]],
    source: str,
    prefix: str,
    seen_texts: set[str],
    warnings: list[str],
) -> list[Fact]:
    """Applies deduplication, sensitive flags, number verification, and assigns IDs."""
    assigned: list[Fact] = []
    index = 1

    for item, source_text in raw_facts:
        text = item.text.strip()
        if not text:
            continue

        norm_key = re.sub(r"\s+", " ", text.lower())
        if norm_key in seen_texts:
            continue
        seen_texts.add(norm_key)

        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        invalid_number = any(num not in source_text for num in numbers)
        if invalid_number:
            warnings.append("Dropped a fact whose numbers were not in the source")
            continue

        cat = item.category.strip() or "other"
        sensitive = (
            item.sensitive
            or is_sensitive_text(text)
            or (cat in SENSITIVE_CATEGORIES)
        )

        assigned.append(
            Fact(
                id=f"{prefix}{index}",
                source=source,  # type: ignore[arg-type]
                category=cat,
                text=text,
                sensitive=sensitive,
            )
        )
        index += 1

    return assigned


@agent_span("intake", role="intake", goal="extract atomic facts from cv, transcript, and vault")
def run_intake(
    payload: dict[str, Any], ctx: RunContext | None = None
) -> dict[str, Any]:
    """Runs intake extraction over CV, transcript, and vault documents."""
    ctx = ctx or RunContext()
    warnings: list[str] = []
    seen_texts: set[str] = set()

    cv_text = extract_cv_text(payload, warnings)
    cv_chunks = chunk_document(cv_text)
    cv_raw = _extract_source_facts(cv_chunks, ctx)
    cv_facts = _filter_and_assign_ids(cv_raw, "cv", "C", seen_texts, warnings)

    tr_text = (payload.get("transcript_text") or "").strip()
    tr_chunks = chunk_document(tr_text)
    tr_raw = _extract_source_facts(tr_chunks, ctx)
    tr_facts = _filter_and_assign_ids(tr_raw, "transcript", "T", seen_texts, warnings)

    v_raw = _extract_vault_facts(payload, ctx)
    v_facts = _filter_and_assign_ids(v_raw, "vault", "P", seen_texts, warnings)

    all_facts = cv_facts + tr_facts + v_facts
    db.replace_facts(all_facts)

    prefs_raw = payload.get("preferences")
    if prefs_raw:
        if isinstance(prefs_raw, dict):
            prefs = Preferences.model_validate(prefs_raw)
        elif isinstance(prefs_raw, Preferences):
            prefs = prefs_raw
        else:
            prefs = None
        if prefs:
            db.set_preferences(prefs)

    counts = {"cv": len(cv_facts), "transcript": len(tr_facts), "vault": len(v_facts)}
    if ctx.run_id:
        db.add_event(ctx.run_id, None, "intake", "step_completed", "Intake extraction complete", counts)

    return {
        "facts": all_facts,
        "counts": counts,
        "warnings": warnings,
    }

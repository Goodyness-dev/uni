"""Verifier agent: deterministic source checking, claim audit, and adversarial challenge."""
import re
from typing import Any

from app import db
from app.errors import RunContext
from app.llm import call_llm
from app.models import (
    Claim,
    RemovedClaim,
    Segment,
    TailoredOutput,
    VerificationReport,
)
from app.prompts import (
    CHALLENGER_SYSTEM,
    VERIFIER_EXTRACT_SYSTEM,
    VERIFIER_JUDGE_SYSTEM,
)
from app.schemas import ChallengeOut, ExtractOut, JudgeOut
from app.tracing import agent_span, guardrail, tool_span

NUMBER_WORDS: dict[str, str] = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "twelve": "12", "twenty": "20", "fifty": "50", "hundred": "100",
}

CAP_STOPWORDS: set[str] = {
    "I", "The", "A", "An", "My", "In", "On", "At", "And", "We", "Our", "It"
}


def _normalize_tokens(text: str) -> str:
    """Replaces English number words with digits and collapses whitespace."""
    tokens = text.split()
    norm = [NUMBER_WORDS.get(t.lower().rstrip(".,:;"), t) for t in tokens]
    return " ".join(norm).lower()


@tool_span("deterministic_claim_check", description="deterministic verification of numbers and entities")
def deterministic_check(
    claim_text: str, source_ids: list[str], sources: dict[str, str]
) -> bool:
    """Verifies that numbers and capitalized entities in a claim exist in cited sources."""
    if not source_ids or any(sid not in sources for sid in source_ids):
        return False

    raw_sources = " ".join(sources[sid] for sid in source_ids)
    source_blob = _normalize_tokens(raw_sources)
    claim_norm = _normalize_tokens(claim_text)

    # 1. Number check
    claim_numbers = re.findall(r"\d+(?:\.\d+)?", claim_norm)
    for num in claim_numbers:
        pattern = rf"(?<!\d){re.escape(num)}(?!\d)"
        if not re.search(pattern, source_blob):
            return False

    # 2. Capitalized entity check (excluding sentence starters and stopwords)
    sentences = re.split(r"[.!?]\s*", claim_text.strip())
    for sent in sentences:
        tokens = sent.strip().split()
        if len(tokens) <= 1:
            continue
        for t in tokens[1:]:
            clean_word = re.sub(r"[^\w]", "", t)
            if (
                clean_word
                and clean_word[0].isupper()
                and len(clean_word) > 2
                and clean_word not in CAP_STOPWORDS
            ):
                if clean_word.lower() not in source_blob:
                    return False

    return True


def _extract_claims(
    tailored: TailoredOutput, sources: dict[str, str], ctx: RunContext
) -> list[Claim]:
    """Extracts atomic checkable statements from tailored sections."""
    segments_to_check: list[tuple[str, int, Segment]] = []
    for idx, s in enumerate(tailored.cv_summary):
        if s.status != "removed":
            segments_to_check.append(("cv_summary", idx, s))
    for idx, s in enumerate(tailored.cv_bullets):
        if s.status != "removed":
            segments_to_check.append(("cv_bullets", idx, s))
    for idx, s in enumerate(tailored.essay):
        if s.status != "removed":
            segments_to_check.append(("essay", idx, s))

    sentences_input = [
        f"[{sec}:{idx}] {s.text}"
        for sec, idx, s in segments_to_check
    ]
    user_text = "Extract atomic claims from sentences:\n" + "\n".join(sentences_input)

    res = call_llm("verifier_extract_v1", VERIFIER_EXTRACT_SYSTEM, user_text, ExtractOut, ctx)
    parsed = res.parsed
    out = ExtractOut.model_validate(parsed) if isinstance(parsed, dict) else (parsed or ExtractOut())

    claims: list[Claim] = []
    seg_map = {(sec, idx): s for sec, idx, s in segments_to_check}

    claim_idx = 1
    for c in out.claims:
        key = (c.section, c.segment_index)
        parent_seg = seg_map.get(key)
        s_ids = parent_seg.source_ids if parent_seg else []
        claims.append(
            Claim(
                id=f"CL{claim_idx}",
                text=c.text.strip(),
                segment_index=c.segment_index,
                section=c.section,  # type: ignore[arg-type]
                source_ids=s_ids,
            )
        )
        claim_idx += 1

    # Fallback: if no claims extracted for a segment, use segment text as a claim
    covered = {(c.section, c.segment_index) for c in claims}
    for sec, idx, s in segments_to_check:
        if (sec, idx) not in covered:
            claims.append(
                Claim(
                    id=f"CL{claim_idx}",
                    text=s.text.strip(),
                    segment_index=idx,
                    section=sec,  # type: ignore[arg-type]
                    source_ids=s.source_ids,
                )
            )
            claim_idx += 1

    return claims


def _judge_batch(
    batch: list[Claim], sources: dict[str, str], ctx: RunContext
) -> list[tuple[str, str]]:
    """Judges up to 10 claims with verifier_judge_v1."""
    lines = []
    for c in batch:
        c_srcs = " | ".join(f"{sid}: {sources.get(sid, '')}" for sid in c.source_ids)
        lines.append(f"{c.id}: Claim='{c.text}' CitedSources='{c_srcs}'")

    user_text = "Judge these claims:\n" + "\n".join(lines)
    res = call_llm("verifier_judge_v1", VERIFIER_JUDGE_SYSTEM, user_text, JudgeOut, ctx)
    parsed = res.parsed
    out = JudgeOut.model_validate(parsed) if isinstance(parsed, dict) else (parsed or JudgeOut())

    v_map = {item.claim_id: (item.verdict.lower().strip(), item.reason.strip()) for item in out.verdicts}
    results = []
    for c in batch:
        verdict, reason = v_map.get(c.id, ("unsupported", "No judge output"))
        if verdict not in ("supported", "partial", "unsupported"):
            verdict = "unsupported"
        results.append((verdict, reason))
    return results


def audit(
    tailored: TailoredOutput, sources: dict[str, str], ctx: RunContext, round_no: int = 1
) -> VerificationReport:
    """Extracts, deterministically checks, and LLM-judges claims against sources."""
    claims = _extract_claims(tailored, sources, ctx)

    # 1. Deterministic check
    for c in claims:
        c.deterministic_pass = deterministic_check(c.text, c.source_ids, sources)

    # 2. Batched judging
    for i in range(0, len(claims), 10):
        batch = claims[i : i + 10]
        judgments = _judge_batch(batch, sources, ctx)
        for c, (llm_verdict, reason) in zip(batch, judgments):
            c.reason = reason
            c.llm_pass = (llm_verdict == "supported")
            if llm_verdict == "unsupported":
                c.verdict = "unsupported"
            elif llm_verdict == "partial":
                c.verdict = "partial"
            elif llm_verdict == "supported":
                c.verdict = "supported" if c.deterministic_pass else "partial"

    unsupported_count = sum(1 for c in claims if c.verdict != "supported")
    with guardrail("verification_round") as gr:
        gr.set_result(
            passed=(unsupported_count == 0),
            input_text=f"Round {round_no} checking {len(claims)} claims",
            reason=f"{unsupported_count} claims unsupported",
        )
        gr.attrs(
            round=round_no,
            claims_checked=len(claims),
            claims_unsupported=unsupported_count,
        )

    return VerificationReport(
        rounds=round_no,
        claims=claims,
        removed_claims=[],
        overturned_claims=[],
        unsupported_before=unsupported_count,
        unsupported_final=unsupported_count,
    )


def challenge(
    report: VerificationReport, sources: dict[str, str], ctx: RunContext
) -> VerificationReport:
    """Challenges supported claims with adversarial review to find overreach."""
    supported = [c for c in report.claims if c.verdict == "supported"]
    overturned_claims: list[RemovedClaim] = []

    for i in range(0, len(supported), 10):
        batch = supported[i : i + 10]
        lines = []
        for c in batch:
            c.challenged = True
            c_srcs = " | ".join(f"{sid}: {sources.get(sid, '')}" for sid in c.source_ids)
            lines.append(f"{c.id}: Claim='{c.text}' CitedSources='{c_srcs}'")

        user_text = "Challenge these claims:\n" + "\n".join(lines)
        res = call_llm("challenger_v1", CHALLENGER_SYSTEM, user_text, ChallengeOut, ctx)
        parsed = res.parsed
        out = ChallengeOut.model_validate(parsed) if isinstance(parsed, dict) else (parsed or ChallengeOut())

        c_map = {item.claim_id: (item.outcome.lower().strip(), item.reason.strip()) for item in out.challenges}
        for c in batch:
            outcome, reason = c_map.get(c.id, ("defend", ""))
            if outcome == "overturn":
                c.overturned = True
                overturned_claims.append(RemovedClaim(text=c.text, reason=reason))
                if ctx.run_id:
                    db.add_event(
                        ctx.run_id,
                        ctx.application_id or None,
                        "challenger",
                        "claim_overturned",
                        f"Claim overturned: {reason}",
                        {"claim_id": c.id, "claim_text": c.text},
                    )

    with guardrail("adversarial_challenge") as gr:
        gr.set_result(
            passed=(len(overturned_claims) == 0),
            input_text=f"Challenged {len(supported)} claims",
            reason=f"{len(overturned_claims)} claims overturned",
        )
        gr.attrs(claims_overturned=len(overturned_claims))

    report.overturned_claims = overturned_claims
    return report


@agent_span("verifier", role="verifier", goal="strict audit and adversarial verification of claims")
def verify_mode_a(
    tailored: TailoredOutput, sources: dict[str, str], ctx: RunContext | None = None
) -> tuple[TailoredOutput, VerificationReport]:
    """Runs measurement-only audit and challenge without modifying the tailored text."""
    ctx = ctx or RunContext()
    report = audit(tailored, sources, ctx, round_no=1)
    report_challenged = challenge(report, sources, ctx)
    report_challenged.unsupported_final = report_challenged.unsupported_before
    return tailored, report_challenged

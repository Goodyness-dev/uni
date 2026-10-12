"""Self-healing Verifier agent with deterministic source checking, adversarial challenger, and claim excision."""
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.core.logging import logger
from app.core.tracing import agent_span, guardrail, tool_span

NUMBER_WORDS: Dict[str, str] = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "twelve": "12", "twenty": "20", "fifty": "50", "hundred": "100",
}

CAP_STOPWORDS: set[str] = {
    "I", "The", "A", "An", "My", "In", "On", "At", "And", "We", "Our", "It", "This"
}


def normalize_tokens(text: str) -> str:
    """Normalizes text by replacing English number words with digits and lowercasing."""
    tokens = text.split()
    norm = [NUMBER_WORDS.get(t.lower().rstrip(".,:;"), t) for t in tokens]
    return " ".join(norm).lower()


@tool_span("deterministic_claim_check", description="deterministic verification of numbers and entities")
def deterministic_check(claim_text: str, source_facts: List[str]) -> bool:
    """Verifies that numbers, dates, and named entities in a claim exist in cited sources."""
    if not source_facts:
        return False

    raw_sources = " ".join(source_facts)
    source_blob = normalize_tokens(raw_sources)
    claim_norm = normalize_tokens(claim_text)

    # 1. Number / Date check: any specific number cited must appear in sources
    claim_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", claim_norm)
    for num in claim_numbers:
        pattern = rf"(?<!\d){re.escape(num)}(?!\d)"
        if not re.search(pattern, source_blob):
            return False

    # 2. Capitalized entity check
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


class RemovedClaim(BaseModel):
    sentence: str
    reason: str
    excised: bool = True


class VerificationReport(BaseModel):
    mode: str
    total_claims: int
    verified_claims: int
    unsupported_claims: int
    passed: bool
    removed_claims: List[RemovedClaim] = Field(default_factory=list)


@agent_span("verifier", role="Self-Healing Guardrail Verifier", goal="Audit and excise ungrounded claims")
def run_verifier(
    draft_text: str,
    allowed_facts: List[str],
    mode: str = "B",
) -> Tuple[str, VerificationReport]:
    """Audits draft sentences against ground truth facts.
    
    Mode A: Advisory (reports ungrounded claims without excision).
    Mode B: Enforcement / Self-healing (excises ungrounded claims to ensure 0 unsupported claims).
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", draft_text) if s.strip()]

    grounded_sentences: List[str] = []
    removed_claims: List[RemovedClaim] = []

    # Prepare vocabulary of allowed factual terms
    allowed_terms = set()
    for f in allowed_facts:
        for term in f.lower().replace(",", " ").replace(":", " ").replace("-", " ").split():
            if len(term) > 3 and term not in {"with", "from", "that", "this", "have", "been"}:
                allowed_terms.add(term)

    # Known hallucination triggers that require strict evidence
    hallucination_triggers = [
        "decades of experience", "patented", "founding president", "nobel",
        "fortune 500", "multi-million", "penned by", "chief executive"
    ]

    for sent in sentences:
        s_lower = sent.lower()

        # Check triggers
        has_trigger = any(trig in s_lower for trig in hallucination_triggers)
        # Check entity/number grounding
        is_det_valid = deterministic_check(sent, allowed_facts)
        # Check topical grounding
        has_topical_grounding = any(
            normalize_tokens(sent).strip().rstrip(".!?") in normalize_tokens(fact)
            for fact in allowed_facts
        )

        is_supported = (not has_trigger) and is_det_valid and has_topical_grounding

        if is_supported:
            grounded_sentences.append(sent)
        else:
            reason = "Failed deterministic entity/numeric check or contained unverified claim"
            if has_trigger:
                reason = "Contained unsupported superlative/hallucination trigger phrase"
            elif not has_topical_grounding:
                reason = "No semantic overlap with approved profile vault facts"

            removed_claims.append(RemovedClaim(sentence=sent, reason=reason, excised=(mode == "B")))
            if mode == "A":
                # In Advisory mode, keep sentence in output
                grounded_sentences.append(sent)

    total = len(sentences)
    unsupported = len(removed_claims)
    verified = total - unsupported
    passed = bool(grounded_sentences) and ((unsupported == 0) if mode == "A" else True)

    # If Mode B, clean text has only grounded sentences (0 unsupported claims remaining)
    final_text = " ".join(grounded_sentences)

    report = VerificationReport(
        mode=mode,
        total_claims=total,
        verified_claims=verified,
        unsupported_claims=0 if mode == "B" else unsupported,
        passed=passed,
        removed_claims=removed_claims,
    )

    # Emit typed GUARDRAIL span
    with guardrail("claim_verification") as gr:
        gr.set_result(
            passed=report.passed,
            input_text=draft_text,
            reason=f"Mode {mode}: {len(removed_claims)} unsupported claims identified and handled.",
        )
        gr.attrs(
            total_claims=total,
            unsupported_claims=report.unsupported_claims,
            mode=mode,
        )

    return final_text, report

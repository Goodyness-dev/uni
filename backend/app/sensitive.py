import re
from typing import Any
from app.models import Fact, Listing

SENSITIVE_CATEGORIES: set[str] = {
    "health",
    "religion",
    "disability",
    "family_income",
    "immigration",
}

SENSITIVE_STEMS: list[str] = [
    "health", "medical", "illness", "disease",
    "disabled", "disability",
    "religion", "church", "mosque", "pastor", "imam",
    "income", "poverty", "salary",
    "immigration", "visa", "refugee",
]

_STEM_REGEXES = [re.compile(r"\b" + re.escape(stem), re.IGNORECASE) for stem in SENSITIVE_STEMS]


def is_sensitive_text(text: str) -> bool:
    """Returns True if any sensitive stem appears as a word start."""
    for pattern in _STEM_REGEXES:
        if pattern.search(text):
            return True
    return False


def strip_sensitive(facts: list[Fact], listing: Listing, consent: bool) -> list[Fact]:
    """Removes sensitive facts unless consent is True and category is explicitly required."""
    allowed: list[Fact] = []
    required_cats = set(listing.requires_sensitive)

    for fact in facts:
        is_category_sensitive = fact.category in SENSITIVE_CATEGORIES
        is_marked_sensitive = fact.sensitive or is_category_sensitive or is_sensitive_text(fact.text)

        if not is_marked_sensitive:
            allowed.append(fact)
            continue

        # If sensitive, allowed only with consent AND listing explicitly requires that category
        if consent and fact.category in required_cats:
            allowed.append(fact)

    return allowed


def contains_sensitive(output_text: str) -> list[str]:
    """Scans text and returns all matched sensitive stems."""
    matched = []
    for stem, pattern in zip(SENSITIVE_STEMS, _STEM_REGEXES):
        if pattern.search(output_text):
            matched.append(stem)
    return matched

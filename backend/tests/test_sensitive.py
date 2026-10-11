from app.models import Fact, Listing
from app.sensitive import (
    is_sensitive_text,
    strip_sensitive,
    contains_sensitive,
    SENSITIVE_CATEGORIES,
)


def test_is_sensitive_text():
    assert is_sensitive_text("Diagnosed with a chronic medical condition") is True
    assert is_sensitive_text("Active member of church youth group") is True
    assert is_sensitive_text("From a low income family") is True
    assert is_sensitive_text("Regular software engineering project") is False


def test_strip_sensitive_no_consent():
    listing = Listing(
        id="listing_1",
        name="Test Award",
        is_mock=True,
        provider="Provider",
        country="UK",
        level="masters",
        fields=["CS"],
        deadline="2027/01/01",
        channel="portal_form",
        criteria_text="Criteria",
        essay_prompt="Prompt",
    )
    facts = [
        Fact(id="P1", source="vault", category="sports", text="Soccer player"),
        Fact(id="P2", source="vault", category="health", text="Chronic illness diagnosis"),
        Fact(id="P3", source="vault", category="religion", text="President of church group"),
    ]

    filtered = strip_sensitive(facts, listing, consent=False)
    assert len(filtered) == 1
    assert filtered[0].id == "P1"


def test_strip_sensitive_with_consent_and_matching_listing():
    listing = Listing(
        id="listing_1",
        name="Need Based Award",
        is_mock=True,
        provider="Provider",
        country="UK",
        level="masters",
        fields=["CS"],
        deadline="2027/01/01",
        channel="portal_form",
        criteria_text="Criteria",
        essay_prompt="Prompt",
        requires_sensitive=["health"],
    )
    facts = [
        Fact(id="P1", source="vault", category="sports", text="Soccer player"),
        Fact(id="P2", source="vault", category="health", text="Chronic illness diagnosis"),
        Fact(id="P3", source="vault", category="religion", text="President of church group"),
    ]

    filtered = strip_sensitive(facts, listing, consent=True)
    # P1 (clean) and P2 (health matches requires_sensitive + consent) should be kept; P3 (religion) stripped
    assert len(filtered) == 2
    ids = {f.id for f in filtered}
    assert "P1" in ids
    assert "P2" in ids
    assert "P3" not in ids


def test_contains_sensitive():
    assert len(contains_sensitive("Recipient of university scholarship")) == 0
    stems = contains_sensitive("Overcame financial poverty and medical hardships")
    assert "poverty" in stems
    assert "medical" in stems

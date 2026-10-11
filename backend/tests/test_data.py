"""Tests for synthetic persona files, listings, and traps (Task B06)."""
import json
from pathlib import Path
import pytest
from app.models import Listing

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_listings_data_validity():
    listings_path = DATA_DIR / "listings.json"
    assert listings_path.exists(), "listings.json must exist"

    raw = json.loads(listings_path.read_text(encoding="utf-8"))
    assert "listings" in raw, "listings.json must have 'listings' key"
    listings_list = raw["listings"]

    # Must have exactly 5 listings (3 mock, 2 real)
    assert len(listings_list) == 5, f"Expected 5 listings, got {len(listings_list)}"

    mock_count = sum(1 for item in listings_list if item.get("is_mock"))
    assert mock_count == 3, f"Expected 3 mock listings, got {mock_count}"

    # Validate each listing against Pydantic Listing model
    for item in listings_list:
        listing = Listing.model_validate(item)
        assert listing.id, "Listing must have an id"
        assert listing.name, "Listing must have a name"

        # No field may contain 'REPLACE'
        dumped = json.dumps(item)
        assert "REPLACE" not in dumped, f"Listing {listing.id} still contains placeholder REPLACE"


def test_persona_files_and_traps():
    synth_dir = DATA_DIR / "synthetic"
    assert synth_dir.exists(), "synthetic directory must exist"

    cv_path = synth_dir / "cv.txt"
    tr_path = synth_dir / "transcript.txt"
    pref_path = synth_dir / "preferences.json"
    vault_path = synth_dir / "vault.json"

    assert cv_path.exists()
    assert tr_path.exists()
    assert pref_path.exists()
    assert vault_path.exists()

    cv_text = cv_path.read_text(encoding="utf-8")
    vault_text = vault_path.read_text(encoding="utf-8")

    # Trap 1: Vault says assistant coordinator; CV does not say president
    assert "assistant coordinator" in vault_text.lower()
    assert "president" not in cv_text.lower()

    # Trap 2: Internship duration is 5 months
    assert "5 months" in cv_text.lower()

    # Trap 4: Hardship fact exists in vault
    assert "income" in vault_text.lower() or "hardship" in vault_text.lower()


def test_dossier_caches_exist():
    cache_dir = DATA_DIR / "dossier_cache"
    assert cache_dir.exists()

    for mock_id in ["mock_portal_masters", "mock_captcha_award", "mock_email_award"]:
        cache_file = cache_dir / f"{mock_id}.json"
        assert cache_file.exists(), f"Dossier cache for {mock_id} must exist"
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["listing_id"] == mock_id
        assert len(data["facts"]) >= 4

"""Tests for LLM Provider Switching (Gemini <-> Claude) and Extended Scholarship Catalog."""
import asyncio
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from app.core.config import settings
from app.core.llm_gateway import call_llm, set_active_llm_provider
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Scholarship
from scripts.import_catalog import import_listings


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes and tears down in-memory test database and seeds catalog."""
    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        catalog_path = Path(__file__).resolve().parent.parent / "backend" / "data" / "listings.json"
        if catalog_path.exists():
            await import_listings(catalog_path)

    async def teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(init())
    yield
    asyncio.run(teardown())


def test_provider_switching_configuration():
    """Verifies that active LLM provider can be switched cleanly between Gemini and Claude."""
    set_active_llm_provider("gemini")
    assert settings.LLM_PROVIDER == "gemini"

    set_active_llm_provider("claude")
    assert settings.LLM_PROVIDER == "claude"

    with pytest.raises(ValueError):
        set_active_llm_provider("invalid_provider")

    # Reset back to gemini
    set_active_llm_provider("gemini")
    assert settings.LLM_PROVIDER == "gemini"


def test_mock_llm_gateway_gemini_and_claude():
    """Verifies that call_llm executes cleanly under both Gemini and Claude provider configurations."""
    async def run():
        # Test under Gemini mode
        set_active_llm_provider("gemini")
        resp_gemini = await call_llm(
            system_prompt="You are ScholarPilot.",
            user_prompt="Hello Gemini.",
            mock_response='{"message": "Hello from Gemini"}',
        )
        assert resp_gemini.content == '{"message": "Hello from Gemini"}'

        # Test under Claude mode
        set_active_llm_provider("claude")
        resp_claude = await call_llm(
            system_prompt="You are ScholarPilot.",
            user_prompt="Hello Claude.",
            mock_response='{"message": "Hello from Claude"}',
        )
        assert resp_claude.content == '{"message": "Hello from Claude"}'

        # Reset back to gemini
        set_active_llm_provider("gemini")

    asyncio.run(run())


def test_expanded_scholarship_catalog_and_portals():
    """Verifies that the expanded scholarship listings and portals JSON files are valid and populated."""
    catalog_path = Path(__file__).resolve().parent.parent / "backend" / "data" / "listings.json"
    portals_path = Path(__file__).resolve().parent.parent / "backend" / "data" / "scholarship_portals.json"

    assert catalog_path.exists()
    assert portals_path.exists()

    # Verify portals JSON
    portals_data = json.loads(portals_path.read_text(encoding="utf-8"))
    portals = portals_data.get("portals", [])
    assert len(portals) == 60  # All 60 portals across Tier 1, 2, and 3
    
    tiers = {p["tier"] for p in portals}
    assert tiers == {1, 2, 3}

    # Verify database catalog population
    async def run():
        async with AsyncSessionLocal() as session:
            schol_list = (await session.execute(select(Scholarship))).scalars().all()
            assert len(schol_list) >= 12

            titles = {s.title for s in schol_list}
            assert "Chevening Scholarships" in titles
            assert "Commonwealth Master's Scholarships" in titles
            assert "Fulbright Foreign Student Program" in titles
            assert "Rhodes Scholarship for West Africa" in titles
            assert "Gates Cambridge Scholarship" in titles
            assert "PTDF Overseas Scholarship Scheme" in titles
            assert "Mastercard Foundation Scholars Program" in titles
            assert "Erasmus Mundus Joint Masters Scholarships" in titles
            assert "Swedish Institute Scholarship for Global Professionals (SISGP)" in titles
            assert "DAAD Development-Related Postgraduate Courses (EPOS)" in titles
            assert "Vanier Canada Graduate Scholarships" in titles
            assert "Turkiye Burslari Government Scholarships" in titles

    asyncio.run(run())

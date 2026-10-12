"""Acceptance and queue tests for Milestone 3: Agents on a Queue."""
import asyncio
import uuid
import pytest
from sqlalchemy import select
from app.agents.drafter import DrafterInput, enforce_word_limit, perform_grounding_check, run_drafter
from app.agents.edge_finder import EdgeFinderInput, run_edge_finder
from app.agents.matcher import MatcherInput, run_matcher
from app.agents.researcher import ResearcherInput, run_researcher
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, Draft, Profile, Scholarship, User
from app.jobs.queue import enqueue_job, execute_job
from scripts.import_catalog import import_listings
from pathlib import Path


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


def test_word_limit_enforcement():
    """Verifies that in-code word limits strictly cap word count and maintain punctuation."""
    long_essay = " ".join(["word"] * 600)
    trimmed, count = enforce_word_limit(long_essay, 500)
    assert count == 500
    assert len(trimmed.split()) == 500
    assert trimmed.endswith(".")


def test_grounding_check_removes_unverified_claims():
    """Verifies that ungrounded or hallucinated claims are stripped from final draft."""
    allowed = ["I completed my Computer Engineering degree with a 4.8 GPA."]
    draft = "I completed my Computer Engineering degree with a 4.8 GPA. I am also the founding president of a global venture fund."
    clean, sources, flagged = perform_grounding_check(draft, allowed)
    assert len(flagged) == 1
    assert "founding president" in flagged[0]
    assert "founding president" not in clean
    assert "Computer Engineering degree" in clean


def test_agents_queue_three_grounded_drafts():
    """Full Milestone 3 acceptance test:
    One profile produces grounded drafts for 3 scholarships with no unsourced claims.
    """
    async def run():
        # 1. Create student and Profile Vault
        async with AsyncSessionLocal() as session:
            user = User(email="student.queue@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()
            await session.refresh(user)

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Chidi", "nationalities": ["Nigeria"]},
                education_history=[
                    {"institution": "University of Lagos", "degree": "B.Sc. Systems Engineering", "year": 2025}
                ],
                grades={"gpa": 4.75, "gpa_scale": 5.0},
                achievements=[
                    {"title": "Lead Engineer, Solar Inverter IoT Monitor", "year": 2024},
                    {"title": "Winner, Shell STEM Innovation Award", "year": 2025},
                ],
                financial_need_info={"statement": "First-generation graduate seeking postgraduate scholarship"},
                target_countries=["UK", "Canada"],
                target_fields_of_study=["artificial intelligence", "computer engineering", "energy systems"],
                completeness_score=95.0,
            )
            session.add(profile)
            await session.commit()
            user_id = user.id

        # 2. Run Matcher Agent via Job Queue
        matcher_job = await enqueue_job("matcher", {"user_id": str(user_id)})
        match_res = await execute_job(matcher_job.id, {"user_id": str(user_id)})
        matches = match_res["matches"]
        assert len(matches) >= 3, f"Expected at least 3 matches, got {len(matches)}"

        top_3_matches = matches[:3]

        # 3. For each of the top 3 scholarships, execute Researcher -> Edge Finder -> Drafter
        drafted_applications: list[Draft] = []

        async with AsyncSessionLocal() as session:
            for match_item in top_3_matches:
                schol_id = uuid.UUID(match_item["scholarship_id"])
                schol = await session.get(Scholarship, schol_id)

                # Create Application row
                app_record = Application(
                    user_id=user_id,
                    scholarship_id=schol_id,
                    status="drafting",
                    mode_used="autopilot",
                )
                session.add(app_record)
                await session.commit()
                await session.refresh(app_record)

                # A. Run Researcher Job
                research_job = await enqueue_job("researcher", {"scholarship_id": str(schol_id)})
                research_res = await execute_job(research_job.id, {"scholarship_id": str(schol_id)})
                assert len(research_res["facts"]) == 1
                assert "Fictional institutional page" in research_res["facts"][0]["claim"]
                for fact in research_res["facts"]:
                    assert fact["source_url"], "Every fact must have a source URL"
                    assert fact["retrieved_at"], "Every fact must have a retrieved_at timestamp"

                # Verify 7-day caching on repeat call
                repeat_job = await enqueue_job("researcher", {"scholarship_id": str(schol_id)})
                repeat_res = await execute_job(repeat_job.id, {"scholarship_id": str(schol_id)})
                assert repeat_res["from_cache"] is True

                # B. Run Edge Finder Job
                edge_job = await enqueue_job("edge_finder", {
                    "user_id": str(user_id),
                    "scholarship_id": str(schol_id),
                    "research_facts": research_res["facts"],
                })
                edge_res = await execute_job(edge_job.id, {
                    "user_id": str(user_id),
                    "scholarship_id": str(schol_id),
                    "research_facts": research_res["facts"],
                })
                angles = edge_res["angles"]
                assert len(angles) >= 1
                for ang in angles:
                    assert len(ang["supporting_profile_facts"]) > 0
                    assert ang["reasoning"]

                # C. Run Drafter Job
                drafter_job = await enqueue_job("drafter", {
                    "application_id": str(app_record.id),
                    "user_id": str(user_id),
                    "scholarship_id": str(schol_id),
                    "angles": angles,
                    "essay_prompt": schol.eligibility_rules.get("essay_prompt") or "Personal statement",
                    "word_limit": schol.eligibility_rules.get("essay_word_limit", 500),
                })
                drafter_res = await execute_job(drafter_job.id, {
                    "application_id": str(app_record.id),
                    "user_id": str(user_id),
                    "scholarship_id": str(schol_id),
                    "angles": angles,
                    "essay_prompt": schol.eligibility_rules.get("essay_prompt") or "Personal statement",
                    "word_limit": schol.eligibility_rules.get("essay_word_limit", 500),
                })

                # Assertions on Draft Output
                assert drafter_res["content"]
                assert drafter_res["word_count"] <= 500
                assert len(drafter_res["source_facts"]) > 0, "Draft must cite verified source facts"
                assert drafter_res["version"] >= 1

                # Verify saved in drafts table
                saved_draft = await session.get(Draft, uuid.UUID(drafter_res["draft_id"]))
                assert saved_draft is not None
                assert len(saved_draft.source_facts) > 0
                drafted_applications.append(saved_draft)

        # Confirm exactly 3 distinct scholarship applications were drafted
        assert len(drafted_applications) == 3

    asyncio.run(run())

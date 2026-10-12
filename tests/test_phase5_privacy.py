"""Acceptance tests for Phase 5: Autonomous Scheduler, Proactive Notifications & Privacy Compliance."""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, ApplicationEvent, Document, Match, Profile, Scholarship, User
from app.main import app
from app.services.scheduler import run_daily_discovery_and_matching, run_daily_scheduler_cycle
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


def test_timezone_aware_discovery_filtering():
    """Verifies that daily discovery strictly filters by target timezone."""
    async def run():
        async with AsyncSessionLocal() as session:
            # Create user in Lagos timezone
            u_lagos = User(email="lagos.user@example.com", status="active", timezone="Africa/Lagos")
            session.add(u_lagos)
            await session.commit()

            p_lagos = Profile(
                user_id=u_lagos.id,
                personal_details={"first_name": "Emeka", "citizenship": "Nigeria"},
                target_countries=["United Kingdom"],
                target_fields_of_study=["Engineering"],
                education_history=[{"degree": "B.Sc."}],
                grades={"gpa": 4.5},
            )
            session.add(p_lagos)

            # Create user in New York timezone
            u_ny = User(email="ny.user@example.com", status="active", timezone="America/New_York")
            session.add(u_ny)
            await session.commit()

            p_ny = Profile(
                user_id=u_ny.id,
                personal_details={"first_name": "John", "citizenship": "United States"},
                target_countries=["Canada"],
                target_fields_of_study=["Engineering"],
                education_history=[{"degree": "B.Sc."}],
                grades={"gpa": 3.8},
            )
            session.add(p_ny)
            await session.commit()

            # Run for Lagos timezone only
            res_lagos = await run_daily_discovery_and_matching(session, target_timezone="Africa/Lagos")
            assert res_lagos["users_processed"] == 1

            # Run for New York timezone only
            res_ny = await run_daily_discovery_and_matching(session, target_timezone="America/New_York")
            assert res_ny["users_processed"] == 1

            # Run with no timezone filter (all users)
            res_all = await run_daily_discovery_and_matching(session, target_timezone=None)
            assert res_all["users_processed"] == 2

    asyncio.run(run())


def test_telegram_chat_id_resolution_in_alerts(monkeypatch):
    """Verifies that proactive deadline alerts dispatch to user.telegram_chat_id."""
    sent_messages = []

    async def mock_send_telegram(chat_id: str, text: str):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"ok": True}

    monkeypatch.setattr("app.services.scheduler.send_telegram_message", mock_send_telegram)

    async def run():
        async with AsyncSessionLocal() as session:
            # Create user with specific telegram_chat_id
            user = User(
                email="telegram.student@example.com",
                status="active",
                telegram_chat_id="chat_987654321",
                timezone="Africa/Lagos",
            )
            session.add(user)
            await session.commit()

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Amina", "citizenship": "Nigeria"},
                target_countries=["United Kingdom"],
                target_fields_of_study=["Computer Science"],
                education_history=[{"degree": "B.Sc."}],
                grades={"gpa": 4.9},
            )
            session.add(profile)

            # Create upcoming scholarship within 3-day deadline
            now = datetime.now(timezone.utc)
            schol = (await session.execute(select(Scholarship))).scalars().first()
            schol.deadline = now + timedelta(days=2)
            session.add(schol)
            await session.commit()

            # Run daily scheduler cycle
            cycle_res = await run_daily_scheduler_cycle(session, reference_time=now, target_timezone="Africa/Lagos")

            assert cycle_res["notifications_dispatched"] >= 1
            assert len(sent_messages) >= 1
            assert sent_messages[0]["chat_id"] == "chat_987654321"
            assert user.id.hex not in sent_messages[0]["chat_id"]

    asyncio.run(run())


def test_document_ingestion_and_verification():
    """Metadata registration cannot assert factual verification."""
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            key_resp = await client.post("/v1/auth/keys", json={"email": "doc.student@example.com"})
            api_key = key_resp.json()["api_key"]
            headers = {"X-API-Key": api_key}

            # Create initial profile
            await client.put(
                "/v1/profile",
                headers=headers,
                json={
                    "personal_details": {"first_name": "Kemi"},
                    "education_history": [{"degree": "B.Sc."}],
                    "grades": {"gpa": 4.5},
                },
            )

            # Register a fictional managed file; no authenticity is inferred.
            profile_resp = await client.get("/v1/profile", headers=headers)
            document_path = Path("storage/documents") / profile_resp.json()["user_id"] / "transcript.pdf"
            document_path.parent.mkdir(parents=True, exist_ok=True)
            document_path.write_text("Fictional transcript test fixture")
            doc_resp = await client.post(
                "/v1/documents",
                headers=headers,
                json={"type": "transcript", "storage_key": str(document_path.resolve())},
            )
            assert doc_resp.status_code == 201
            doc_data = doc_resp.json()
            assert doc_data["verified"] is False

            # Verify list returns verified document
            list_resp = await client.get("/v1/documents", headers=headers)
            assert list_resp.status_code == 200
            assert list_resp.json()[0]["verified"] is False

    asyncio.run(run())


def test_export_and_gdpr_physical_file_erasure():
    """Verifies that data export includes matches and account deletion physically cleans files."""
    async def run():
        temp_doc = Path("storage/test_temp_doc.pdf")
        temp_ss = Path("storage/screenshots/test_temp_ss.png")
        temp_doc.parent.mkdir(parents=True, exist_ok=True)
        temp_ss.parent.mkdir(parents=True, exist_ok=True)
        temp_doc.write_text("sample document content")
        temp_ss.write_text("sample screenshot content")

        assert temp_doc.exists()
        assert temp_ss.exists()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            key_resp = await client.post("/v1/auth/keys", json={"email": "gdpr.physical@example.com"})
            api_key = key_resp.json()["api_key"]
            headers = {"X-API-Key": api_key}

            # Setup profile and trigger matching to get match rows
            await client.put(
                "/v1/profile",
                headers=headers,
                json={
                    "personal_details": {"first_name": "Tari", "nationalities": ["Nigeria"]},
                    "education_history": [{"degree": "B.Sc."}],
                    "grades": {"gpa": 4.8, "gpa_scale": 5.0},
                    "target_countries": ["United Kingdom"],
                },
            )
            await client.post("/v1/matches/refresh", headers=headers)

            # Move fixture inside the owner's managed storage before registration.
            profile_resp = await client.get("/v1/profile", headers=headers)
            owned_path = Path("storage/documents") / profile_resp.json()["user_id"] / "fixture.pdf"
            owned_path.parent.mkdir(parents=True, exist_ok=True)
            temp_doc.rename(owned_path)
            temp_doc = owned_path
            # Register document pointing to temp file
            await client.post(
                "/v1/documents",
                headers=headers,
                json={"type": "cv", "storage_key": str(temp_doc.resolve())},
            )

            # 1. Test Export includes matches
            export_resp = await client.get("/v1/account/export", headers=headers)
            assert export_resp.status_code == 200
            export_data = export_resp.json()
            assert "matches" in export_data
            assert len(export_data["matches"]) > 0
            assert "fit_score" in export_data["matches"][0]
            assert "documents" in export_data
            assert len(export_data["documents"]) == 1

            # 2. Test Account Deletion cleans matches and files
            del_resp = await client.delete("/v1/account", headers=headers)
            assert del_resp.status_code == 200
            assert del_resp.json()["success"] is True

            # Verify physical file on disk was removed
            assert not temp_doc.exists()

    asyncio.run(run())

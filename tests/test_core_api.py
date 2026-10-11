"""Acceptance and contract tests for Milestone 2: Core API."""
import asyncio
import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.db.base import Base, engine
from app.main import app
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


def test_developer_e2e_journey():
    """Full developer flow per Milestone 2 acceptance criteria:
    Create a key -> Fill a profile -> Fetch ranked matches.
    """
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Developer creates an API key
            key_resp = await client.post(
                "/v1/auth/keys",
                json={"email": "developer.tunde@example.com", "scopes": ["read", "write"]},
            )
            assert key_resp.status_code == 201
            key_data = key_resp.json()
            api_key = key_data["api_key"]
            key_id = key_data["id"]
            assert api_key.startswith("sp_live_")

            headers = {"X-API-Key": api_key}

            # 2. Verify unauthenticated call fails with consistent error payload
            unauth_resp = await client.get("/v1/profile")
            assert unauth_resp.status_code == 401
            unauth_err = unauth_resp.json()
            assert unauth_err["code"] == "AUTHENTICATION_REQUIRED"
            assert "request_id" in unauth_err

            # 3. Read initially empty profile
            prof_resp = await client.get("/v1/profile", headers=headers)
            assert prof_resp.status_code == 200
            assert prof_resp.json()["completeness_score"] == 0.0

            # 4. Fill and update Profile Vault
            profile_payload = {
                "personal_details": {
                    "first_name": "Tunde",
                    "last_name": "Adeleke",
                    "nationalities": ["Nigeria"],
                    "state_of_origin": "Oyo",
                },
                "education_history": [
                    {
                        "institution": "University of Ibadan",
                        "degree": "B.Sc. Computer Engineering",
                        "graduation_year": 2025,
                    }
                ],
                "grades": {"gpa": 4.82, "gpa_scale": 5.0},
                "test_scores": {"gre_quant": 168},
                "achievements": [
                    {"title": "Winner, National Robotics Competition", "year": 2024},
                    {"title": "Published paper in IEEE AI in Power Systems", "year": 2025},
                ],
                "financial_need_info": {"statement": "Self-funded undergraduate seeking international scholarship"},
                "target_countries": ["UK", "Canada"],
                "target_fields_of_study": ["artificial intelligence", "computer engineering"],
            }

            put_resp = await client.put("/v1/profile", headers=headers, json=profile_payload)
            assert put_resp.status_code == 200
            put_data = put_resp.json()
            assert put_data["completeness_score"] == 100.0
            assert put_data["grades"]["gpa"] == 4.82

            # 5. Upload document metadata
            doc_resp = await client.post(
                "/v1/documents",
                headers=headers,
                json={"type": "transcript", "storage_key": "s3://vault/tunde/transcript_official.pdf"},
            )
            assert doc_resp.status_code == 201
            assert doc_resp.json()["type"] == "transcript"

            docs_list = await client.get("/v1/documents", headers=headers)
            assert docs_list.status_code == 200
            assert len(docs_list.json()) == 1

            # 6. Discover scholarships with filters
            all_schol = await client.get("/v1/scholarships")
            assert all_schol.status_code == 200
            schol_data = all_schol.json()
            assert schol_data["total"] >= 3

            filtered_schol = await client.get("/v1/scholarships?country=UK&level=masters")
            assert filtered_schol.status_code == 200
            for item in filtered_schol.json()["items"]:
                assert item["country"].upper() == "UK"
                assert item["level"].lower() == "masters"

            # 7. Trigger matching run and fetch ranked matches
            refresh_resp = await client.post("/v1/matches/refresh", headers=headers)
            assert refresh_resp.status_code == 200
            matches = refresh_resp.json()
            assert len(matches) > 0

            top_match = matches[0]
            assert top_match["fit_score"] >= 70.0
            assert "reasons" in top_match
            assert len(top_match["reasons"]) >= 2
            assert any("Nigeria" in r for r in top_match["reasons"])

            # 8. Fetch stored matches via GET /v1/matches
            get_matches = await client.get("/v1/matches", headers=headers)
            assert get_matches.status_code == 200
            assert len(get_matches.json()) == len(matches)

            # 9. Revoke the API key and verify access is immediately blocked
            revoke_resp = await client.delete(f"/v1/auth/keys/{key_id}", headers=headers)
            assert revoke_resp.status_code == 200
            assert revoke_resp.json()["status"] == "revoked"

            blocked_resp = await client.get("/v1/profile", headers=headers)
            assert blocked_resp.status_code == 401
            assert blocked_resp.json()["code"] == "INVALID_API_KEY"

    asyncio.run(run())

"""Operator-only fictional cloud smoke test; this does NOT validate onboarding.

Run inside the private API container. All applicant content comes from the
repository's synthetic fixture. The test key stays in ignored host storage.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any
import httpx
from sqlalchemy import select
from app.core.security import generate_api_key
from app.db.base import AsyncSessionLocal
from app.db.models import ApiKey, User
from scripts.import_catalog import import_listings

PRIVATE = Path("storage/cloud_fixture/session.json")
SYNTHETIC = Path("backend/data/synthetic")


async def portal_receipt(application_id: str) -> dict[str, Any] | None:
    connection = sqlite3.connect("storage/portal/app.db")
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("SELECT draft_id FROM portal_drafts WHERE idempotency_key=?", (application_id,)).fetchone()
    finally:
        connection.close()
    if not row:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("http://127.0.0.1:8000/portal/api/submissions/" + row["draft_id"])
        response.raise_for_status()
        return response.json()


async def prepare_identity() -> str:
    if PRIVATE.is_file():
        return json.loads(PRIVATE.read_text())["api_key"]
    preferences = json.loads((SYNTHETIC / "preferences.json").read_text())
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == preferences["email"]))).scalar_one_or_none()
        if not user:
            user = User(email=preferences["email"], mode="autopilot", status="active")
            session.add(user)
            await session.flush()
        plain, hashed = generate_api_key()
        session.add(ApiKey(user_id=user.id, hashed_key=hashed, scopes=["read", "write"]))
        await session.commit()
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        PRIVATE.write_text(json.dumps({"api_key": plain, "user_id": str(user.id), "operator_fixture": True}))
        os.chmod(PRIVATE, 0o600)
        return plain


async def call(client: httpx.AsyncClient, method: str, path: str, payload: dict | None = None) -> Any:
    response = await client.request(method, "/v1" + path, json=payload)
    response.raise_for_status()
    return response.json()


async def prepare_profile(client: httpx.AsyncClient) -> None:
    preferences = json.loads((SYNTHETIC / "preferences.json").read_text())
    await call(client, "PUT", "/profile", {"personal_details": {"full_name": preferences["full_name"],
        "target_level": preferences["level"], "citizenship": preferences["nationality"]},
        "grades": {"gpa": preferences["gpa"], "gpa_scale": preferences["gpa_scale"]},
        "target_countries": preferences["countries"], "target_fields_of_study": preferences["fields"]})
    for kind, name in (("cv", "cv.txt"), ("transcript", "transcript.txt")):
        document = await call(client, "POST", "/documents/upload", {"type": kind, "filename": name,
            "content_base64": base64.b64encode((SYNTHETIC / name).read_bytes()).decode()})
        profile = await call(client, "GET", "/profile")
        facts = [{key: fact[key] for key in ("category", "text", "source_excerpt")}
            for fact in profile["personal_details"].get("_pending_facts", [])
            if fact["document_id"] == document["id"] and not fact["sensitive"]]
        await call(client, "POST", "/documents/" + document["id"] + "/verify", {"confirmed": True, "facts": facts})


async def start() -> dict[str, Any]:
    key = await prepare_identity()
    catalog = json.loads(Path("backend/data/listings.json").read_text())
    fixture_catalog = PRIVATE.parent / "catalog.json"
    fixture_catalog.write_text(json.dumps({"listings": [item for item in catalog["listings"]
        if item["is_mock"] and item["channel"] == "portal_form"]}))
    await import_listings(fixture_catalog)
    # Requests go through the real Next frontend proxy, not an ASGI test client.
    async with httpx.AsyncClient(base_url="http://127.0.0.1:3000", headers={"X-API-Key": key}, timeout=10) as client:
        await prepare_profile(client)
        run = await call(client, "POST", "/runs", {"mode": "B", "top_n": 1, "live_research": False, "tags": ["cloud_fictional_smoke"]})
    saved = json.loads(PRIVATE.read_text())
    saved["run_id"] = run["run_id"]
    PRIVATE.write_text(json.dumps(saved))
    return {"run_id": run["run_id"], "fictional": True, "operator_fixture": True, "onboarding_validated": False}


async def inspect() -> dict[str, Any]:
    saved = json.loads(PRIVATE.read_text())
    async with httpx.AsyncClient(base_url="http://127.0.0.1:3000", headers={"X-API-Key": saved["api_key"]}, timeout=10) as client:
        run = await call(client, "GET", "/runs/" + saved["run_id"])
        applications = await call(client, "GET", "/applications")
        details = []
        for application in applications:
            detail = await call(client, "GET", "/applications/" + application["id"])
            files = []
            for path in sorted((Path("storage/packages") / saved["user_id"] / application["id"]).glob("*")):
                if path.is_file():
                    files.append({"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
            details.append({"id": detail["id"], "status": detail["status"], "confirmation_ref": detail["confirmation_ref"],
                "verification": detail["verification"], "package_files": files, "trace_url": detail["trace_url"],
                "portal_receipt": await portal_receipt(detail["id"]) if detail["status"] == "submitted" else None})
    return {"fictional": True, "operator_fixture": True, "onboarding_validated": False,
        "run_status": run["status"], "applications": details}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "inspect"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(start() if args.action == "start" else inspect()), default=str))


if __name__ == "__main__":
    main()

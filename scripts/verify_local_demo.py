"""Collect real local integration evidence for the repository's fictional persona."""
import asyncio
import hashlib
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import asyncpg
import redis.asyncio as redis

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.local_demo import RUNTIME, configuration, environment


async def audit_guard_checks(connection: asyncpg.Connection, event_id: Any) -> dict[str, bool]:
    checks = {}
    for name, statement in (("update_denied", "UPDATE application_events SET event_type=event_type WHERE id=$1"),
        ("delete_denied", "DELETE FROM application_events WHERE id=$1")):
        transaction = connection.transaction()
        await transaction.start()
        try:
            await connection.execute(statement, event_id)
            checks[name] = False
        except asyncpg.RaiseError:
            checks[name] = True
        finally:
            await transaction.rollback()
    return checks


async def collect() -> dict[str, Any]:
    config = configuration()
    if config["database"] != "scholarpilot_demo" or config["pg_port"] != 55432 or config["redis_port"] != 16379:
        raise ValueError("Evidence collection is restricted to this isolated fictional runtime.")
    preferences = json.loads((ROOT / "backend/data/synthetic/preferences.json").read_text(encoding="utf-8"))
    pg = await asyncpg.connect(host="127.0.0.1", port=config["pg_port"], user="scholarpilot_admin",
        password=config["admin_password"], database=config["database"])
    client = redis.Redis(host="127.0.0.1", port=config["redis_port"], password=config["redis_password"], socket_timeout=2)
    try:
        owner = await pg.fetchval("SELECT id FROM users WHERE email=$1", preferences["email"])
        if owner is None:
            raise ValueError("The fictional applicant has not been created through the frontend.")
        rows = await pg.fetch("SELECT id,status,confirmation_ref,submitted_at FROM applications WHERE user_id=$1 ORDER BY created_at", owner)
        identifiers = [str(row["id"]) for row in rows]
        jobs = await pg.fetch("SELECT id,type,status,attempts FROM jobs WHERE payload->>'user_id'=$1 OR payload->>'application_id'=ANY($2::text[]) ORDER BY created_at", str(owner), identifiers)
        event = await pg.fetchval("SELECT id FROM application_events WHERE application_id=$1 LIMIT 1", rows[-1]["id"])
        guards = await audit_guard_checks(pg, event)
        profile = json.loads(await pg.fetchval("SELECT personal_details FROM profiles WHERE user_id=$1", owner))
        details = []
        connection = sqlite3.connect(RUNTIME / "portal.db")
        connection.row_factory = sqlite3.Row
        try:
            for row in rows:
                portal = connection.execute("SELECT draft_id,submitted,confirmation_code FROM portal_drafts WHERE idempotency_key=?", (str(row["id"]),)).fetchone()
                receipt = None
                if portal:
                    with urllib.request.urlopen("http://localhost:8000/portal/api/submissions/" + portal["draft_id"], timeout=10) as response:
                        receipt = json.load(response)
                directory = ROOT / "storage/packages" / str(owner) / str(row["id"])
                files = [{"name": path.name, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(directory.glob("*")) if path.is_file()]
                details.append({"id": str(row["id"]), "status": row["status"], "confirmation_ref": row["confirmation_ref"],
                    "submitted_at": row["submitted_at"].isoformat() if row["submitted_at"] else None,
                    "portal_receipt": receipt, "package_files": files})
        finally:
            connection.close()
        # Exercise the actual Redis lease Lua path in a separate local process.
        import os
        os.environ.update(environment())
        from app.core.runtime import submission_lease, assert_submission_lease
        from app.jobs.queue import close_redis_client
        lease_id = uuid4()
        async with submission_lease(lease_id):
            await assert_submission_lease()
            try:
                async with submission_lease(lease_id):
                    raise AssertionError("A competing lease was accepted.")
            except RuntimeError:
                lease_excluded = True
        lease_released = await client.get("scholarpilot:submission:" + str(lease_id)) is None
        await close_redis_client()
        return {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "fictional_fixture": preferences["full_name"],
            "postgresql_version": await pg.fetchval("SHOW server_version"), "redis_version": (await client.info("server"))["redis_version"],
            "migration": await pg.fetchval("SELECT version_num FROM alembic_version"), "audit_guards": guards,
            "reviewed_documents": await pg.fetchval("SELECT count(*) FROM documents WHERE user_id=$1 AND verified=true", owner),
            "reviewed_source_facts": len(profile.get("_verified_facts", [])), "redis_lease_excluded_competitor": lease_excluded,
            "redis_lease_released": lease_released, "jobs": [dict(row) for row in jobs], "applications": details,
            "llm_drafting_enabled": (ROOT / "storage/local_runtime/runtime_mode.txt").is_file() and (ROOT / "storage/local_runtime/runtime_mode.txt").read_text().strip() == "agent",
            "public_research_snapshot_count": await pg.fetchval("SELECT count(*) FROM jobs WHERE type='research_snapshot' AND payload->>'url' LIKE 'https://%'"),
            "scope": "Local fictional application integration and retained receipts. Public source observations and external notification delivery are reported separately; no real scholarship submission."}
    finally:
        await client.aclose()
        await pg.close()


if __name__ == "__main__":
    result = asyncio.run(collect())
    assert all(result["audit_guards"].values())
    assert result["redis_lease_excluded_competitor"] and result["redis_lease_released"]
    assert any(row["status"] == "submitted" and row["portal_receipt"].get("confirmation_code") == row["confirmation_ref"] for row in result["applications"])
    destination = ROOT / ("docs/evidence/agent_local_e2e_20261012.json" if result["llm_drafting_enabled"] else "docs/evidence/fictional_e2e_20261012.json")
    destination.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print("Verified real local integration; report:", destination)

"""Import scholarship catalog from JSON into the production PostgreSQL/SQLite database."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from sqlalchemy import select
from app.db.base import AsyncSessionLocal, engine, Base
from app.db.models import Scholarship


async def import_listings(json_path: Path) -> int:
    """Reads listings from JSON and inserts them into the scholarships table."""
    if not json_path.exists():
        raise FileNotFoundError(f"Listings file not found at: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    listings = data.get("listings", [])

    # Ensure tables exist (helpful for local dev or tests)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    imported_count = 0
    async with AsyncSessionLocal() as session:
        for item in listings:
            # Parse deadline string YYYY/MM/DD
            deadline_dt = None
            if item.get("deadline"):
                try:
                    deadline_dt = datetime.strptime(item["deadline"], "%Y/%m/%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            # Fields string representation
            fields_list = item.get("fields", [])
            primary_field = fields_list[0] if fields_list else "General"

            # Check if scholarship with same title & provider already exists
            stmt = select(Scholarship).where(
                Scholarship.title == item.get("name", "Untitled"),
                Scholarship.provider == item.get("provider", "Unknown"),
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

            eligibility = {
                "catalog_id": item.get("id"),
                "fields": fields_list,
                "min_gpa": item.get("min_gpa", 0.0),
                "gpa_scale": item.get("gpa_scale", 5.0),
                "eligible_nationalities": item.get("eligible_nationalities", []),
                "requires_sensitive": item.get("requires_sensitive", []),
                "criteria_text": item.get("criteria_text", ""),
                "essay_prompt": item.get("essay_prompt", ""),
                "essay_word_limit": item.get("essay_word_limit", 500),
                "channel": item.get("channel", "portal_form"),
                "is_mock": item.get("is_mock", False),
                "ai_policy": item.get("ai_policy", "unknown") if item.get("is_mock") else "unknown",
            }
            application_url = item.get("source_url") or "https://scholarpilot.demo"
            if item.get("is_mock") and item.get("portal_path"):
                origin = urlsplit(application_url)
                application_url = origin.scheme + "://" + origin.netloc + item["portal_path"]

            if existing:
                existing.country = item.get("country", "Unknown")
                existing.level = item.get("level", "masters")
                existing.field = primary_field
                existing.deadline = deadline_dt if item.get("is_mock") else existing.deadline if existing.last_verified_at else None
                existing.eligibility_rules = {**eligibility, **({k: v for k, v in existing.eligibility_rules.items() if k in {"_source_observation", "research_urls", "portal_url", "portal_policy", "ai_policy"}} if existing.last_verified_at else {})}
                existing.application_url = application_url
                existing.source = "listings.json"
                existing.status = "active" if item.get("is_mock") else existing.status if existing.last_verified_at else "unverified"
            else:
                scholarship = Scholarship(
                    title=item.get("name", "Untitled"),
                    provider=item.get("provider", "Unknown"),
                    country=item.get("country", "Unknown"),
                    level=item.get("level", "masters"),
                    field=primary_field,
                    amount=float(item.get("amount", 0.0)),
                    currency="USD",
                    deadline=deadline_dt if item.get("is_mock") else None,
                    eligibility_rules=eligibility,
                    application_url=application_url,
                    requires_essay=bool(item.get("essay_prompt")),
                    source="listings.json",
                    status="active" if item.get("is_mock") else "unverified",
                )
                session.add(scholarship)
                imported_count += 1

        await session.commit()

    return imported_count


async def main() -> None:
    catalog_path = root_dir / "backend" / "data" / "listings.json"
    print(f"Importing scholarship catalog from {catalog_path}...")
    count = await import_listings(catalog_path)
    print(f"Catalog import completed successfully. {count} new scholarships inserted.")


if __name__ == "__main__":
    asyncio.run(main())

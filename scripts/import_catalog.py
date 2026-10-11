"""Import scholarship catalog from JSON into the production PostgreSQL/SQLite database."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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
            }

            if existing:
                existing.country = item.get("country", "Unknown")
                existing.level = item.get("level", "masters")
                existing.field = primary_field
                existing.deadline = deadline_dt
                existing.eligibility_rules = eligibility
                existing.application_url = item.get("source_url") or "https://scholarpilot.demo"
                existing.source = "listings.json"
                existing.status = "active"
            else:
                scholarship = Scholarship(
                    title=item.get("name", "Untitled"),
                    provider=item.get("provider", "Unknown"),
                    country=item.get("country", "Unknown"),
                    level=item.get("level", "masters"),
                    field=primary_field,
                    amount=float(item.get("amount", 10000.0) if item.get("funding") == "full" else 5000.0),
                    currency="USD",
                    deadline=deadline_dt,
                    eligibility_rules=eligibility,
                    application_url=item.get("source_url") or "https://scholarpilot.demo",
                    requires_essay=bool(item.get("essay_prompt")),
                    source="listings.json",
                    status="active",
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

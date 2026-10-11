"""Scout agent: sources scholarship listings and filters by open deadline."""
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app import db
from app.models import Listing
from app.tracing import retriever_span, set_attrs


def get_listings_path() -> Path:
    """Resolves path to listings.json."""
    candidates = [
        Path("data/listings.json"),
        Path("backend/data/listings.json"),
        Path(__file__).resolve().parent.parent.parent / "data" / "listings.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[-1]


@retriever_span("scout")
def load_listings() -> list[Listing]:
    """Loads and validates all scholarship listings from listings.json."""
    path = get_listings_path()
    if not path.is_file():
        raise ValueError(f"listings.json not found at {path}")

    raw_text = path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    items = data.get("listings", [])

    listings: list[Listing] = []
    for item in items:
        try:
            listing = Listing.model_validate(item)
            listings.append(listing)
        except Exception as e:
            item_id = item.get("id", "unknown") if isinstance(item, dict) else "unknown"
            raise ValueError(f"Invalid listing entry {item_id}: {e}") from e

    return listings


def filter_open(
    listings: list[Listing], today: date | None = None
) -> tuple[list[Listing], list[Listing]]:
    """Partitions listings into open and expired based on today's date."""
    if today is None:
        today = db.today_date()

    open_listings: list[Listing] = []
    expired_listings: list[Listing] = []

    for listing in listings:
        try:
            deadline_date = datetime.strptime(listing.deadline, "%Y/%m/%d").date()
        except ValueError:
            # If invalid date format, treat as expired
            expired_listings.append(listing)
            continue

        if deadline_date >= today:
            open_listings.append(listing)
        else:
            expired_listings.append(listing)

    return open_listings, expired_listings

"""Tests for Scout listing loader and deadline filter (Task B08)."""
from datetime import date
import pytest

from app.agents.scout import filter_open, load_listings
from app.models import Listing


def test_scout_load_listings():
    listings = load_listings()
    assert len(listings) >= 5
    assert all(isinstance(l, Listing) for l in listings)


def test_filter_open_partitions_by_deadline():
    listings = load_listings()

    # If today is 2026/10/10, listings with deadlines after today are open
    open_l, expired_l = filter_open(listings, today=date(2026, 10, 10))
    assert len(open_l) >= 5
    assert len(expired_l) == 0

    # If today is 2026/11/25:
    # Nov 03 and Nov 20 deadlines are expired; Dec 01, Dec 10, Dec 15 are open
    open_l2, expired_l2 = filter_open(listings, today=date(2026, 11, 25))
    assert len(open_l2) >= 3
    assert len(expired_l2) >= 2
    expired_ids = {l.id for l in expired_l2}
    assert "real_one" in expired_ids  # Nov 03
    assert "mock_captcha_award" in expired_ids  # Nov 20

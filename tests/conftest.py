"""Global pytest configuration and fixtures for ScholarPilot tests."""
import os
import pytest

# Ensure tests default to in-memory sqlite if DATABASE_URL is not explicitly pointing to test postgres
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

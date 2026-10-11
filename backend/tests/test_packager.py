"""Unit tests for the Packager agent."""
from pathlib import Path
import pytest

from app.agents import packager
from app import db
from app.errors import RunContext
from app.models import Listing, Preferences, TailoredOutput, Segment


@pytest.fixture
def sample_listing():
    return Listing(
        id="mock_portal_masters",
        name="Aurora Energy AI Scholarship",
        is_mock=True,
        provider="Aurora Tech",
        country="UK",
        level="masters",
        fields=["artificial intelligence", "energy"],
        min_gpa=3.5,
        gpa_scale=5.0,
        eligible_nationalities=[],
        deadline="2026/12/01",
        deadline_note="Open",
        funding="full",
        channel="portal_form",
        ai_policy="allowed",
        source_url="http://localhost:8000/portal/about/mock_portal_masters",
        criteria_text="Strong academic background in engineering.",
        essay_prompt="Why energy AI?",
        essay_word_limit=300,
        required_documents=["cv", "essay"],
    )


@pytest.fixture
def sample_prefs():
    return Preferences(
        full_name="Adebayo Nnamdi",
        email="adebayo.nnamdi@example.com",
        gpa=4.5,
        gpa_scale=5.0,
        level="masters",
        fields=["computer engineering"],
    )


def test_build_package_full_mode(sample_listing, sample_prefs):
    db.init_db()
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, sample_listing.id, sample_listing.channel)

    tailored = TailoredOutput(
        cv_summary=[
            Segment(text="First class graduate in computer engineering.", source_ids=["C1"], status="supported"),
            Segment(text="Hallucinated founder of international NGO.", source_ids=[], status="removed"),
        ],
        cv_bullets=[
            Segment(text="Led final year solar energy forecasting project.", source_ids=["P1"], status="supported"),
            Segment(text="Fabricated 10 years experience.", source_ids=[], status="removed"),
        ],
        essay=[
            Segment(text="I am driven to advance clean energy technologies.", source_ids=["C1"], status="supported"),
            Segment(text="Fake publication in Nature Energy.", source_ids=[], status="removed"),
        ],
        mode="full",
        outline=[],
    )

    ctx = RunContext(run_id=run_id, app_id=app_id)
    pkg = packager.build_package(app_id, sample_listing, sample_prefs, tailored, ctx)

    assert "cv_pdf" in pkg
    assert "essay_txt" in pkg
    assert "checklist_txt" in pkg

    # Check files exist on disk
    backend_dir = Path(__file__).resolve().parent.parent
    pkg_dir = backend_dir / "data" / "packages" / app_id

    cv_path = pkg_dir / "cv.pdf"
    essay_path = pkg_dir / "essay.txt"
    checklist_path = pkg_dir / "checklist.txt"

    assert cv_path.is_file()
    assert essay_path.is_file()
    assert checklist_path.is_file()

    # Check PDF content starts with %PDF header
    cv_bytes = cv_path.read_bytes()
    assert cv_bytes.startswith(b"%PDF")

    # Check essay content: only supported segments included, removed excluded
    essay_text = essay_path.read_text(encoding="utf-8")
    assert "I am driven to advance clean energy technologies." in essay_text
    assert "Fake publication in Nature Energy" not in essay_text

    # Check checklist content
    checklist_text = checklist_path.read_text(encoding="utf-8")
    assert "Aurora Energy AI Scholarship" in checklist_text
    assert "2026/12/01" in checklist_text
    assert "ALLOWED" in checklist_text
    assert "[ ] CV" in checklist_text
    assert "[ ] ESSAY" in checklist_text


def test_build_package_notes_only_mode(sample_listing, sample_prefs):
    db.init_db()
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, sample_listing.id, sample_listing.channel)

    outline_notes = [
        "1. Academic Foundations: Highlight 4.5 GPA and thesis (facts: C1)",
        "2. Community Impact: Mention solar workshop mentoring (facts: P1)",
    ]

    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[
            Segment(text="First class graduate.", source_ids=["C1"], status="supported"),
        ],
        essay=[],
        mode="notes_only",
        outline=outline_notes,
    )

    ctx = RunContext(run_id=run_id, app_id=app_id)
    pkg = packager.build_package(app_id, sample_listing, sample_prefs, tailored, ctx)

    backend_dir = Path(__file__).resolve().parent.parent
    essay_path = backend_dir / "data" / "packages" / app_id / "essay.txt"
    essay_text = essay_path.read_text(encoding="utf-8")

    assert "Academic Foundations" in essay_text
    assert "Community Impact" in essay_text

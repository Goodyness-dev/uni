import os
import tempfile
import pytest

from app import db


@pytest.fixture(autouse=True)
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    os.environ["TEST_DB_PATH"] = temp_path
    db.init_db()
    yield
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.environ.pop("TEST_DB_PATH", None)


def test_init_db_twice():
    db.init_db()
    db.init_db()


def test_status_transitions():
    run_id = db.create_run(mode="B", top_n=2)
    app_id = db.create_application(run_id=run_id, listing_id="mock_portal_masters", channel="portal_captcha")

    # Initial status is found
    app = db.get_application(app_id)
    assert app["status"] == "found"

    # Legal: found -> matched
    db.set_status(app_id, "matched", "Matched rules")
    assert db.get_application(app_id)["status"] == "matched"

    # Legal: matched -> researched
    db.set_status(app_id, "researched", "Research built")
    assert db.get_application(app_id)["status"] == "researched"

    # Illegal: researched -> submitted (must go through edges, tailored, etc.)
    with pytest.raises(ValueError):
        db.set_status(app_id, "submitted", "Direct submit invalid")

    # Legal: any status to failed
    db.set_status(app_id, "failed", "Fatal error occurred")
    assert db.get_application(app_id)["status"] == "failed"


def test_vault_fact_id_increment():
    f1 = db.add_vault_fact("sports", "Plays soccer")
    f2 = db.add_vault_fact("leadership", "Team captain")
    assert f1["id"] == "P1"
    assert f2["id"] == "P2"


def test_consume_flag_counted_and_uncounted():
    # Counted flag
    db.set_flag("llm_429", enabled=True, count=2)
    assert db.consume_flag("llm_429") is True
    flags = db.get_flags()
    assert flags["flags"]["llm_429"] is True
    assert flags["remaining"]["llm_429"] == 1

    assert db.consume_flag("llm_429") is True
    flags = db.get_flags()
    assert flags["flags"]["llm_429"] is False
    assert flags["remaining"]["llm_429"] == 0

    assert db.consume_flag("llm_429") is False

    # Uncounted flag (stays enabled)
    db.set_flag("captcha_wall", enabled=True)
    assert db.consume_flag("captcha_wall") is True
    assert db.consume_flag("captcha_wall") is True
    assert db.get_flags()["flags"]["captcha_wall"] is True


def test_replace_and_list_facts():
    facts = [
        {"id": "C1", "source": "cv", "category": "work", "text": "Software intern", "sensitive": False},
        {"id": "T1", "source": "transcript", "category": "grades", "text": "GPA 4.8", "sensitive": False},
    ]
    db.replace_facts(facts)
    loaded = db.list_facts()
    assert len(loaded) == 2
    assert loaded[0]["id"] == "C1"
    assert loaded[1]["id"] == "T1"

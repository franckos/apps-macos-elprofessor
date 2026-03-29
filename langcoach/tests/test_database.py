# langcoach/tests/test_database.py
import pytest
from pathlib import Path
from core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_create_and_get_profile(db):
    profile = db.create_profile("Franck", "🧑", {"target_language": "english", "level": "B1"})
    assert profile["name"] == "Franck"
    assert profile["avatar"] == "🧑"
    assert profile["settings"]["level"] == "B1"
    fetched = db.get_profile(profile["id"])
    assert fetched["name"] == "Franck"


def test_list_profiles(db):
    db.create_profile("Franck", "🧑", {})
    db.create_profile("Sophie", "👩", {})
    profiles = db.list_profiles()
    assert len(profiles) == 2
    assert {p["name"] for p in profiles} == {"Franck", "Sophie"}


def test_update_profile_settings(db):
    profile = db.create_profile("Franck", "🧑", {"level": "B1"})
    db.update_profile_settings(profile["id"], {"level": "B2", "target_language": "spanish"})
    fetched = db.get_profile(profile["id"])
    assert fetched["settings"]["level"] == "B2"
    assert fetched["settings"]["target_language"] == "spanish"


def test_open_close_and_get_session(db):
    profile = db.create_profile("Franck", "🧑", {})
    session_id = db.open_session(profile["id"], "english", "B1", "Travel")
    assert session_id
    db.close_session(session_id, quality_score=0.75, summary="Good session.")
    session = db.get_session(session_id)
    assert session["quality_score"] == pytest.approx(0.75)
    assert session["summary"] == "Good session."
    assert session["ended_at"] is not None


def test_record_exchange_and_errors(db):
    profile = db.create_profile("Franck", "🧑", {})
    session_id = db.open_session(profile["id"], "english", "B1", "Travel")
    exchange_id = db.record_exchange(session_id, "I go yesterday", "I went yesterday.", 1, 1200)
    assert exchange_id
    errors = [{"error_type": "tense", "original": "I go", "corrected": "I went", "rule": "simple past"}]
    db.record_errors(exchange_id, session_id, profile["id"], errors, "english", "B1")
    breakdown = db.get_error_breakdown(profile["id"])
    assert len(breakdown) == 1
    assert breakdown[0]["error_type"] == "tense"
    assert breakdown[0]["count"] == 1


def test_error_patterns_aggregated(db):
    profile = db.create_profile("Franck", "🧑", {})
    session_id = db.open_session(profile["id"], "english", "B1", "Travel")
    error = [{"error_type": "tense", "original": "x", "corrected": "y", "rule": "simple past"}]
    for _ in range(3):
        ex_id = db.record_exchange(session_id, "msg", "resp", 1, 100)
        db.record_errors(ex_id, session_id, profile["id"], error, "english", "B1")
    patterns = db.get_top_patterns(profile["id"])
    assert patterns[0]["rule"] == "simple past"
    assert patterns[0]["occurrence_count"] == 3


def test_get_kpis_empty(db):
    profile = db.create_profile("Franck", "🧑", {})
    kpis = db.get_kpis(profile["id"])
    assert kpis["total_sessions"] == 0
    assert kpis["streak_days"] == 0


def test_session_exchange_count_incremented(db):
    profile = db.create_profile("Franck", "🧑", {})
    session_id = db.open_session(profile["id"], "english", "B1", "Travel")
    db.record_exchange(session_id, "Hello", "Hi!", 0, 400)
    db.record_exchange(session_id, "How are you?", "Fine!", 0, 350)
    session = db.get_session(session_id)
    assert session["exchange_count"] == 2

# langcoach/tests/test_stats_engine.py
import pytest
from pathlib import Path
from core.database import Database
from core.stats_engine import StatsEngine


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def profile(db):
    return db.create_profile("Franck", "🧑", {
        "target_language": "english", "level": "B1", "topic": "Travel"
    })


def test_parse_errors_single():
    errors = StatsEngine.parse_errors(
        '[tense: "I go yesterday" → "I went yesterday" | simple past irregular]'
    )
    assert len(errors) == 1
    assert errors[0]["error_type"] == "tense"
    assert errors[0]["original"] == "I go yesterday"
    assert errors[0]["corrected"] == "I went yesterday"
    assert errors[0]["rule"] == "simple past irregular"


def test_parse_errors_multiple():
    text = (
        'Good try! [grammar: "I am boring" → "I am bored" | adjective vs participle] '
        'Also [vocabulary: "I am angry on him" → "I am angry with him" | preposition after angry]'
    )
    errors = StatsEngine.parse_errors(text)
    assert len(errors) == 2
    assert errors[0]["error_type"] == "grammar"
    assert errors[1]["error_type"] == "vocabulary"


def test_parse_errors_none():
    assert StatsEngine.parse_errors("Great job! Keep it up.") == []


def test_parse_errors_malformed_no_crash():
    # Missing closing bracket — must not crash
    result = StatsEngine.parse_errors('[tense: "I go" → "I went" | rule without close')
    assert isinstance(result, list)


def test_record_exchange_persists(db, profile):
    engine = StatsEngine(db, llm=None)
    engine.start_session(profile, language="english", level="B1", topic="Travel")
    engine.record_exchange(
        user_text="I go yesterday to the park.",
        ai_response='[tense: "I go yesterday" → "I went yesterday" | simple past] Nice story!',
        duration_ms=800,
    )
    assert engine.exchange_count == 1
    assert engine.error_count == 1
    session = db.get_session(engine.session_id)
    assert session["exchange_count"] == 1
    assert session["error_count"] == 1


def test_end_session_closes_db_record(db, profile):
    engine = StatsEngine(db, llm=None)
    engine.start_session(profile, language="english", level="B1", topic="Travel")
    engine.record_exchange("Hello", "Hi!", 500)
    engine.record_exchange("How are you?", "Fine!", 400)
    session_id = engine.session_id
    engine.end_session()
    assert engine.session_id is None
    session = db.get_session(session_id)
    assert session["ended_at"] is not None


def test_get_lesson_cards_threshold(db, profile):
    engine = StatsEngine(db, llm=None)
    sid = db.open_session(profile["id"], "english", "B1", "Travel")
    error = [{"error_type": "tense", "original": "x", "corrected": "y", "rule": "simple past"}]
    for _ in range(6):
        eid = db.record_exchange(sid, "msg", "resp", 1, 100)
        db.record_errors(eid, sid, profile["id"], error, "english", "B1")
    cards = engine.get_lesson_cards(profile["id"], threshold=5)
    assert len(cards) >= 1
    assert cards[0]["pattern"]["rule"] == "simple past"

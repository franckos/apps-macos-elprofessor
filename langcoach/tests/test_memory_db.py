# langcoach/tests/test_memory_db.py
import json
import pytest
from pathlib import Path
from core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def profile(db):
    return db.create_profile("Franck", "🧑", {})


@pytest.fixture
def session(db, profile):
    sid = db.open_session(profile["id"], "english", "B1", "Travel")
    return sid


def test_create_memory(db, profile):
    m = db.create_memory(profile["id"], "Travaille chez une startup", ["pro", "travail"])
    assert m["id"]
    assert m["content"] == "Travaille chez une startup"
    assert m["tags"] == ["pro", "travail"]
    assert m["source"] == "manual"
    assert m["weight"] == 1.0


def test_list_memories(db, profile):
    db.create_memory(profile["id"], "Mémoire 1", ["perso"])
    db.create_memory(profile["id"], "Mémoire 2", ["pro"])
    memories = db.list_memories(profile["id"])
    assert len(memories) == 2


def test_list_memories_empty_other_profile(db, profile):
    other = db.create_profile("Sophie", "👩", {})
    db.create_memory(profile["id"], "Mémoire Franck", ["perso"])
    assert db.list_memories(other["id"]) == []


def test_delete_memory(db, profile):
    m = db.create_memory(profile["id"], "À supprimer", ["perso"])
    db.delete_memory(m["id"])
    assert db.list_memories(profile["id"]) == []


def test_update_memory(db, profile):
    m = db.create_memory(profile["id"], "Ancien contenu", ["perso"])
    db.update_memory(m["id"], content="Nouveau contenu", tags=["pro"])
    memories = db.list_memories(profile["id"])
    assert memories[0]["content"] == "Nouveau contenu"
    assert memories[0]["tags"] == ["pro"]


def test_update_memory_last_used(db, profile):
    m = db.create_memory(profile["id"], "Content", ["perso"])
    assert m["last_used"] is None
    db.update_memory_last_used(m["id"])
    memories = db.list_memories(profile["id"])
    assert memories[0]["last_used"] is not None


def test_update_memory_weight(db, profile):
    m = db.create_memory(profile["id"], "Content", ["perso"])
    db.update_memory_weight(m["id"], increment=0.1)
    memories = db.list_memories(profile["id"])
    assert abs(memories[0]["weight"] - 1.1) < 0.001


def test_create_memory_suggestion(db, profile, session):
    s = db.create_memory_suggestion(profile["id"], session, "Prépare un entretien", ["pro", "objectifs"])
    assert s["id"]
    assert s["content"] == "Prépare un entretien"


def test_list_memory_suggestions(db, profile, session):
    db.create_memory_suggestion(profile["id"], session, "Suggestion 1", ["pro"])
    db.create_memory_suggestion(profile["id"], session, "Suggestion 2", ["perso"])
    suggestions = db.list_memory_suggestions(profile["id"])
    assert len(suggestions) == 2


def test_delete_memory_suggestion(db, profile, session):
    s = db.create_memory_suggestion(profile["id"], session, "À supprimer", ["perso"])
    db.delete_memory_suggestion(s["id"])
    assert db.list_memory_suggestions(profile["id"]) == []


def test_accept_memory_suggestion(db, profile, session):
    s = db.create_memory_suggestion(profile["id"], session, "Fait accepté", ["pro"])
    m = db.accept_memory_suggestion(s["id"])
    assert m["content"] == "Fait accepté"
    assert m["source"] == "ai"
    assert db.list_memory_suggestions(profile["id"]) == []
    assert len(db.list_memories(profile["id"])) == 1


def test_delete_profile_cascades_memories(db, profile):
    db.create_memory(profile["id"], "Mémoire", ["perso"])
    db.delete_profile(profile["id"])
    # Profile gone — memory should be cascade-deleted
    # list_memories by that profile_id should return 0 rows
    assert db.list_memories(profile["id"]) == []

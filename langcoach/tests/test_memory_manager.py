# langcoach/tests/test_memory_manager.py
import json
import pytest
from pathlib import Path
from core.database import Database
from core.memory_manager import MemoryManager


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def profile(db):
    return db.create_profile("Franck", "🧑", {})


@pytest.fixture
def mm(db):
    return MemoryManager(db, llm=None)


def test_get_context_memories_empty(mm, profile):
    result = mm.get_context_memories(profile["id"])
    assert result == []


def test_get_context_memories_excludes_confidentiel(mm, db, profile):
    db.create_memory(profile["id"], "Secret médical", ["santé", "confidentiel"])
    result = mm.get_context_memories(profile["id"])
    assert result == []


def test_get_context_memories_includes_important_first(mm, db, profile):
    db.create_memory(profile["id"], "Fait normal", ["pro"])
    db.create_memory(profile["id"], "Fait important", ["pro", "important"])
    result = mm.get_context_memories(profile["id"])
    assert result[0]["content"] == "Fait important"


def test_get_context_memories_max_5_important(mm, db, profile):
    for i in range(7):
        db.create_memory(profile["id"], f"Important {i}", ["perso", "important"])
    result = mm.get_context_memories(profile["id"])
    important = [m for m in result if "important" in m["tags"]]
    assert len(important) == 5


def test_format_memory_block_empty(mm):
    assert mm.format_memory_block([]) == ""


def test_format_memory_block(mm, db, profile):
    memories = [
        {"id": "1", "content": "Travaille chez une startup", "tags": ["pro"], "weight": 1.0, "last_used": None},
    ]
    block = mm.format_memory_block(memories)
    assert "## Ce que tu sais sur ton élève" in block
    assert "[pro] Travaille chez une startup" in block


def test_get_topic_suggestions_empty(mm, profile):
    result = mm.get_topic_suggestions(profile["id"], [])
    assert result == []


def test_get_topic_suggestions_from_objectifs(mm, db, profile):
    db.create_memory(profile["id"], "Prépare un entretien chez Google", ["objectifs", "pro"])
    result = mm.get_topic_suggestions(profile["id"], [])
    assert len(result) >= 1
    assert any("Google" in s or "entretien" in s.lower() for s in result)


def test_parse_suggestions_valid_json(mm):
    text = '[{"content": "Prépare un entretien", "tags": ["pro", "objectifs"]}]'
    result = mm._parse_suggestions(text)
    assert len(result) == 1
    assert result[0]["content"] == "Prépare un entretien"


def test_parse_suggestions_empty_array(mm):
    assert mm._parse_suggestions("[]") == []


def test_parse_suggestions_invalid_json(mm):
    assert mm._parse_suggestions("not json") == []


def test_parse_suggestions_extracts_from_noisy_text(mm):
    text = 'Voici les mémoires:\n[{"content": "Fait 1", "tags": ["pro"]}]\nMerci.'
    result = mm._parse_suggestions(text)
    assert len(result) == 1

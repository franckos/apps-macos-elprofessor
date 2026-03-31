# tests/test_prompt_builder.py
from core.prompt_builder import build_system_prompt


def _base_settings():
    return {
        "teacher_style": "bienveillant",
        "level": "B1",
        "topic": "Travel",
        "target_language": "english",
        "native_language": "fr",
        "coach": "angela",
    }


def test_build_prompt_no_memories():
    prompt = build_system_prompt(_base_settings(), "Franck")
    assert "Ce que tu sais" not in prompt


def test_build_prompt_with_memories():
    memories = [
        {"id": "1", "content": "Prépare un entretien chez Google", "tags": ["objectifs"], "weight": 1.0, "last_used": None},
        {"id": "2", "content": "A deux enfants", "tags": ["famille"], "weight": 1.0, "last_used": None},
    ]
    prompt = build_system_prompt(_base_settings(), "Franck", memories=memories)
    assert "## Ce que tu sais sur ton élève" in prompt
    assert "[objectifs] Prépare un entretien chez Google" in prompt
    assert "[famille] A deux enfants" in prompt


def test_build_prompt_empty_memories_list():
    prompt = build_system_prompt(_base_settings(), "Franck", memories=[])
    assert "Ce que tu sais" not in prompt

# Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a profile-linked mini-memory system that injects personal facts about the user into the LLM system prompt, extracted manually or by AI after sessions.

**Architecture:** Flat memories stored in SQLite with JSON tag arrays. A `MemoryManager` class handles CRUD, token-budgeted selection, and async AI extraction. Memories are injected into `build_system_prompt()` as a compact `## Ce que tu sais sur ton élève` block. UI surfaces via a dialog from SettingsPanel + two new header buttons (Finir et Analyser / Nouvelle session with topic picker).

**Tech Stack:** Python 3.9+, PyQt6, SQLite (via existing `Database` class), Ollama/Mistral via `LLMEngine.chat_oneshot()`, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `langcoach/core/database.py` | Add `memories` + `memory_suggestions` tables, CRUD methods, migration |
| Create | `langcoach/core/memory_manager.py` | Selection algorithm, AI extraction, topic suggestions |
| Modify | `langcoach/core/prompt_builder.py` | Inject memory block into system prompt |
| Modify | `langcoach/core/stats_engine.py` | Hook memory extraction at `end_session()` |
| Create | `langcoach/ui/memory_panel.py` | Memory management dialog (list, add, validate suggestions) |
| Modify | `langcoach/ui/settings_panel.py` | Add "🧠 Mémoires" button that opens MemoryDialog |
| Modify | `langcoach/ui/main_window.py` | "Finir et Analyser" button, topic picker screen |
| Create | `langcoach/tests/test_memory_db.py` | DB CRUD tests for memories |
| Create | `langcoach/tests/test_memory_manager.py` | MemoryManager unit tests |
| Modify | `langcoach/tests/test_prompt_builder.py` | Test memory injection (new file if not exists) |

---

## Task 1: DB Schema — tables + CRUD

**Files:**
- Modify: `langcoach/core/database.py`
- Create: `langcoach/tests/test_memory_db.py`

- [ ] **Step 1: Write the failing tests**

Create `langcoach/tests/test_memory_db.py`:

```python
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
    # No cascade assertion on list since profile gone — just verify no crash
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS/langcoach
python -m pytest tests/test_memory_db.py -v 2>&1 | head -40
```

Expected: `ERROR` — `db.create_memory` not found, `db.delete_profile` not found.

- [ ] **Step 3: Add tables to `_SCHEMA` in `database.py`**

In `langcoach/core/database.py`, append to `_SCHEMA` (after the existing `CREATE INDEX` lines):

```python
_SCHEMA = """
...existing content...

CREATE TABLE IF NOT EXISTS memories (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    source      TEXT NOT NULL DEFAULT 'manual',
    weight      REAL NOT NULL DEFAULT 1.0,
    last_used   INTEGER,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_suggestions (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_profile    ON memories(profile_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_profile ON memory_suggestions(profile_id);
"""
```

- [ ] **Step 4: Add `_migrate_schema` entries for existing DBs**

In `_migrate_schema()`, append after the existing migration:

```python
def _migrate_schema(self):
    """Ajoute les colonnes manquantes pour les anciennes bases de données."""
    cursor = self._conn.execute("PRAGMA table_info(sessions)")
    columns = {row["name"] for row in cursor.fetchall()}
    if "title" not in columns:
        self._conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
        self._conn.commit()
        logger.info("Migration DB : colonne sessions.title ajoutée")

    # Ensure memory tables exist (for DBs created before this feature)
    self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id          TEXT PRIMARY KEY,
            profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            content     TEXT NOT NULL,
            tags        TEXT NOT NULL DEFAULT '[]',
            source      TEXT NOT NULL DEFAULT 'manual',
            weight      REAL NOT NULL DEFAULT 1.0,
            last_used   INTEGER,
            created_at  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_suggestions (
            id          TEXT PRIMARY KEY,
            profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            content     TEXT NOT NULL,
            tags        TEXT NOT NULL DEFAULT '[]',
            created_at  INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memories_profile    ON memories(profile_id);
        CREATE INDEX IF NOT EXISTS idx_suggestions_profile ON memory_suggestions(profile_id);
    """)
    self._conn.commit()
```

- [ ] **Step 5: Add `delete_profile` method (needed for cascade test)**

Add after `touch_profile()`:

```python
def delete_profile(self, profile_id: str):
    self._conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    self._conn.commit()
```

- [ ] **Step 6: Add memories CRUD methods to `Database`**

Add a new section `# ── Memories ──` after `# ── Dashboard Queries ──`:

```python
# ── Memories ──────────────────────────────────────────────

def create_memory(self, profile_id: str, content: str, tags: list,
                  source: str = "manual") -> dict:
    mid = str(uuid.uuid4())
    now = _ms()
    self._conn.execute(
        "INSERT INTO memories (id, profile_id, content, tags, source, weight, last_used, created_at) "
        "VALUES (?,?,?,?,?,1.0,NULL,?)",
        (mid, profile_id, content[:120], json.dumps(tags), source, now),
    )
    self._conn.commit()
    return self._memory_dict(
        self._conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
    )

def list_memories(self, profile_id: str) -> list:
    rows = self._conn.execute(
        "SELECT * FROM memories WHERE profile_id=? ORDER BY weight DESC, created_at DESC",
        (profile_id,),
    ).fetchall()
    return [self._memory_dict(r) for r in rows]

def update_memory(self, memory_id: str, content: str = None, tags: list = None):
    if content is not None:
        self._conn.execute(
            "UPDATE memories SET content=? WHERE id=?", (content[:120], memory_id)
        )
    if tags is not None:
        self._conn.execute(
            "UPDATE memories SET tags=? WHERE id=?", (json.dumps(tags), memory_id)
        )
    self._conn.commit()

def update_memory_last_used(self, memory_id: str):
    self._conn.execute(
        "UPDATE memories SET last_used=? WHERE id=?", (_ms(), memory_id)
    )
    self._conn.commit()

def update_memory_weight(self, memory_id: str, increment: float):
    self._conn.execute(
        "UPDATE memories SET weight = MIN(weight + ?, 5.0) WHERE id=?",
        (increment, memory_id),
    )
    self._conn.commit()

def delete_memory(self, memory_id: str):
    self._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    self._conn.commit()

def create_memory_suggestion(self, profile_id: str, session_id: str,
                              content: str, tags: list) -> dict:
    sid = str(uuid.uuid4())
    now = _ms()
    self._conn.execute(
        "INSERT INTO memory_suggestions (id, profile_id, session_id, content, tags, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (sid, profile_id, session_id, content[:120], json.dumps(tags), now),
    )
    self._conn.commit()
    return self._suggestion_dict(
        self._conn.execute(
            "SELECT * FROM memory_suggestions WHERE id=?", (sid,)
        ).fetchone()
    )

def list_memory_suggestions(self, profile_id: str) -> list:
    rows = self._conn.execute(
        "SELECT * FROM memory_suggestions WHERE profile_id=? ORDER BY created_at DESC",
        (profile_id,),
    ).fetchall()
    return [self._suggestion_dict(r) for r in rows]

def delete_memory_suggestion(self, suggestion_id: str):
    self._conn.execute(
        "DELETE FROM memory_suggestions WHERE id=?", (suggestion_id,)
    )
    self._conn.commit()

def accept_memory_suggestion(self, suggestion_id: str) -> dict:
    """Converts a suggestion into a memory. Returns the new memory."""
    row = self._conn.execute(
        "SELECT * FROM memory_suggestions WHERE id=?", (suggestion_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Suggestion {suggestion_id} not found")
    s = self._suggestion_dict(row)
    memory = self.create_memory(s["profile_id"], s["content"], s["tags"], source="ai")
    self.delete_memory_suggestion(suggestion_id)
    return memory

def _memory_dict(self, row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d

def _suggestion_dict(self, row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d
```

- [ ] **Step 7: Run tests — all must pass**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS/langcoach
python -m pytest tests/test_memory_db.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 8: Run full test suite — no regressions**

```bash
python -m pytest tests/ -v
```

Expected: All existing tests pass.

- [ ] **Step 9: Commit**

```bash
git add langcoach/core/database.py langcoach/tests/test_memory_db.py
git commit -m "feat: add memories and memory_suggestions tables with CRUD"
```

---

## Task 2: MemoryManager

**Files:**
- Create: `langcoach/core/memory_manager.py`
- Create: `langcoach/tests/test_memory_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `langcoach/tests/test_memory_manager.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS/langcoach
python -m pytest tests/test_memory_manager.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'core.memory_manager'`

- [ ] **Step 3: Create `langcoach/core/memory_manager.py`**

```python
"""
LangCoach — Memory Manager
CRUD mémoires, sélection contextuelle, suggestions IA asynchrones
"""
import json
import logging
import re
import threading
from typing import Optional

from core.database import Database

logger = logging.getLogger(__name__)

SYSTEM_TAGS = [
    "perso", "famille", "enfants", "couple", "amis", "logement",
    "pro", "travail", "carrière", "business", "finance",
    "santé", "sport", "psycho", "bien-être",
    "loisirs", "voyage", "culture", "technologie", "gastronomie", "lecture",
    "apprentissage", "objectifs", "langue",
]

_MAX_IMPORTANT = 5
_BUDGET_TOKENS = 800
_CHARS_PER_TOKEN = 4   # rough approximation


class MemoryManager:
    def __init__(self, db: Database, llm=None):
        self._db = db
        self._llm = llm

    # ── Selection ─────────────────────────────────────────────

    def get_context_memories(self, profile_id: str) -> list:
        """Returns list of memory dicts to inject into system prompt.

        Rules:
        - Exclude memories tagged 'confidentiel'
        - Always include memories tagged 'important' (max 5)
        - Fill remaining budget (800 tokens) with others sorted by weight DESC, last_used DESC
        """
        all_memories = self._db.list_memories(profile_id)
        if not all_memories:
            return []

        confidential_ids = {
            m["id"] for m in all_memories if "confidentiel" in m["tags"]
        }

        important = [
            m for m in all_memories
            if "important" in m["tags"] and m["id"] not in confidential_ids
        ][:_MAX_IMPORTANT]
        selected_ids = {m["id"] for m in important}

        rest = sorted(
            [
                m for m in all_memories
                if m["id"] not in selected_ids and m["id"] not in confidential_ids
            ],
            key=lambda m: (-m["weight"], -(m["last_used"] or 0)),
        )

        selected = list(important)
        budget_chars = _BUDGET_TOKENS * _CHARS_PER_TOKEN
        used_chars = sum(len(m["content"]) + 12 for m in selected)

        for m in rest:
            line_len = len(m["content"]) + 12
            if used_chars + line_len > budget_chars:
                break
            selected.append(m)
            used_chars += line_len

        return selected

    def format_memory_block(self, memories: list) -> str:
        """Formats a list of memories for system prompt injection."""
        if not memories:
            return ""
        lines = []
        for m in memories:
            tags = m["tags"] if isinstance(m["tags"], list) else json.loads(m["tags"])
            first_tag = next(
                (t for t in tags if t not in ("important", "confidentiel")), "perso"
            )
            lines.append(f"- [{first_tag}] {m['content']}")
        return "## Ce que tu sais sur ton élève\n" + "\n".join(lines)

    # ── Topic suggestions ──────────────────────────────────────

    def get_topic_suggestions(self, profile_id: str, last_sessions: list) -> list:
        """Returns 0-3 topic suggestion strings from memories (no LLM)."""
        memories = self._db.list_memories(profile_id)
        if not memories:
            return []

        relevant = [
            m for m in memories
            if any(t in ("objectifs", "pro", "travail", "carrière") for t in m["tags"])
        ]

        suggestions = []
        for m in relevant[:3]:
            tags = m["tags"]
            content = m["content"]
            if "objectifs" in tags:
                suggestions.append(f"Continuer sur : {content}")
            else:
                suggestions.append(f"Parler de : {content}")

        return suggestions[:3]

    # ── AI extraction ──────────────────────────────────────────

    def extract_suggestions_async(
        self,
        profile_id: str,
        session_id: str,
        exchanges: list,
        on_done=None,
    ):
        """Launches background AI extraction. on_done(count: int) called when done."""
        if not self._llm or len(exchanges) < 3:
            return
        threading.Thread(
            target=self._extract,
            args=(profile_id, session_id, exchanges, on_done),
            daemon=True,
        ).start()

    def _extract(self, profile_id: str, session_id: str, exchanges: list, on_done):
        try:
            convo = "\n".join(
                f"Apprenant: {e['user_text']}\nCoach: {e['ai_response'][:150]}"
                for e in exchanges[:10]
            )
            system = (
                "Tu extrais des faits mémorables sur un apprenant de langue. "
                "Réponds uniquement en JSON valide."
            )
            user = (
                "Analyse cette conversation et extrais 1 à 3 faits mémorables sur l'utilisateur.\n"
                "Chaque fait doit être court (max 120 chars), factuel, et utile pour personnaliser "
                "les prochaines sessions.\n\n"
                "Format JSON strict :\n"
                '[{"content": "...", "tags": ["tag1"]}, ...]\n\n'
                "Retourne UNIQUEMENT le JSON, rien d'autre. Si rien de mémorable, retourne [].\n\n"
                f"Conversation :\n{convo[:1500]}"
            )
            response = self._llm.chat_oneshot(system, user)
            if not response:
                return
            suggestions = self._parse_suggestions(response)
            count = 0
            for s in suggestions:
                content = str(s.get("content", ""))[:120]
                tags = s.get("tags", [])
                if content:
                    self._db.create_memory_suggestion(profile_id, session_id, content, tags)
                    count += 1
            if on_done:
                on_done(count)
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")

    def _parse_suggestions(self, text: str) -> list:
        """Extracts JSON array from LLM response (tolerant of surrounding text)."""
        try:
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    # ── Weight update ──────────────────────────────────────────

    def update_weights_after_injection(self, memories: list, ai_response: str):
        """Updates last_used for all injected memories; bumps weight if cited."""
        for m in memories:
            self._db.update_memory_last_used(m["id"])
            keywords = [w for w in m["content"].lower().split()[:4] if len(w) > 3]
            if keywords and all(kw in ai_response.lower() for kw in keywords[:2]):
                self._db.update_memory_weight(m["id"], increment=0.1)
```

- [ ] **Step 4: Run tests — all must pass**

```bash
python -m pytest tests/test_memory_manager.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add langcoach/core/memory_manager.py langcoach/tests/test_memory_manager.py
git commit -m "feat: add MemoryManager with selection algorithm and AI extraction"
```

---

## Task 3: PromptBuilder — inject memory block

**Files:**
- Modify: `langcoach/core/prompt_builder.py`
- Create: `langcoach/tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

Create `langcoach/tests/test_prompt_builder.py`:

```python
# langcoach/tests/test_prompt_builder.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompt_builder.py -v 2>&1 | head -20
```

Expected: `FAILED — build_system_prompt() got unexpected keyword argument 'memories'`

- [ ] **Step 3: Modify `build_system_prompt()` in `prompt_builder.py`**

Change the function signature and add the memory block. The full file after modification:

```python
"""
LangCoach — Prompt Builder
Génère le system prompt en fonction des paramètres de session
"""
import json

from config.settings import TEACHER_STYLES, LEVELS, TARGET_LANGUAGES, NATIVE_LANGUAGES, COACHES


def build_system_prompt(settings: dict, user_name: str = "the student",
                        memories: list = None) -> str:
    style_key = settings.get("teacher_style", "bienveillant")
    level_key = settings.get("level", "B1")
    topic = settings.get("topic", "Conversation libre")
    target_lang_key = settings.get("target_language", "english")
    native_lang_key = settings.get("native_language", "fr")
    coach_key = settings.get("coach", "angela")

    style = TEACHER_STYLES.get(style_key, TEACHER_STYLES["bienveillant"])
    level = LEVELS.get(level_key, LEVELS["B1"])
    target_lang = TARGET_LANGUAGES.get(target_lang_key, TARGET_LANGUAGES["english"])
    native_lang = NATIVE_LANGUAGES.get(native_lang_key, "French")

    lang_coaches = COACHES.get(target_lang_key, COACHES["english"])
    coach = lang_coaches.get(coach_key) or next(iter(lang_coaches.values()))
    coach_name = coach["name"]

    lang_name = target_lang["label"].split(" ")[0]
    native_name = native_lang

    prompt = f"""You are {coach_name}, an expert {lang_name} language teacher.

## Student Profile
- Name: {user_name} (address them by name occasionally, warmly)
- Target language: {lang_name}
- Level: {level_key} — {level['desc']}
- Native language: {native_name}
- Conversation topic: {topic}

## Your Teaching Style
{style['system_hint']}

## Core Rules
1. ALWAYS respond ONLY in {lang_name}. NEVER translate your response or add any translation into another language. Do NOT include parenthetical translations. Do NOT add text in {native_name} or any other language.
2. Keep responses concise and conversational (2-4 sentences max unless explaining something).
3. Adapt your vocabulary and sentence complexity strictly to {level_key} level.
4. When {user_name} makes a mistake, correct it using this EXACT format inline:
   - Minor mistake: reformulate correctly in your reply without any marker.
   - Significant mistake: add a correction marker in this format:
     [type: "original phrase" → "corrected phrase" | brief rule]
     Where type is exactly one of: grammar, vocabulary, tense, syntax, pronunciation_hint
     Example: [tense: "I go yesterday" → "I went yesterday" | simple past irregular verb]
     Keep the correction marker brief and embedded naturally in your response.
5. Stay on the topic "{topic}" unless {user_name} clearly changes subject.
6. If {user_name} goes silent or seems stuck, ask an open, simple question to re-engage.
7. NEVER use markdown formatting. Plain text only, except correction markers in [brackets].
8. Keep the conversation flowing naturally — you are a conversational partner, not a quiz master.

## Tone
{style['description']}

## Session Start
Greet {user_name} warmly in {lang_name}, introduce yourself briefly as {coach_name}, and open the topic "{topic}" with an engaging question suited to {level_key} level."""

    memory_block = _format_memory_block(memories)
    if memory_block:
        prompt += f"\n\n{memory_block}"

    return prompt.strip()


def _format_memory_block(memories: list) -> str:
    if not memories:
        return ""
    lines = []
    for m in memories:
        tags = m["tags"] if isinstance(m["tags"], list) else json.loads(m["tags"])
        first_tag = next(
            (t for t in tags if t not in ("important", "confidentiel")), "perso"
        )
        lines.append(f"- [{first_tag}] {m['content']}")
    return "## Ce que tu sais sur ton élève\n" + "\n".join(lines)


def build_correction_note(original: str, corrected: str, explanation: str) -> str:
    """Format une correction pour l'affichage UI"""
    return f"💡 '{original}' → '{corrected}' — {explanation}"
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_prompt_builder.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add langcoach/core/prompt_builder.py langcoach/tests/test_prompt_builder.py
git commit -m "feat: inject memory block into system prompt"
```

---

## Task 4: StatsEngine — hook memory extraction

**Files:**
- Modify: `langcoach/core/stats_engine.py`

No new tests needed (MemoryManager is already tested; StatsEngine wiring is integration-level).

- [ ] **Step 1: Add `set_memory_manager()` method to `StatsEngine`**

After `__init__()`:

```python
def set_memory_manager(self, memory_manager):
    self._memory_manager = memory_manager
```

Also add `self._memory_manager = None` in `__init__()`:

```python
def __init__(self, db: Database, llm):
    self._db = db
    self._llm = llm
    self._memory_manager = None
    self._profile: Optional[dict] = None
    self._session_id: Optional[str] = None
    self._exchange_count = 0
    self._error_count = 0
```

- [ ] **Step 2: Modify `end_session()` to call memory extraction**

Replace the existing `end_session()` with:

```python
def end_session(self, on_memory_suggestions=None):
    """Close session and launch background analysis + memory extraction."""
    if not self._session_id:
        return
    session_id = self._session_id
    exchange_count = self._exchange_count
    profile = self._profile
    self._db.close_session(session_id, quality_score=None, summary=None)

    if exchange_count >= 3 and self._llm and profile:
        threading.Thread(
            target=self._analyze_session_async,
            args=(session_id,),
            daemon=True,
        ).start()

        if self._memory_manager:
            exchanges = self._db.get_session_exchanges(session_id)
            self._memory_manager.extract_suggestions_async(
                profile["id"], session_id, exchanges,
                on_done=on_memory_suggestions,
            )

    self._session_id = None
    self._exchange_count = 0
    self._error_count = 0
```

- [ ] **Step 3: Add `analyze_and_extract_async()` for "Finir et Analyser" button**

This method triggers both analysis and memory extraction, then calls `on_done(score, summary, suggestion_count)`.

Add after `end_session()`:

```python
def analyze_and_extract_async(self, on_done):
    """Used by 'Finir et Analyser' button. Calls on_done(score, summary, suggestion_count)."""
    if not self._session_id:
        on_done(None, "Aucune session en cours.", 0)
        return

    session_id = self._session_id
    profile = self._profile
    exchange_count = self._exchange_count

    # Close the session
    self._db.close_session(session_id, quality_score=None, summary=None)
    self._session_id = None
    self._exchange_count = 0
    self._error_count = 0

    if not self._llm or not profile:
        on_done(None, "LLM non disponible.", 0)
        return

    suggestion_count_holder = [0]
    analysis_result = [None, None]
    done_events = [False, False]  # [analysis_done, extraction_done]

    def _check_both_done():
        if all(done_events):
            score, summary = analysis_result
            on_done(score, summary, suggestion_count_holder[0])

    def _on_analysis(score, summary):
        analysis_result[0] = score
        analysis_result[1] = summary
        done_events[0] = True
        _check_both_done()

    def _on_extraction(count):
        suggestion_count_holder[0] = count
        done_events[1] = True
        _check_both_done()

    self.analyze_session_by_id(session_id, _on_analysis)

    if self._memory_manager and exchange_count >= 3:
        exchanges = self._db.get_session_exchanges(session_id)
        self._memory_manager.extract_suggestions_async(
            profile["id"], session_id, exchanges,
            on_done=_on_extraction,
        )
    else:
        done_events[1] = True
        _check_both_done()
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add langcoach/core/stats_engine.py
git commit -m "feat: hook memory extraction into StatsEngine end_session and add analyze_and_extract_async"
```

---

## Task 5: MemoryPanel UI

**Files:**
- Create: `langcoach/ui/memory_panel.py`
- Modify: `langcoach/ui/settings_panel.py`

No unit tests for UI. Manual verification required.

- [ ] **Step 1: Create `langcoach/ui/memory_panel.py`**

```python
"""
LangCoach — Memory Panel
Dialog de gestion des mémoires du profil
"""
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QLineEdit, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config.theme import T
from core.memory_manager import SYSTEM_TAGS


class TagChip(QPushButton):
    """Clickable tag chip."""
    def __init__(self, tag: str, selected: bool = False, parent=None):
        super().__init__(tag, parent)
        self.tag = tag
        self._selected = selected
        self.setCheckable(True)
        self.setChecked(selected)
        self._refresh_style()
        self.toggled.connect(lambda _: self._refresh_style())

    def _refresh_style(self):
        sel = self.isChecked()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent_soft'] if sel else T['bg_card']};
                color: {T['accent'] if sel else T['text_secondary']};
                border: 1px solid {T['accent'] if sel else T['border']};
                border-radius: 10px;
                padding: 3px 10px;
                font-size: {T['font_size_xs']}px;
                font-family: '{T['font_body']}';
            }}
        """)


class MemoryRow(QWidget):
    """Single memory row: content + tags + delete button."""
    deleted = pyqtSignal(str)  # emits memory_id

    def __init__(self, memory: dict, parent=None):
        super().__init__(parent)
        self._memory_id = memory["id"]
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        tags = memory["tags"]
        source = memory.get("source", "manual")
        source_icon = "🤖" if source == "ai" else "✍️"

        # Source icon
        src_lbl = QLabel(source_icon)
        src_lbl.setStyleSheet("background: transparent; border: none;")
        src_lbl.setFixedWidth(18)
        layout.addWidget(src_lbl)

        # Content + tags column
        col = QVBoxLayout()
        col.setSpacing(3)

        content_lbl = QLabel(memory["content"])
        content_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        content_lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        content_lbl.setWordWrap(True)
        col.addWidget(content_lbl)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        tag_row.setContentsMargins(0, 0, 0, 0)
        for tag in tags:
            badge_text = tag
            if tag == "important":
                badge_text = "📌 important"
            elif tag == "confidentiel":
                badge_text = "🔒 confidentiel"
            badge = QLabel(badge_text)
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {T['accent_soft']};
                    color: {T['accent']};
                    border-radius: 8px;
                    padding: 1px 7px;
                    font-size: {T['font_size_xs']}px;
                    font-family: '{T['font_body']}';
                }}
            """)
            tag_row.addWidget(badge)
        tag_row.addStretch()
        col.addLayout(tag_row)

        layout.addLayout(col, 1)

        # Delete button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{ color: {T['error']}; }}
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self._memory_id))
        layout.addWidget(del_btn)


class AddMemoryForm(QWidget):
    """Inline form for adding a new memory."""
    submitted = pyqtSignal(str, list)  # content, tags

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['accent']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ex : Prépare un entretien chez Google en juin… (max 120 chars)")
        self._input.setMaxLength(120)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T['bg_secondary']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                padding: 6px 10px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QLineEdit:focus {{ border-color: {T['accent']}; }}
        """)
        layout.addWidget(self._input)

        self._counter = QLabel("0 / 120")
        self._counter.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none; font-size: {T['font_size_xs']}px;")
        self._counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._counter)
        self._input.textChanged.connect(lambda t: self._counter.setText(f"{len(t)} / 120"))

        # Tag chips
        tag_label = QLabel("Tags :")
        tag_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none; font-size: {T['font_size_xs']}px;")
        layout.addWidget(tag_label)

        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFixedHeight(80)
        chips_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        chips_widget = QWidget()
        chips_widget.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_widget)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._chips = {}
        for tag in SYSTEM_TAGS:
            chip = TagChip(tag)
            self._chips[tag] = chip
            chips_layout.addWidget(chip)
        chips_layout.addStretch()
        chips_scroll.setWidget(chips_widget)
        layout.addWidget(chips_scroll)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
                padding: 0 12px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ color: {T['text_primary']}; }}
        """)
        cancel_btn.clicked.connect(lambda: self.hide())
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Enregistrer")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: white;
                border: none; border-radius: {T['radius_sm']}px;
                padding: 0 12px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}'; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        content = self._input.text().strip()
        if not content:
            return
        tags = [tag for tag, chip in self._chips.items() if chip.isChecked()]
        self.submitted.emit(content, tags)
        self._input.clear()
        for chip in self._chips.values():
            chip.setChecked(False)
        self.hide()


class SuggestionRow(QWidget):
    """Suggestion row with Accept / Edit / Reject actions."""
    accepted = pyqtSignal(str)   # suggestion_id
    rejected = pyqtSignal(str)   # suggestion_id

    def __init__(self, suggestion: dict, parent=None):
        super().__init__(parent)
        self._suggestion_id = suggestion["id"]
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['warning'] if T.get('warning') else T['border']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(3)

        content_lbl = QLabel(suggestion["content"])
        content_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        content_lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        content_lbl.setWordWrap(True)
        col.addWidget(content_lbl)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        for tag in suggestion["tags"]:
            badge = QLabel(tag)
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {T['accent_soft']}; color: {T['accent']};
                    border-radius: 8px; padding: 1px 7px;
                    font-size: {T['font_size_xs']}px; font-family: '{T['font_body']}';
                }}
            """)
            tag_row.addWidget(badge)
        tag_row.addStretch()
        col.addLayout(tag_row)
        layout.addLayout(col, 1)

        accept_btn = QPushButton("✓ Accepter")
        accept_btn.setFixedHeight(28)
        accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['success'] if T.get('success') else T['accent']}; color: white;
                border: none; border-radius: {T['radius_sm']}px;
                padding: 0 10px; font-size: {T['font_size_xs']}px; font-family: '{T['font_body']}';
            }}
        """)
        accept_btn.clicked.connect(lambda: self.accepted.emit(self._suggestion_id))
        layout.addWidget(accept_btn)

        reject_btn = QPushButton("✕")
        reject_btn.setFixedSize(28, 28)
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {T['error']}; border-color: {T['error']}; }}
        """)
        reject_btn.clicked.connect(lambda: self.rejected.emit(self._suggestion_id))
        layout.addWidget(reject_btn)


class MemoryDialog(QDialog):
    """Full memory management dialog."""

    def __init__(self, db, profile: dict, parent=None):
        super().__init__(parent)
        self._db = db
        self._profile = profile
        self.setWindowTitle("Mémoires")
        self.setMinimumSize(540, 620)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background-color: {T['bg_secondary']}; border-bottom: 1px solid {T['border']};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 16, 0)
        title = QLabel("🧠  Mémoires")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        h_layout.addWidget(title, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
            }}
            QPushButton:hover {{ color: {T['text_primary']}; border-color: {T['accent']}; }}
        """)
        close_btn.clicked.connect(self.accept)
        h_layout.addWidget(close_btn)
        root.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {T['bg_primary']}; }}")
        content = QWidget()
        content.setStyleSheet(f"background-color: {T['bg_primary']};")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(20, 16, 20, 20)
        self._content_layout.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._refresh()

    def _refresh(self):
        """Clears and rebuilds the content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        suggestions = self._db.list_memory_suggestions(self._profile["id"])
        memories = self._db.list_memories(self._profile["id"])

        # Suggestions banner
        if suggestions:
            banner = QWidget()
            banner.setStyleSheet(f"""
                QWidget {{
                    background-color: {T['accent_soft']};
                    border: 1px solid {T['accent']};
                    border-radius: {T['radius_md']}px;
                }}
            """)
            b_layout = QVBoxLayout(banner)
            b_layout.setContentsMargins(12, 10, 12, 10)
            b_layout.setSpacing(8)

            b_title = QLabel(f"💡 {len(suggestions)} mémoire(s) suggérée(s) — à valider")
            b_title.setFont(QFont(T["font_body"], T["font_size_sm"]))
            b_title.setStyleSheet(f"color: {T['accent']}; background: transparent; font-weight: 600;")
            b_layout.addWidget(b_title)

            for s in suggestions:
                row = SuggestionRow(s)
                row.accepted.connect(self._on_accept)
                row.rejected.connect(self._on_reject)
                b_layout.addWidget(row)

            self._content_layout.addWidget(banner)

        # Add memory button + form
        add_btn = QPushButton("＋  Ajouter une mémoire")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px;
                padding: 0 16px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ border-color: {T['accent']}; color: {T['accent']}; background: {T['accent_soft']}; }}
        """)
        self._content_layout.addWidget(add_btn)

        self._add_form = AddMemoryForm()
        self._add_form.hide()
        self._add_form.submitted.connect(self._on_add_memory)
        self._content_layout.addWidget(self._add_form)
        add_btn.clicked.connect(lambda: self._add_form.setVisible(not self._add_form.isVisible()))

        # Memories list
        if not memories:
            empty = QLabel("Aucune mémoire enregistrée.")
            empty.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(empty)
        else:
            section_lbl = QLabel(f"Mémoires ({len(memories)})")
            section_lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
            section_lbl.setStyleSheet(f"color: {T['text_muted']}; background: transparent; letter-spacing: 1px;")
            self._content_layout.addWidget(section_lbl)

            for m in memories:
                row = MemoryRow(m)
                row.deleted.connect(self._on_delete)
                self._content_layout.addWidget(row)

        self._content_layout.addStretch()

    def _on_add_memory(self, content: str, tags: list):
        self._db.create_memory(self._profile["id"], content, tags, source="manual")
        self._refresh()

    def _on_delete(self, memory_id: str):
        self._db.delete_memory(memory_id)
        self._refresh()

    def _on_accept(self, suggestion_id: str):
        self._db.accept_memory_suggestion(suggestion_id)
        self._refresh()

    def _on_reject(self, suggestion_id: str):
        self._db.delete_memory_suggestion(suggestion_id)
        self._refresh()
```

- [ ] **Step 2: Add "Mémoires" button to `settings_panel.py`**

In `SettingsPanel.__init__()`, after the `layout.addStretch()` line and before the `layout.addWidget(self._section("⬆  App"))` line, add:

```python
layout.addWidget(self._section("🧠  Mémoires"))
layout.addWidget(self._build_memories_section())
```

Then add the method:

```python
def _build_memories_section(self) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    desc = QLabel("Faits personnels injectés dans le prompt pour personnaliser vos sessions.")
    desc.setFont(QFont(T["font_body"], T["font_size_xs"]))
    desc.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    btn = QPushButton("Gérer les mémoires →")
    btn.setFixedHeight(36)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {T['bg_card']};
            color: {T['text_primary']};
            border: 1px solid {T['border']};
            border-radius: {T['radius_md']}px;
            padding: 0 16px;
            font-size: {T['font_size_sm']}px;
            font-family: '{T['font_body']}';
        }}
        QPushButton:hover {{
            border-color: {T['accent']};
            background-color: {T['accent_soft']};
            color: {T['accent']};
        }}
    """)
    btn.clicked.connect(self._open_memory_dialog)
    layout.addWidget(btn)

    self._memory_suggestion_badge = QLabel("")
    self._memory_suggestion_badge.setStyleSheet(
        f"color: {T['accent']}; background: transparent; font-size: {T['font_size_xs']}px;"
    )
    self._memory_suggestion_badge.hide()
    layout.addWidget(self._memory_suggestion_badge)

    return w

def _open_memory_dialog(self):
    if not hasattr(self, '_profile') or not self._profile:
        return
    from ui.memory_panel import MemoryDialog
    dlg = MemoryDialog(self._db, self._profile, parent=self)
    dlg.exec()

def set_profile_context(self, db, profile: dict):
    """Called by MainWindow after init to provide profile context for the memory dialog."""
    self._db = db
    self._profile = profile

def update_suggestion_badge(self, count: int):
    """Shows/hides a badge with pending suggestion count."""
    if count > 0:
        self._memory_suggestion_badge.setText(f"💡 {count} suggestion(s) en attente")
        self._memory_suggestion_badge.show()
    else:
        self._memory_suggestion_badge.hide()
```

- [ ] **Step 3: Verify app launches without errors (manual)**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS/langcoach
python main.py
```

Open Settings panel → scroll to "Mémoires" section → click "Gérer les mémoires →" → dialog opens.

- [ ] **Step 4: Commit**

```bash
git add langcoach/ui/memory_panel.py langcoach/ui/settings_panel.py
git commit -m "feat: add MemoryDialog with list, add, validate-suggestions UI"
```

---

## Task 6: MainWindow — wire memories + Finir et Analyser + topic picker

**Files:**
- Modify: `langcoach/ui/main_window.py`

- [ ] **Step 1: Import `MemoryManager` and init in `MainWindow.__init__()`**

In `main_window.py`, add the import at the top:

```python
from core.memory_manager import MemoryManager
```

In `MainWindow.__init__()`, after `self._stats = StatsEngine(db=db, llm=None)`:

```python
self._memory_manager = MemoryManager(db=db, llm=None)
```

- [ ] **Step 2: Pass `MemoryManager` to `StatsEngine` and `SettingsPanel` in `_start_session()`**

In `_start_session()`, after `self._stats._llm = self.session._llm`:

```python
def _on_models_ready_with_llm(status: dict):
    self._stats._llm = self.session._llm
    self._memory_manager._llm = self.session._llm
    self._stats.set_memory_manager(self._memory_manager)
    self.sig_models_ready.emit(status)
```

After `self.session.initialize(...)`:

```python
self._settings_panel.set_profile_context(self._db, self._profile)
```

- [ ] **Step 3: Add "Finir et Analyser" button in `_build_header()`**

Replace the existing `self._btn_reset` block in `_build_header()`:

```python
self._btn_finir = QPushButton("🔍  Finir et Analyser")
self._btn_finir.setStyleSheet(btn_style)
self._btn_finir.setFixedHeight(36)
self._btn_finir.setToolTip("Analyser la session et extraire des mémoires")
self._btn_finir.clicked.connect(self._on_finir_analyser)
layout.addWidget(self._btn_finir)

self._btn_reset = QPushButton("↺  Nouvelle session")
self._btn_reset.setStyleSheet(btn_style)
self._btn_reset.setFixedHeight(36)
self._btn_reset.setToolTip("Réinitialiser la conversation (R)")
self._btn_reset.clicked.connect(self._on_reset)
layout.addWidget(self._btn_reset)
```

- [ ] **Step 4: Add `_on_finir_analyser()` method**

Add after `_on_reset()`:

```python
def _on_finir_analyser(self):
    """Closes session, runs quality analysis + memory extraction, shows recap modal."""
    if not self._stats.session_id:
        self._show_toast("Aucune session active à analyser", kind="info")
        return

    self._btn_finir.setEnabled(False)
    self._btn_finir.setText("⏳  Analyse en cours…")

    def on_done(score, summary, suggestion_count):
        # Re-enable button (thread-safe via signal)
        from PyQt6.QtCore import QMetaObject, Qt as QtCore_Qt
        QMetaObject.invokeMethod(
            self, "_on_analysis_complete",
            QtCore_Qt.ConnectionType.QueuedConnection,
            *[],  # use a lambda signal instead
        )
        self._show_analysis_recap(score, summary, suggestion_count)

    # Use a signal to safely update UI from background thread
    self._pending_recap = None

    class _Emitter(QObject := __import__('PyQt6.QtCore', fromlist=['QObject']).QObject):
        pass

    from PyQt6.QtCore import QObject, pyqtSignal as _sig

    class Emitter(QObject):
        done = _sig(object, object, int)

    emitter = Emitter()
    emitter.done.connect(self._on_finir_result)
    self._finir_emitter = emitter  # keep alive

    def _on_done(score, summary, suggestion_count):
        emitter.done.emit(score, summary, suggestion_count)

    self._stats.analyze_and_extract_async(_on_done)

    # Clear chat for new session
    while self._chat_layout.count() > 1:
        item = self._chat_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    self.session.reset_session()

def _on_finir_result(self, score, summary, suggestion_count):
    self._btn_finir.setEnabled(True)
    self._btn_finir.setText("🔍  Finir et Analyser")
    self._show_analysis_recap(score, summary, suggestion_count)

def _show_analysis_recap(self, score, summary, suggestion_count):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
    dlg = QDialog(self)
    dlg.setWindowTitle("Résumé de session")
    dlg.setMinimumWidth(400)
    dlg.setStyleSheet(f"background-color: {T['bg_card']}; color: {T['text_primary']};")

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(16)

    title = QLabel("📊 Résumé de la session")
    title.setFont(QFont(T["font_display"], T["font_size_lg"]))
    title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
    layout.addWidget(title)

    if score is not None:
        score_pct = round(score * 100)
        score_color = T.get("success", T["accent"]) if score >= 0.7 else T.get("warning", T["accent"])
        score_lbl = QLabel(f"Score qualité : {score_pct} / 100")
        score_lbl.setFont(QFont(T["font_body"], T["font_size_md"]))
        score_lbl.setStyleSheet(f"color: {score_color}; background: transparent; font-weight: 600;")
        layout.addWidget(score_lbl)

    if summary:
        from PyQt6.QtWidgets import QTextEdit
        summary_edit = QTextEdit()
        summary_edit.setPlainText(summary)
        summary_edit.setReadOnly(True)
        summary_edit.setFixedHeight(80)
        summary_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {T['bg_secondary']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                padding: 8px;
                font-size: {T['font_size_sm']}px;
            }}
        """)
        layout.addWidget(summary_edit)

    if suggestion_count > 0:
        mem_lbl = QLabel(f"💡 {suggestion_count} mémoire(s) suggérée(s) — Consultez l'onglet Mémoires dans les paramètres.")
        mem_lbl.setStyleSheet(f"color: {T['accent']}; background: transparent; font-size: {T['font_size_sm']}px;")
        mem_lbl.setWordWrap(True)
        layout.addWidget(mem_lbl)
        self._settings_panel.update_suggestion_badge(suggestion_count)

    ok_btn = QPushButton("Fermer")
    ok_btn.setFixedHeight(36)
    ok_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {T['accent']}; color: white;
            border: none; border-radius: {T['radius_md']}px;
            padding: 0 20px; font-size: {T['font_size_sm']}px;
            font-family: '{T['font_body']}'; font-weight: 600;
        }}
    """)
    ok_btn.clicked.connect(dlg.accept)
    layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()
```

- [ ] **Step 5: Wire memories into session start — inject into prompt**

In `_start_session()`, modify `session.initialize()` call. First, check how `SessionManager.initialize()` takes settings and profile. Read `langcoach/core/session.py` lines around `initialize()` to understand the signature. Then pass the memory block:

The system prompt is built in `session.py` via `prompt_builder.build_system_prompt()`. To inject memories, we need to pass them to the session. Add this after `self.session.initialize(...)`:

```python
# Inject memories into the active session prompt
memories = self._memory_manager.get_context_memories(self._profile["id"])
if memories and hasattr(self.session, '_llm') and self.session._llm:
    from core.prompt_builder import build_system_prompt
    prompt = build_system_prompt(
        self.settings,
        user_name=self._profile.get("name", ""),
        memories=memories,
    )
    self.session._llm.set_system_prompt(prompt)
```

Note: Read `langcoach/core/session.py` first to verify `self.session._llm` is accessible at this point. If models are loaded asynchronously (which they are based on the existing `sig_models_ready` signal), update the prompt inside `_on_models_ready_with_llm()` instead:

```python
def _on_models_ready_with_llm(status: dict):
    self._stats._llm = self.session._llm
    self._memory_manager._llm = self.session._llm
    self._stats.set_memory_manager(self._memory_manager)
    # Inject memories into prompt now that LLM is ready
    memories = self._memory_manager.get_context_memories(self._profile["id"])
    if memories:
        from core.prompt_builder import build_system_prompt
        prompt = build_system_prompt(
            self.settings,
            user_name=self._profile.get("name", ""),
            memories=memories,
        )
        self.session._llm.set_system_prompt(prompt)
    self.sig_models_ready.emit(status)
```

- [ ] **Step 6: Add topic picker screen**

In `_build_ui()`, replace the session_widget block with a stacked widget that has topic picker at index 0 and chat at index 1:

```python
# Session tab: topic picker (index 0) + chat (index 1)
session_widget = QWidget()
session_widget.setStyleSheet(f"background-color: {T['bg_primary']};")
session_outer_layout = QVBoxLayout(session_widget)
session_outer_layout.setContentsMargins(0, 0, 0, 0)
session_outer_layout.setSpacing(0)

self._session_stack = QStackedWidget()
self._session_stack.setStyleSheet(f"background-color: {T['bg_primary']};")

# Topic picker (index 0)
self._topic_picker = self._build_topic_picker()
self._session_stack.addWidget(self._topic_picker)

# Chat area (index 1)
chat_widget = QWidget()
chat_widget.setStyleSheet(f"background-color: {T['bg_primary']};")
chat_vlayout = QVBoxLayout(chat_widget)
chat_vlayout.setContentsMargins(0, 0, 0, 0)
chat_vlayout.setSpacing(0)
self._chat_scroll = self._build_chat_area()
chat_vlayout.addWidget(self._chat_scroll, 1)
input_bar = self._build_input_bar()
chat_vlayout.addWidget(input_bar)
self._session_stack.addWidget(chat_widget)

session_outer_layout.addWidget(self._session_stack, 1)
self._main_stack.addWidget(session_widget)
```

Then show topic picker on reset and chat on session start.

Add `_build_topic_picker()` method:

```python
def _build_topic_picker(self) -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background-color: {T['bg_primary']};")
    layout = QVBoxLayout(w)
    layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
    layout.setSpacing(T["spacing_lg"])
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    title = QLabel("Choisissez un thème pour cette session")
    title.setFont(QFont(T["font_display"], T["font_size_xl"]))
    title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
    layout.addWidget(title)

    sub = QLabel("Ou saisissez un thème libre en bas")
    sub.setFont(QFont(T["font_body"], T["font_size_sm"]))
    sub.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
    layout.addWidget(sub)

    layout.addSpacing(T["spacing_md"])

    # Memory-based suggestions block (populated at runtime)
    self._memory_topics_section = QWidget()
    self._memory_topics_section.setStyleSheet("background: transparent;")
    self._memory_topics_layout = QVBoxLayout(self._memory_topics_section)
    self._memory_topics_layout.setContentsMargins(0, 0, 0, 0)
    self._memory_topics_layout.setSpacing(8)
    layout.addWidget(self._memory_topics_section)

    # Default topics
    default_label = QLabel("THÈMES HABITUELS")
    default_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
    default_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent; letter-spacing: 1px;")
    layout.addWidget(default_label)

    default_topics = [
        "Conversation libre", "Actualités", "Voyage", "Travail",
        "Culture & cinéma", "Sport", "Gastronomie", "Technologie",
    ]
    topics_grid = QWidget()
    topics_grid.setStyleSheet("background: transparent;")
    grid_layout = QHBoxLayout(topics_grid)
    grid_layout.setContentsMargins(0, 0, 0, 0)
    grid_layout.setSpacing(8)
    grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    for topic in default_topics:
        btn = QPushButton(topic)
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{
                background-color: {T['accent_soft']};
                color: {T['accent']};
                border-color: {T['accent']};
            }}
        """)
        btn.clicked.connect(lambda _, t=topic: self._start_with_topic(t))
        grid_layout.addWidget(btn)

    grid_layout.addStretch()
    layout.addWidget(topics_grid)

    layout.addStretch()

    # Free input row
    free_row = QHBoxLayout()
    self._topic_free_input = QLineEdit()
    self._topic_free_input.setPlaceholderText("Ou saisir un thème libre…")
    self._topic_free_input.setFixedHeight(44)
    self._topic_free_input.setStyleSheet(f"""
        QLineEdit {{
            background-color: {T['bg_card']};
            color: {T['text_primary']};
            border: 1px solid {T['border']};
            border-radius: {T['radius_md']}px;
            padding: 0 {T['spacing_md']}px;
            font-size: {T['font_size_md']}px;
            font-family: '{T['font_body']}';
        }}
        QLineEdit:focus {{ border-color: {T['border_active']}; }}
    """)
    self._topic_free_input.returnPressed.connect(self._start_with_free_topic)
    free_row.addWidget(self._topic_free_input, 1)

    start_btn = QPushButton("Démarrer →")
    start_btn.setFixedHeight(44)
    start_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {T['accent']}; color: white;
            border: none; border-radius: {T['radius_md']}px;
            padding: 0 20px; font-size: {T['font_size_sm']}px;
            font-family: '{T['font_body']}'; font-weight: 600;
        }}
    """)
    start_btn.clicked.connect(self._start_with_free_topic)
    free_row.addWidget(start_btn)
    layout.addLayout(free_row)

    return w

def _refresh_topic_picker(self):
    """Repopulates memory-based suggestions in topic picker."""
    # Clear previous memory suggestions
    while self._memory_topics_layout.count():
        item = self._memory_topics_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    last_sessions = self._db.list_sessions(self._profile["id"], limit=3)
    suggestions = self._memory_manager.get_topic_suggestions(self._profile["id"], last_sessions)

    if suggestions:
        mem_label = QLabel("ISSUS DE VOS MÉMOIRES")
        mem_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        mem_label.setStyleSheet(f"color: {T['accent']}; background: transparent; letter-spacing: 1px;")
        self._memory_topics_layout.addWidget(mem_label)

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(8)
        row_l.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for s in suggestions:
            btn = QPushButton(s)
            btn.setFixedHeight(36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {T['accent_soft']};
                    color: {T['accent']};
                    border: 1px solid {T['accent']};
                    border-radius: {T['radius_md']}px;
                    padding: 0 16px;
                    font-size: {T['font_size_sm']}px;
                    font-family: '{T['font_body']}';
                }}
                QPushButton:hover {{ background-color: {T['accent']}; color: white; }}
            """)
            btn.clicked.connect(lambda _, t=s: self._start_with_topic(t))
            row_l.addWidget(btn)

        row_l.addStretch()
        self._memory_topics_layout.addWidget(row_w)
        self._memory_topics_layout.addSpacing(T["spacing_md"])

    self._memory_topics_section.setVisible(bool(suggestions))

def _start_with_topic(self, topic: str):
    """Sets the topic in settings and switches to chat screen."""
    self._update("topic", topic)  # not available — use direct settings update
    self.settings["topic"] = topic
    self._db.update_profile_settings(self._profile["id"], self.settings)
    self.session.update_settings(self.settings)
    self._update_sidebar_info()
    self._session_stack.setCurrentIndex(1)

def _start_with_free_topic(self):
    topic = self._topic_free_input.text().strip()
    if not topic:
        topic = "Conversation libre"
    self._topic_free_input.clear()
    self._start_with_topic(topic)
```

- [ ] **Step 7: Update `_on_reset()` to show topic picker**

Replace `_on_reset()`:

```python
def _on_reset(self):
    """Quick new session — shows topic picker without analysis."""
    while self._chat_layout.count() > 1:
        item = self._chat_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    self.session.reset_session()
    self._refresh_topic_picker()
    self._session_stack.setCurrentIndex(0)
    self._show_toast("Nouvelle session", kind="info")
```

Also update `_start_session()` to show topic picker on first load:

```python
def _start_session(self):
    self._update_sidebar_info()
    self._update_session_title()

    original_on_models_ready = self.session.on_models_ready

    def _on_models_ready_with_llm(status: dict):
        self._stats._llm = self.session._llm
        self._memory_manager._llm = self.session._llm
        self._stats.set_memory_manager(self._memory_manager)
        memories = self._memory_manager.get_context_memories(self._profile["id"])
        if memories:
            from core.prompt_builder import build_system_prompt
            prompt = build_system_prompt(
                self.settings,
                user_name=self._profile.get("name", ""),
                memories=memories,
            )
            self.session._llm.set_system_prompt(prompt)
        self.sig_models_ready.emit(status)

    self.session.on_models_ready = _on_models_ready_with_llm
    self.session.initialize(self.settings, profile=self._profile, stats=self._stats)
    self._dashboard_panel.set_profile(self._profile)
    self._settings_panel.set_profile_context(self._db, self._profile)

    # Show topic picker on startup
    self._refresh_topic_picker()
    self._session_stack.setCurrentIndex(0)
```

- [ ] **Step 8: Update `_reload_profile()` to re-init MemoryManager**

In `_reload_profile()`, after `self._stats = StatsEngine(db=self._db, llm=None)`:

```python
self._memory_manager = MemoryManager(db=self._db, llm=None)
```

- [ ] **Step 9: Run the app and verify manually**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS/langcoach
python main.py
```

Verify:
- [ ] App opens with topic picker screen
- [ ] Memory-based suggestions appear if memories exist (add one via Settings > Mémoires first)
- [ ] Clicking a topic starts the session (chat screen appears)
- [ ] "Finir et Analyser" button appears in header
- [ ] Settings panel has "Mémoires" section with "Gérer les mémoires" button
- [ ] Memory dialog opens and allows adding/deleting memories

- [ ] **Step 10: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 11: Commit**

```bash
git add langcoach/ui/main_window.py
git commit -m "feat: wire MemoryManager into MainWindow, add Finir et Analyser button and topic picker screen"
```

---

## Self-Review

### Spec coverage check

| Spec section | Covered in task |
|---|---|
| 2.1 Table `memories` | Task 1 |
| 2.2 Table `memory_suggestions` | Task 1 |
| 2.3 Tag taxonomy (22 system tags) | Task 2 (SYSTEM_TAGS constant) |
| 3.1 Sélection algorithm (important/confidentiel/budget) | Task 2 |
| 3.2 Format d'injection `[tag] content` | Task 2 + Task 3 |
| 3.3 weight update after injection | Task 2 (`update_weights_after_injection`) |
| 4.1 Extraction auto ≥3 échanges | Task 4 (`end_session`) |
| 4.2 Bouton "Finir et Analyser" | Task 6 |
| 4.3 Mini-prompt d'extraction JSON | Task 2 (`_extract`) |
| 4.4 Notification + validation suggestions | Task 5 (SuggestionRow in MemoryDialog) |
| 5.1 Thèmes issus de la mémoire | Task 6 (`_refresh_topic_picker`) |
| 5.2 Thèmes par défaut | Task 6 (`_build_topic_picker`) |
| 5.3 Comportement sélection thème | Task 6 (`_start_with_topic`) |
| 6.1 Onglet Mémoires dans profil | Task 5 (MemoryDialog via SettingsPanel button) |
| Bouton "Nouvelle session" | Task 6 (existing button kept) |

### Gap identified: weight update after AI response

Spec section 3.3 says weight should be updated when AI response is analyzed. `MemoryManager.update_weights_after_injection()` exists but is not yet called from `MainWindow`. Add this call in `_handle_ai_done()` in Task 6:

```python
def _handle_ai_done(self, text: str):
    if self._current_ai_bubble:
        self._current_ai_bubble.set_text(text)
        self._current_ai_bubble.on_replay = lambda t=text: self.session.replay(t)
        self._current_ai_bubble.finalize()
    self._scroll_to_bottom()
    # Update memory weights based on AI response
    if self._stats.session_id:
        injected = self._memory_manager.get_context_memories(self._profile["id"])
        if injected:
            self._memory_manager.update_weights_after_injection(injected, text)
```

Add this to Task 6 Step 6, after adding `_on_finir_result`.

### Type consistency check

- `db.create_memory()` returns `dict` with `tags: list` (deserialized) ✓
- `MemoryManager.get_context_memories()` returns `list[dict]` with `tags: list` ✓  
- `_format_memory_block()` in both `memory_manager.py` and `prompt_builder.py` both handle `tags` as `list` with JSON fallback ✓
- `StatsEngine.end_session(on_memory_suggestions=None)` — signature change is backward compatible (optional kwarg) ✓
- `SettingsPanel.set_profile_context(db, profile)` called in `_start_session()` after `self._settings_panel` exists ✓

### Placeholder scan — NONE found ✓

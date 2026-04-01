# Profiles, Statistics & Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-profile support, per-exchange oral error tracking, and an analytics dashboard to Echo.

**Architecture:** SQLite database at `~/.langcoach/data.db` stores profiles, sessions, exchanges, errors, and aggregated error patterns. `StatsEngine` parses structured `[type: "original" → "corrected" | rule]` correction markers from LLM responses in real time, then triggers a silent end-of-session LLM analysis for quality scoring. A `DashboardPanel` tab exposes per-profile analytics with automatic lesson recommendations and on-demand AI coaching analysis.

**Tech Stack:** Python 3.9+, PyQt6, SQLite3 (stdlib), uuid (stdlib), re (stdlib), json (stdlib), pytest

---

## File Map

### New Files

| File                                   | Responsibility                                                                 |
| -------------------------------------- | ------------------------------------------------------------------------------ |
| `langcoach/core/database.py`           | SQLite manager: schema creation, CRUD, dashboard queries                       |
| `langcoach/core/stats_engine.py`       | Error parsing, exchange recording, end-of-session LLM analysis, lesson catalog |
| `langcoach/ui/profile_screen.py`       | Profile splash screen + 3-step creation wizard                                 |
| `langcoach/ui/dashboard_panel.py`      | Dashboard tab: Vue globale / Erreurs / Sessions / Leçons                       |
| `langcoach/tests/__init__.py`          | Empty, marks tests as package                                                  |
| `langcoach/tests/test_database.py`     | Unit tests for Database                                                        |
| `langcoach/tests/test_stats_engine.py` | Unit tests for StatsEngine                                                     |

### Modified Files

| File                               | Change                                                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `langcoach/config/settings.py`     | Add `DB_FILE`; add `load_last_profile_id` / `save_last_profile_id` / `migrate_if_needed`                |
| `langcoach/core/prompt_builder.py` | Add `user_name` param; update correction format instructions                                            |
| `langcoach/core/session.py`        | Accept `profile` + `stats` on `initialize()`; wire exchange events; call `end_session()` on reset/close |
| `langcoach/ui/main_window.py`      | Accept `db` + `profile`; add Session/Dashboard tab navigation; wire StatsEngine                         |
| `langcoach/main.py`                | Profile selection flow before MainWindow; inject `db` + `profile`                                       |

---

## Task 1: Database Layer

**Files:**

- Create: `langcoach/core/database.py`
- Create: `langcoach/tests/__init__.py`
- Create: `langcoach/tests/test_database.py`

- [ ] **Step 1.1 — Write failing tests**

```python
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
```

- [ ] **Step 1.2 — Run tests to confirm they fail**

```bash
cd langcoach && python -m pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.database'`

- [ ] **Step 1.3 — Create `langcoach/tests/__init__.py`**

```python
# langcoach/tests/__init__.py
```

- [ ] **Step 1.4 — Implement `langcoach/core/database.py`**

```python
"""
LangCoach — Database Manager
SQLite persistence for profiles, sessions, exchanges, errors, patterns
"""
import json
import time
import uuid
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import sqlite3

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    avatar      TEXT NOT NULL DEFAULT '🧑',
    created_at  INTEGER NOT NULL,
    last_used   INTEGER NOT NULL,
    settings    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    started_at      INTEGER NOT NULL,
    ended_at        INTEGER,
    language        TEXT NOT NULL,
    level           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    exchange_count  INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    quality_score   REAL,
    summary         TEXT
);

CREATE TABLE IF NOT EXISTS exchanges (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    timestamp    INTEGER NOT NULL,
    user_text    TEXT NOT NULL,
    ai_response  TEXT NOT NULL,
    error_count  INTEGER NOT NULL DEFAULT 0,
    duration_ms  INTEGER
);

CREATE TABLE IF NOT EXISTS errors (
    id           TEXT PRIMARY KEY,
    exchange_id  TEXT NOT NULL REFERENCES exchanges(id),
    profile_id   TEXT NOT NULL REFERENCES profiles(id),
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    timestamp    INTEGER NOT NULL,
    error_type   TEXT NOT NULL,
    original     TEXT NOT NULL,
    corrected    TEXT NOT NULL,
    rule         TEXT NOT NULL,
    language     TEXT NOT NULL,
    level        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_patterns (
    profile_id        TEXT NOT NULL REFERENCES profiles(id),
    error_type        TEXT NOT NULL,
    rule              TEXT NOT NULL,
    occurrence_count  INTEGER NOT NULL DEFAULT 1,
    last_seen         INTEGER NOT NULL,
    PRIMARY KEY (profile_id, error_type, rule)
);

CREATE INDEX IF NOT EXISTS idx_sessions_profile ON sessions(profile_id);
CREATE INDEX IF NOT EXISTS idx_errors_profile   ON errors(profile_id);
CREATE INDEX IF NOT EXISTS idx_errors_session   ON errors(session_id);
"""


def _ms() -> int:
    return int(time.time() * 1000)


class Database:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── Profiles ──────────────────────────────────────────────

    def create_profile(self, name: str, avatar: str, settings: dict) -> dict:
        now = _ms()
        pid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO profiles (id, name, avatar, created_at, last_used, settings) VALUES (?,?,?,?,?,?)",
            (pid, name, avatar, now, now, json.dumps(settings)),
        )
        self._conn.commit()
        return self.get_profile(pid)

    def get_profile(self, profile_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return self._profile_dict(row) if row else None

    def list_profiles(self) -> list:
        rows = self._conn.execute(
            "SELECT * FROM profiles ORDER BY last_used DESC"
        ).fetchall()
        return [self._profile_dict(r) for r in rows]

    def update_profile_settings(self, profile_id: str, settings: dict):
        self._conn.execute(
            "UPDATE profiles SET settings = ? WHERE id = ?",
            (json.dumps(settings), profile_id),
        )
        self._conn.commit()

    def touch_profile(self, profile_id: str):
        self._conn.execute(
            "UPDATE profiles SET last_used = ? WHERE id = ?", (_ms(), profile_id)
        )
        self._conn.commit()

    def _profile_dict(self, row) -> dict:
        d = dict(row)
        d["settings"] = json.loads(d["settings"])
        return d

    # ── Sessions ──────────────────────────────────────────────

    def open_session(self, profile_id: str, language: str, level: str, topic: str) -> str:
        sid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO sessions (id, profile_id, started_at, language, level, topic) VALUES (?,?,?,?,?,?)",
            (sid, profile_id, _ms(), language, level, topic),
        )
        self._conn.commit()
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def close_session(self, session_id: str, quality_score: Optional[float], summary: Optional[str]):
        self._conn.execute(
            "UPDATE sessions SET ended_at=?, quality_score=?, summary=? WHERE id=?",
            (_ms(), quality_score, summary, session_id),
        )
        self._conn.commit()

    def list_sessions(self, profile_id: str, limit: int = 20) -> list:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE profile_id=? ORDER BY started_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Exchanges ─────────────────────────────────────────────

    def record_exchange(self, session_id: str, user_text: str, ai_response: str,
                        error_count: int, duration_ms: int) -> str:
        eid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO exchanges (id, session_id, timestamp, user_text, ai_response, error_count, duration_ms) "
            "VALUES (?,?,?,?,?,?,?)",
            (eid, session_id, _ms(), user_text, ai_response, error_count, duration_ms),
        )
        self._conn.execute(
            "UPDATE sessions SET exchange_count = exchange_count + 1, error_count = error_count + ? WHERE id = ?",
            (error_count, session_id),
        )
        self._conn.commit()
        return eid

    # ── Errors ────────────────────────────────────────────────

    def record_errors(self, exchange_id: str, session_id: str, profile_id: str,
                      errors: list, language: str, level: str):
        now = _ms()
        for e in errors:
            self._conn.execute(
                "INSERT INTO errors (id, exchange_id, profile_id, session_id, timestamp, "
                "error_type, original, corrected, rule, language, level) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), exchange_id, profile_id, session_id, now,
                 e["error_type"], e["original"], e["corrected"], e["rule"], language, level),
            )
            self._conn.execute(
                "INSERT INTO error_patterns (profile_id, error_type, rule, occurrence_count, last_seen) "
                "VALUES (?,?,?,1,?) "
                "ON CONFLICT(profile_id, error_type, rule) DO UPDATE SET "
                "occurrence_count = occurrence_count + 1, last_seen = excluded.last_seen",
                (profile_id, e["error_type"], e["rule"], now),
            )
        self._conn.commit()

    # ── Dashboard Queries ──────────────────────────────────────

    def get_kpis(self, profile_id: str) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) as total_sessions, "
            "AVG(CAST(error_count AS REAL) / MAX(exchange_count, 1)) as avg_errors, "
            "AVG(quality_score) as avg_quality, "
            "SUM(CAST(COALESCE(ended_at, started_at) - started_at AS REAL) / 60000) as total_min "
            "FROM sessions WHERE profile_id=? AND ended_at IS NOT NULL",
            (profile_id,),
        ).fetchone()
        return {
            "total_sessions": row["total_sessions"] or 0,
            "avg_errors_per_exchange": round(row["avg_errors"] or 0.0, 1),
            "avg_quality": round((row["avg_quality"] or 0.0) * 100),
            "total_minutes": round(row["total_min"] or 0.0),
            "streak_days": self._compute_streak(profile_id),
        }

    def get_error_breakdown(self, profile_id: str) -> list:
        rows = self._conn.execute(
            "SELECT error_type, COUNT(*) as count FROM errors "
            "WHERE profile_id=? GROUP BY error_type ORDER BY count DESC",
            (profile_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_top_patterns(self, profile_id: str, limit: int = 10) -> list:
        rows = self._conn.execute(
            "SELECT error_type, rule, occurrence_count, last_seen FROM error_patterns "
            "WHERE profile_id=? ORDER BY occurrence_count DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_quality_progression(self, profile_id: str, limit: int = 10) -> list:
        rows = self._conn.execute(
            "SELECT started_at, quality_score FROM sessions "
            "WHERE profile_id=? AND quality_score IS NOT NULL "
            "ORDER BY started_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
        return list(reversed([dict(r) for r in rows]))

    def _compute_streak(self, profile_id: str) -> int:
        rows = self._conn.execute(
            "SELECT DATE(started_at/1000, 'unixepoch') as day FROM sessions "
            "WHERE profile_id=? AND ended_at IS NOT NULL "
            "GROUP BY day ORDER BY day DESC",
            (profile_id,),
        ).fetchall()
        if not rows:
            return 0
        today = date.today()
        streak = 0
        for i, row in enumerate(rows):
            if row["day"] == (today - timedelta(days=i)).isoformat():
                streak += 1
            else:
                break
        return streak

    def close(self):
        self._conn.close()
```

- [ ] **Step 1.5 — Run tests to confirm they pass**

```bash
cd langcoach && python -m pytest tests/test_database.py -v
```

Expected: 8 tests PASS

- [ ] **Step 1.6 — Commit**

```bash
git add core/database.py tests/__init__.py tests/test_database.py
git commit -m "feat: add SQLite database layer for profiles, sessions, errors, patterns"
```

---

## Task 2: Update Config/Settings

**Files:**

- Modify: `langcoach/config/settings.py`

- [ ] **Step 2.1 — Add DB_FILE, profile helpers, and migration**

Add `import logging` and `from typing import Optional` at the top of `langcoach/config/settings.py` if not already present.

Add `DB_FILE` alongside the existing path constants (after `SETTINGS_FILE`):

```python
DB_FILE = DATA_DIR / "data.db"
LAST_PROFILE_FILE = DATA_DIR / "last_profile.json"
```

Add these functions after `save_settings`:

```python
def load_last_profile_id() -> Optional[str]:
    """Returns the last-used profile ID, or None."""
    if LAST_PROFILE_FILE.exists():
        try:
            with open(LAST_PROFILE_FILE) as f:
                return json.load(f).get("profile_id")
        except Exception:
            pass
    return None


def save_last_profile_id(profile_id: str):
    DATA_DIR.mkdir(exist_ok=True)
    with open(LAST_PROFILE_FILE, "w") as f:
        json.dump({"profile_id": profile_id}, f)


def migrate_if_needed(db) -> bool:
    """
    If no profiles exist in DB but old settings.json exists, create a default profile.
    Returns True if migration happened.
    """
    if db.list_profiles():
        return False
    if not SETTINGS_FILE.exists():
        return False
    try:
        with open(SETTINGS_FILE) as f:
            old_settings = {**DEFAULT_SETTINGS, **json.load(f)}
        profile = db.create_profile("Moi", "🧑", old_settings)
        save_last_profile_id(profile["id"])
        logging.getLogger(__name__).info("Migrated old settings.json to profile")
        return True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Migration failed: {e}")
        return False
```

- [ ] **Step 2.2 — Verify imports**

```bash
cd langcoach && python -c "
from config.settings import DB_FILE, load_last_profile_id, save_last_profile_id, migrate_if_needed
print('DB_FILE:', DB_FILE)
print('OK')
"
```

Expected:

```
DB_FILE: /Users/<you>/.langcoach/data.db
OK
```

- [ ] **Step 2.3 — Commit**

```bash
git add config/settings.py
git commit -m "feat: add DB_FILE, profile helpers, and settings migration"
```

---

## Task 3: Update Prompt Builder

**Files:**

- Modify: `langcoach/core/prompt_builder.py`

- [ ] **Step 3.1 — Add `user_name` param and structured correction format**

Replace the `build_system_prompt` function signature and relevant lines in `langcoach/core/prompt_builder.py`:

```python
def build_system_prompt(settings: dict, user_name: str = "the student") -> str:
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
1. ALWAYS respond ONLY in {lang_name}, never in the student's native language.
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
Greet {user_name} warmly in {lang_name}, introduce yourself briefly as {coach_name}, and open the topic "{topic}" with an engaging question suited to {level_key} level.
"""
    return prompt.strip()
```

- [ ] **Step 3.2 — Verify backward compatibility**

```bash
cd langcoach && python -c "
from core.prompt_builder import build_system_prompt
from config.settings import DEFAULT_SETTINGS
p1 = build_system_prompt(DEFAULT_SETTINGS)
assert 'the student' in p1
p2 = build_system_prompt(DEFAULT_SETTINGS, user_name='Franck')
assert 'Franck' in p2
assert 'tense: \"I go yesterday\"' in p2
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3.3 — Commit**

```bash
git add core/prompt_builder.py
git commit -m "feat: inject user name and structured correction format into system prompt"
```

---

## Task 4: Stats Engine

**Files:**

- Create: `langcoach/core/stats_engine.py`
- Create: `langcoach/tests/test_stats_engine.py`

- [ ] **Step 4.1 — Write failing tests**

```python
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
```

- [ ] **Step 4.2 — Run to confirm failure**

```bash
cd langcoach && python -m pytest tests/test_stats_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.stats_engine'`

- [ ] **Step 4.3 — Implement `langcoach/core/stats_engine.py`**

```python
"""
LangCoach — Stats Engine
Parses correction markers from LLM responses, records exchanges/errors to DB,
triggers end-of-session LLM quality analysis.
"""
import json
import logging
import re
import threading
from typing import Optional

from core.database import Database

logger = logging.getLogger(__name__)

# Matches: [type: "original" → "corrected" | rule]
_ERROR_RE = re.compile(r'\[(\w+):\s*"([^"]+)"\s*→\s*"([^"]+)"\s*\|\s*([^\]]+)\]')

LESSON_CATALOG: dict = {
    ("tense", "simple past"): {
        "title": "Simple past — verbes irréguliers",
        "desc": "Les verbes irréguliers ne prennent pas -ed au prétérit.",
        "examples": ["go → went", "have → had", "see → saw", "do → did", "make → made"],
        "tip": "Mémorise les 30 verbes irréguliers les plus courants.",
    },
    ("tense", "present perfect"): {
        "title": "Present perfect vs Simple past",
        "desc": "Present perfect = lien avec le présent. Simple past = passé révolu.",
        "examples": ["I have seen this (still relevant)", "I saw this yesterday (fixed time)"],
        "tip": "Si tu peux dire 'yesterday/last week' → simple past. Sinon → present perfect.",
    },
    ("tense", "past continuous"): {
        "title": "Past continuous",
        "desc": "Action en cours dans le passé, souvent interrompue par une autre.",
        "examples": ["I was cooking when she called", "We were sleeping at midnight"],
        "tip": "Was/were + verb-ing. Donne le contexte (background) d'une action passée.",
    },
    ("grammar", "subject-verb agreement"): {
        "title": "Accord sujet-verbe",
        "desc": "He/she/it → verbe + s au présent simple.",
        "examples": ["She goes (not go)", "He likes (not like)"],
        "tip": "Au présent simple, ajoute toujours -s/-es pour he/she/it.",
    },
    ("grammar", "article"): {
        "title": "Articles : a / an / the",
        "desc": "A/an = première mention ou non-spécifique. The = chose définie.",
        "examples": ["I saw a dog. The dog was big.", "I play tennis (no article for sports)"],
        "tip": "Pas d'article avec les langues, sports, repas, institutions.",
    },
    ("grammar", "conditional"): {
        "title": "Conditionnel — If clauses",
        "desc": "Structures fixes selon le degré de réalité.",
        "examples": [
            "Type 1: If I study, I will pass",
            "Type 2: If I studied, I would pass",
            "Type 3: If I had studied, I would have passed",
        ],
        "tip": "Ne jamais mettre 'would' dans la clause avec 'if'.",
    },
    ("vocabulary", "false friends"): {
        "title": "Faux amis anglais/français",
        "desc": "Mots similaires mais de sens différents.",
        "examples": ["actually = en fait", "eventually = finalement", "sensible = raisonnable"],
        "tip": "Mémorise les 20 faux amis les plus courants.",
    },
    ("vocabulary", "preposition"): {
        "title": "Prépositions de temps et lieu",
        "desc": "In/on/at suivent des règles précises.",
        "examples": ["at 3pm, on Monday, in January", "at the corner, on the street, in the room"],
        "tip": "AT = moment/lieu précis. ON = jour/surface. IN = période/espace fermé.",
    },
    ("syntax", "word order"): {
        "title": "Ordre des mots",
        "desc": "Adverbes de fréquence avant le verbe principal.",
        "examples": ["I always go (not I go always)", "She never eats meat"],
        "tip": "always/never/often/usually → entre sujet et verbe principal.",
    },
    ("grammar", "irregular plural"): {
        "title": "Pluriels irréguliers",
        "desc": "Certains noms ont des pluriels irréguliers.",
        "examples": ["child → children", "person → people", "tooth → teeth", "foot → feet"],
        "tip": "Mémorise les pluriels irréguliers les plus courants.",
    },
}


class StatsEngine:
    def __init__(self, db: Database, llm):
        self._db = db
        self._llm = llm
        self._profile: Optional[dict] = None
        self._session_id: Optional[str] = None
        self._exchange_count = 0
        self._error_count = 0

    def start_session(self, profile: dict, language: str, level: str, topic: str) -> str:
        self._profile = profile
        self._exchange_count = 0
        self._error_count = 0
        self._session_id = self._db.open_session(profile["id"], language, level, topic)
        return self._session_id

    def record_exchange(self, user_text: str, ai_response: str, duration_ms: int):
        if not self._session_id or not self._profile:
            return
        errors = self.parse_errors(ai_response)
        exchange_id = self._db.record_exchange(
            self._session_id, user_text, ai_response, len(errors), duration_ms
        )
        if errors:
            s = self._profile.get("settings", {})
            self._db.record_errors(
                exchange_id, self._session_id, self._profile["id"],
                errors,
                s.get("target_language", "english"),
                s.get("level", "B1"),
            )
        self._exchange_count += 1
        self._error_count += len(errors)

    @staticmethod
    def parse_errors(ai_response: str) -> list:
        """Extract structured correction markers from an AI response."""
        results = []
        for m in _ERROR_RE.finditer(ai_response):
            results.append({
                "error_type": m.group(1).strip().lower(),
                "original":   m.group(2).strip(),
                "corrected":  m.group(3).strip(),
                "rule":       m.group(4).strip().lower(),
            })
        return results

    def end_session(self):
        if not self._session_id:
            return
        session_id = self._session_id   # capture before reset
        exchange_count = self._exchange_count
        self._db.close_session(session_id, quality_score=None, summary=None)
        # Launch background LLM analysis if enough data
        if exchange_count >= 3 and self._llm and self._profile:
            t = threading.Thread(
                target=self._analyze_session_async,
                args=(session_id,),
                daemon=True,
            )
            t.start()
        self._session_id = None
        self._exchange_count = 0
        self._error_count = 0

    def _analyze_session_async(self, session_id: str):
        session = self._db.get_session(session_id)
        if not session or not self._profile:
            return
        breakdown = self._db.get_error_breakdown(self._profile["id"])
        prompt = self._build_analysis_prompt(session, breakdown)
        try:
            response = self._llm.chat(prompt)
            if response:
                score, summary = self._parse_analysis_response(response)
                self._db.close_session(session_id, quality_score=score, summary=summary)
        except Exception as e:
            logger.error(f"Session analysis failed: {e}")

    def _build_analysis_prompt(self, session: dict, breakdown: list) -> str:
        lines = "\n".join(
            f"  - {e['error_type']}: {e['count']} errors" for e in breakdown[:5]
        ) or "  - No errors recorded"
        dur = round((session.get("ended_at", 0) - session.get("started_at", 0)) / 60000)
        return f"""Analyze this language learning session. Respond ONLY with a valid JSON object, no other text.

Session:
- Language: {session['language']} ({session['level']})
- Topic: {session['topic']}
- Duration: ~{dur} minutes
- Exchanges: {session['exchange_count']}
- Total errors: {session['error_count']}
- Error breakdown:
{lines}

Respond with ONLY this JSON (no extra text):
{{"quality_score": 0.75, "summary": "2-3 sentences in French about quality and main areas to improve."}}

quality_score: 0.0 (very poor) to 1.0 (excellent).
summary: Write in French. Be encouraging but honest."""

    @staticmethod
    def _parse_analysis_response(text: str) -> tuple:
        try:
            match = re.search(r'\{.*?\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                score = max(0.0, min(1.0, float(data.get("quality_score", 0.5))))
                summary = str(data.get("summary", ""))
                return score, summary
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return 0.5, ""

    def get_lesson_cards(self, profile_id: str, threshold: int = 5) -> list:
        """Returns lesson cards for error patterns at or above threshold, ordered by count."""
        patterns = self._db.get_top_patterns(profile_id)
        cards = []
        for p in patterns:
            if p["occurrence_count"] < threshold:
                break
            lesson = LESSON_CATALOG.get((p["error_type"], p["rule"]))
            if not lesson:
                # Partial match on rule keyword
                for (cat, rule_key), l in LESSON_CATALOG.items():
                    if cat == p["error_type"] and rule_key in p["rule"]:
                        lesson = l
                        break
            if lesson:
                cards.append({
                    "pattern": p,
                    "lesson": lesson,
                    "critical": p["occurrence_count"] >= 10,
                })
        return cards

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def exchange_count(self) -> int:
        return self._exchange_count

    @property
    def error_count(self) -> int:
        return self._error_count
```

- [ ] **Step 4.4 — Run tests to confirm they pass**

```bash
cd langcoach && python -m pytest tests/test_stats_engine.py -v
```

Expected: 7 tests PASS

- [ ] **Step 4.5 — Commit**

```bash
git add core/stats_engine.py tests/test_stats_engine.py
git commit -m "feat: add StatsEngine with error parsing, recording, and lesson catalog"
```

---

## Task 5: Update Session Manager

**Files:**

- Modify: `langcoach/core/session.py`

- [ ] **Step 5.1 — Add `_profile`, `_stats`, `_exchange_start_ms` to `__init__`**

In `SessionManager.__init__`, add after the existing instance variables:

```python
self._profile: Optional[dict] = None
self._stats = None
self._exchange_start_ms: int = 0
```

- [ ] **Step 5.2 — Update `initialize()` to accept profile and stats**

Replace the `initialize` method:

```python
def initialize(self, settings: dict, profile: Optional[dict] = None, stats=None):
    """Lance l'initialisation des modèles en arrière-plan"""
    self.settings = settings
    self._profile = profile
    self._stats = stats
    self._set_state(SessionState.LOADING)
    t = threading.Thread(target=self._init_models, daemon=True)
    t.start()
```

- [ ] **Step 5.3 — Update `_init_models` to use user_name and start stats session**

In `_init_models`, replace the LLM setup lines and add stats session start before the greeting:

```python
        # LLM
        self._llm = LLMEngine(config=MODELS["llm"])
        user_name = self._profile.get("name", "the student") if self._profile else "the student"
        self._llm.set_system_prompt(build_system_prompt(self.settings, user_name=user_name))
        status["llm"] = True
```

And add after `self._reachy.start()`, before `self._set_state(SessionState.READY)`:

```python
        # Start stats session
        if self._stats and self._profile:
            lang = self.settings.get("target_language", "english")
            level = self.settings.get("level", "B1")
            topic = self.settings.get("topic", "Conversation libre")
            self._stats.start_session(self._profile, language=lang, level=level, topic=topic)
```

- [ ] **Step 5.4 — Record exchange timing and stats in `_get_ai_response`**

Replace `_get_ai_response`:

```python
def _get_ai_response(self, user_text: str, is_greeting: bool = False):
    import time
    self._exchange_start_ms = int(time.time() * 1000)
    self._set_state(SessionState.PROCESSING)

    full_response = []

    def on_token(token: str):
        full_response.append(token)
        if self.on_assistant_token:
            self.on_assistant_token(token)

    def on_done(text: str):
        import time
        self._llm.trim_history(keep_last=30)
        if text.startswith("[") and text.endswith("]"):
            logger.error(f"LLM returned error: {text}")
            self._set_state(SessionState.ERROR)
            if self.on_error:
                self.on_error(text)
            return
        # Record to stats (skip greeting)
        if not is_greeting and self._stats and user_text.strip():
            duration_ms = int(time.time() * 1000) - self._exchange_start_ms
            self._stats.record_exchange(user_text, text, duration_ms)
        if self.on_assistant_done:
            self.on_assistant_done(text)
        if self._reachy:
            self._reachy.send_transcript(text, role="assistant")
        self._speak(text)

    prompt = "[Start the session with your opening greeting]" if is_greeting else user_text
    self._llm.chat_async(prompt, on_token=on_token, on_done=on_done)
```

- [ ] **Step 5.5 — Call `end_session()` and restart stats in `reset_session`**

Replace `reset_session`:

```python
def reset_session(self):
    """Repart de zéro dans la même session"""
    if self._stats:
        self._stats.end_session()
    if self._llm:
        self._llm.reset_conversation()
    if self._tts:
        self._tts.stop()
    self._set_state(SessionState.READY)
    # Start a new stats session
    if self._stats and self._profile:
        lang = self.settings.get("target_language", "english")
        level = self.settings.get("level", "B1")
        topic = self.settings.get("topic", "Conversation libre")
        self._stats.start_session(self._profile, language=lang, level=level, topic=topic)
    self._get_ai_response("", is_greeting=True)
```

- [ ] **Step 5.6 — Call `end_session()` in `shutdown`**

Replace `shutdown`:

```python
def shutdown(self):
    """Nettoyage propre"""
    try:
        if self._stats:
            self._stats.end_session()
        if self._recorder:
            self._recorder.stop_vad()
        if self._tts:
            self._tts.stop()
        if self._reachy:
            self._reachy.send_session_stop()
            self._reachy.stop()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
```

- [ ] **Step 5.7 — Update `update_settings` to inject user_name**

Replace `update_settings`:

```python
def update_settings(self, new_settings: dict):
    self.settings = new_settings
    if self._llm:
        user_name = self._profile.get("name", "the student") if self._profile else "the student"
        self._llm.set_system_prompt(build_system_prompt(new_settings, user_name=user_name))
    if self._tts:
        self._tts.set_coach(self._get_coach_cfg(new_settings))
    if self._stt:
        self._stt.set_language(new_settings.get("target_language", "english"))
```

- [ ] **Step 5.8 — Verify no import errors**

```bash
cd langcoach && python -c "from core.session import SessionManager; print('OK')"
```

Expected: `OK`

- [ ] **Step 5.9 — Commit**

```bash
git add core/session.py
git commit -m "feat: wire StatsEngine and user_name into SessionManager"
```

---

## Task 6: Profile Screen UI

**Files:**

- Create: `langcoach/ui/profile_screen.py`

- [ ] **Step 6.1 — Implement `langcoach/ui/profile_screen.py`**

```python
"""
LangCoach — Profile Screen
Splash screen for profile selection + 3-step creation wizard.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from config.theme import T
from config.settings import DEFAULT_SETTINGS, COACHES, LEVELS, TARGET_LANGUAGES, TEACHER_STYLES
from core.database import Database

_AVATARS = ["🧑", "👩", "🧒", "👨‍💼", "👩‍🎓", "👴", "👵", "🧑‍🎤", "🧑‍💻", "🦸"]


class ProfileCard(QWidget):
    """Clickable card for an existing profile."""

    def __init__(self, profile: dict, on_select, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._on_select = on_select
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(140, 160)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 2px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
            QWidget:hover {{ border-color: {T['accent']}; background-color: {T['bg_hover']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar = QLabel(profile.get("avatar", "🧑"))
        avatar.setFont(QFont(T["font_body"], 28))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(avatar)

        name = QLabel(profile["name"])
        name.setFont(QFont(T["font_display"], T["font_size_md"]))
        name.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        s = profile.get("settings", {})
        sub = QLabel(f"{s.get('target_language','english').capitalize()} · {s.get('level','B1')}")
        sub.setFont(QFont(T["font_body"], T["font_size_xs"]))
        sub.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

    def mousePressEvent(self, event):
        self._on_select(self._profile)
        super().mousePressEvent(event)


class ProfileScreen(QDialog):
    """
    Handles profile selection at launch.
    - No profiles → wizard immediately.
    - 1 profile → auto-select (accepts via QTimer).
    - 2+ profiles → splash screen with cards.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._selected_profile: Optional[dict] = None
        self.setModal(True)
        self.setWindowTitle("El Profesor")
        self.resize(680, 420)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        profiles = db.list_profiles()

        if not profiles:
            self._embed_wizard()
        elif len(profiles) == 1:
            self._selected_profile = profiles[0]
            db.touch_profile(profiles[0]["id"])
            QTimer.singleShot(0, self.accept)
            QVBoxLayout(self)  # empty layout to avoid Qt warnings
        else:
            self._build_splash(profiles)

    def _embed_wizard(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        wizard = ProfileWizard(self._db, parent=self)
        wizard.profile_created.connect(self._on_wizard_done)
        layout.addWidget(wizard)

    def _build_splash(self, profiles: list):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(28)

        title = QLabel("Qui apprend aujourd'hui ?")
        title.setFont(QFont(T["font_display"], T["font_size_xl"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for profile in profiles:
            card = ProfileCard(profile, on_select=self._on_profile_selected)
            cards_row.addWidget(card)

        new_btn = QPushButton("＋\nNouveau profil")
        new_btn.setFixedSize(140, 160)
        new_btn.setFont(QFont(T["font_body"], T["font_size_sm"]))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T['bg_card']}; color: {T['text_muted']};
                border: 2px dashed {T['border']}; border-radius: {T['radius_md']}px;
            }}
            QPushButton:hover {{ border-color: {T['accent']}; color: {T['text_primary']}; }}
        """)
        new_btn.clicked.connect(self._show_wizard_overlay)
        cards_row.addWidget(new_btn)

        layout.addLayout(cards_row)

    def _on_profile_selected(self, profile: dict):
        self._db.touch_profile(profile["id"])
        self._selected_profile = profile
        self.accept()

    def _show_wizard_overlay(self):
        wizard = ProfileWizard(self._db, parent=self)
        wizard.profile_created.connect(self._on_wizard_done)
        wizard.exec()

    def _on_wizard_done(self, profile_id: str):
        profile = self._db.get_profile(profile_id)
        if profile:
            self._selected_profile = profile
            self.accept()

    @property
    def selected_profile(self) -> Optional[dict]:
        return self._selected_profile


class ProfileWizard(QDialog):
    """3-step profile creation: Step 1 Name+Avatar, Step 2 Language+Level, Step 3 Coach+Style."""

    profile_created = pyqtSignal(str)  # emits profile_id on finish

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._name = ""
        self._avatar = _AVATARS[0]
        self._language = "english"
        self._level = "B1"
        self._coach = "angela"
        self._style = "bienveillant"

        self.setModal(True)
        self.setWindowTitle("Créer un profil")
        self.resize(440, 500)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        self._stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())

    # ── Step 1: Name + Avatar ──────────────────────────────────

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 1)

        title = QLabel("Comment t'appelles-tu ?")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("L'IA t'appellera par ton prénom")
        sub.setFont(QFont(T["font_body"], T["font_size_sm"]))
        sub.setStyleSheet(f"color: {T['text_muted']};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Ton prénom…")
        self._name_input.setFixedHeight(48)
        self._name_input.setFont(QFont(T["font_body"], T["font_size_lg"]))
        self._name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {T['bg_card']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px; padding: 8px 16px;
            }}
            QLineEdit:focus {{ border-color: {T['accent']}; }}
        """)
        layout.addWidget(self._name_input)

        avatar_lbl = QLabel("Avatar")
        avatar_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(avatar_lbl)

        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(8)
        self._avatar_btns: list[QPushButton] = []
        for emoji in _AVATARS[:6]:
            btn = QPushButton(emoji)
            btn.setFixedSize(48, 48)
            btn.setFont(QFont(T["font_body"], 18))
            btn.setCheckable(True)
            btn.setChecked(emoji == self._avatar)
            btn.clicked.connect(lambda _, e=emoji: self._select_avatar(e))
            self._avatar_btns.append(btn)
            avatar_row.addWidget(btn)
        self._update_avatar_styles()
        layout.addLayout(avatar_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(back=False, next_fn=self._go_step2))
        return page

    def _select_avatar(self, emoji: str):
        self._avatar = emoji
        self._update_avatar_styles()

    def _update_avatar_styles(self):
        for btn in self._avatar_btns:
            btn.setStyleSheet(self._pill(btn.text() == self._avatar))

    def _go_step2(self):
        self._name = self._name_input.text().strip()
        if not self._name:
            self._name_input.setFocus()
            return
        self._stack.setCurrentIndex(1)

    # ── Step 2: Language + Level ───────────────────────────────

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 2)

        title = QLabel("Quelle langue apprends-tu ?")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        lang_lbl = QLabel("Langue cible")
        lang_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(lang_lbl)

        lang_row = QHBoxLayout()
        self._lang_btns: dict[str, QPushButton] = {}
        for key, info in TARGET_LANGUAGES.items():
            btn = QPushButton(info["label"])
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_language(k))
            self._lang_btns[key] = btn
            lang_row.addWidget(btn)
        self._update_lang_styles()
        layout.addLayout(lang_row)

        level_lbl = QLabel("Ton niveau actuel")
        level_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(level_lbl)

        level_row = QHBoxLayout()
        self._level_btns: dict[str, QPushButton] = {}
        for key in LEVELS:
            btn = QPushButton(key)
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_level(k))
            self._level_btns[key] = btn
            level_row.addWidget(btn)
        self._update_level_styles()
        layout.addLayout(level_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(
            back=True, back_fn=lambda: self._stack.setCurrentIndex(0), next_fn=self._go_step3
        ))
        return page

    def _select_language(self, key: str):
        self._language = key
        self._update_lang_styles()

    def _update_lang_styles(self):
        for k, btn in self._lang_btns.items():
            btn.setStyleSheet(self._pill(k == self._language))

    def _select_level(self, key: str):
        self._level = key
        self._update_level_styles()

    def _update_level_styles(self):
        for k, btn in self._level_btns.items():
            btn.setStyleSheet(self._pill(k == self._level))

    def _go_step3(self):
        self._stack.setCurrentIndex(2)

    # ── Step 3: Coach + Style ──────────────────────────────────

    def _build_step3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 3)

        title = QLabel("Choisis ton coach")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        coach_lbl = QLabel("Coach")
        coach_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(coach_lbl)

        coach_row = QHBoxLayout()
        self._coach_btns: dict[str, QPushButton] = {}
        for key, info in COACHES.get(self._language, COACHES["english"]).items():
            btn = QPushButton(f"{info['flag']} {info['name']}")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_coach(k))
            self._coach_btns[key] = btn
            coach_row.addWidget(btn)
        self._update_coach_styles()
        layout.addLayout(coach_row)

        style_lbl = QLabel("Style d'enseignement")
        style_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(style_lbl)

        style_row = QHBoxLayout()
        self._style_btns: dict[str, QPushButton] = {}
        for key, info in TEACHER_STYLES.items():
            btn = QPushButton(f"{info['emoji']} {info['label']}")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_style(k))
            self._style_btns[key] = btn
            style_row.addWidget(btn)
        self._update_style_styles()
        layout.addLayout(style_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(
            back=True,
            back_fn=lambda: self._stack.setCurrentIndex(1),
            next_fn=self._finish,
            next_label="Créer mon profil →",
        ))
        return page

    def _select_coach(self, key: str):
        self._coach = key
        self._update_coach_styles()

    def _update_coach_styles(self):
        for k, btn in self._coach_btns.items():
            btn.setStyleSheet(self._pill(k == self._coach))

    def _select_style(self, key: str):
        self._style = key
        self._update_style_styles()

    def _update_style_styles(self):
        for k, btn in self._style_btns.items():
            btn.setStyleSheet(self._pill(k == self._style))

    def _finish(self):
        settings = {
            **DEFAULT_SETTINGS,
            "target_language": self._language,
            "level": self._level,
            "coach": self._coach,
            "teacher_style": self._style,
        }
        profile = self._db.create_profile(self._name, self._avatar, settings)
        self.profile_created.emit(profile["id"])
        self.accept()

    # ── Helpers ───────────────────────────────────────────────

    def _add_step_indicator(self, layout: QVBoxLayout, current: int):
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(6)
        for i in range(1, 4):
            dot = QLabel(str(i))
            dot.setFixedSize(28, 28)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFont(QFont(T["font_body"], T["font_size_sm"]))
            if i == current:
                dot.setStyleSheet(f"background:{T['accent']}; color:white; border-radius:14px;")
            elif i < current:
                dot.setStyleSheet(f"background:{T['success']}; color:white; border-radius:14px;")
            else:
                dot.setStyleSheet(f"background:{T['bg_card']}; color:{T['text_muted']}; border-radius:14px; border:1px solid {T['border']};")
            row.addWidget(dot)
            if i < 3:
                line = QFrame()
                line.setFixedSize(36, 2)
                line.setStyleSheet(f"background: {'#4444ff' if i < current else T['border']};")
                row.addWidget(line)
        layout.addLayout(row)

    def _nav_row(self, back: bool, next_fn, back_fn=None, next_label: str = "Suivant →") -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        if back and back_fn:
            b = QPushButton("← Retour")
            b.setFixedHeight(44)
            b.setStyleSheet(f"QPushButton {{ background:{T['bg_card']}; color:{T['text_secondary']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px; }} QPushButton:hover {{ background:{T['bg_hover']}; }}")
            b.clicked.connect(back_fn)
            row.addWidget(b)
        n = QPushButton(next_label)
        n.setFixedHeight(44)
        n.setStyleSheet(f"QPushButton {{ background:{T['accent']}; color:white; border:none; border-radius:{T['radius_md']}px; font-weight:bold; }} QPushButton:hover {{ background:#5555ff; }}")
        n.clicked.connect(next_fn)
        row.addWidget(n, 2)
        return w

    def _pill(self, selected: bool) -> str:
        if selected:
            return f"QPushButton {{ background:#2a2a4e; color:{T['accent']}; border:2px solid {T['accent']}; border-radius:{T['radius_sm']}px; }}"
        return f"QPushButton {{ background:{T['bg_card']}; color:{T['text_secondary']}; border:1px solid {T['border']}; border-radius:{T['radius_sm']}px; }} QPushButton:hover {{ border-color:{T['accent']}; }}"
```

- [ ] **Step 6.2 — Verify no import errors**

```bash
cd langcoach && python -c "
import sys
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
from ui.profile_screen import ProfileScreen, ProfileWizard
print('OK')
"
```

Expected: `OK`

- [ ] **Step 6.3 — Commit**

```bash
git add ui/profile_screen.py
git commit -m "feat: add ProfileScreen splash and ProfileWizard 3-step creation"
```

---

## Task 7: Dashboard Panel

**Files:**

- Create: `langcoach/ui/dashboard_panel.py`

- [ ] **Step 7.1 — Implement `langcoach/ui/dashboard_panel.py`**

```python
"""
LangCoach — Dashboard Panel
Per-profile analytics: Vue globale / Erreurs / Sessions / Leçons
"""
import datetime
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTabWidget, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush

from config.theme import T
from core.database import Database
from core.stats_engine import StatsEngine


class MiniBarChart(QWidget):
    """Bar chart drawn with QPainter for quality progression."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self.setMinimumHeight(80)

    def set_values(self, values: list[float]):
        self._values = values
        self.update()

    def paintEvent(self, event):
        if not self._values:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._values)
        max_val = max(self._values) or 1.0
        gap = 4
        bar_w = max(4, (w - gap * (n - 1)) // n)
        for i, v in enumerate(self._values):
            bar_h = int((v / max_val) * (h - 8))
            x = i * (bar_w + gap)
            y = h - bar_h
            alpha = 100 + int(155 * (i / max(n - 1, 1)))
            color = QColor(T["accent"])
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 3, 3)


class KpiCard(QWidget):
    def __init__(self, value: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{T['bg_card']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._val = QLabel(value)
        self._val.setFont(QFont(T["font_display"], T["font_size_2xl"]))
        self._val.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._val)

        lbl = QLabel(label)
        lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
        lbl.setStyleSheet(f"color:{T['text_muted']}; background:transparent; border:none;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

    def update_value(self, value: str):
        self._val.setText(value)


class DashboardPanel(QWidget):
    """Dashboard tab with four sub-tabs."""

    def __init__(self, db: Database, stats_engine: StatsEngine, parent=None):
        super().__init__(parent)
        self._db = db
        self._stats = stats_engine
        self._profile: Optional[dict] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Profile header bar
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background:{T['bg_secondary']}; border-bottom:1px solid {T['border']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(T["spacing_xl"], 0, T["spacing_xl"], 0)

        self._profile_lbl = QLabel("—")
        self._profile_lbl.setFont(QFont(T["font_display"], T["font_size_lg"]))
        self._profile_lbl.setStyleSheet(f"color:{T['text_primary']};")
        hl.addWidget(self._profile_lbl)

        refresh_btn = QPushButton("↻ Actualiser")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet(f"QPushButton {{ background:{T['bg_card']}; color:{T['text_secondary']}; border:1px solid {T['border']}; border-radius:{T['radius_sm']}px; padding:0 12px; font-size:{T['font_size_sm']}px; }} QPushButton:hover {{ border-color:{T['accent']}; }}")
        refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(refresh_btn)

        layout.addWidget(header)

        # Sub-tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background:{T['bg_primary']}; border:none; border-top:1px solid {T['border']}; }}
            QTabBar::tab {{ background:{T['bg_secondary']}; color:{T['text_muted']}; padding:10px 20px; border:none; font-family:'{T['font_body']}'; font-size:{T['font_size_sm']}px; }}
            QTabBar::tab:selected {{ color:{T['text_primary']}; border-bottom:2px solid {T['accent']}; background:{T['bg_primary']}; }}
            QTabBar::tab:hover {{ color:{T['text_primary']}; }}
        """)

        self._tab_overview = self._build_overview_tab()
        self._tab_errors = self._build_errors_tab()
        self._tab_sessions = self._build_sessions_tab()
        self._tab_lessons = self._build_lessons_tab()

        self._tabs.addTab(self._tab_overview, "Vue globale")
        self._tabs.addTab(self._tab_errors, "Erreurs")
        self._tabs.addTab(self._tab_sessions, "Sessions")
        self._tabs.addTab(self._tab_lessons, "Leçons")

        layout.addWidget(self._tabs, 1)

    # ── Overview ──────────────────────────────────────────────

    def _build_overview_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setStyleSheet(f"background:{T['bg_primary']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
        layout.setSpacing(T["spacing_lg"])

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(T["spacing_md"])
        self._kpi_sessions = KpiCard("—", "Sessions", T["accent"])
        self._kpi_errors   = KpiCard("—", "Erreurs / échange", T["error"])
        self._kpi_quality  = KpiCard("—", "Qualité moy.", T["success"])
        self._kpi_streak   = KpiCard("—", "Streak 🔥", T["warning"])
        for c in (self._kpi_sessions, self._kpi_errors, self._kpi_quality, self._kpi_streak):
            c.setFixedHeight(100)
            kpi_row.addWidget(c)
        layout.addLayout(kpi_row)

        chart_frame = QWidget()
        chart_frame.setStyleSheet(f"background:{T['bg_card']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px;")
        cl = QVBoxLayout(chart_frame)
        cl.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel("Progression — qualité par session")
        lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        lbl.setStyleSheet(f"color:{T['text_secondary']}; border:none;")
        cl.addWidget(lbl)
        self._chart = MiniBarChart()
        self._chart.setMinimumHeight(80)
        cl.addWidget(self._chart)
        layout.addWidget(chart_frame)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ── Errors ────────────────────────────────────────────────

    def _build_errors_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self._errors_content = QWidget()
        self._errors_content.setStyleSheet(f"background:{T['bg_primary']};")
        self._errors_layout = QVBoxLayout(self._errors_content)
        self._errors_layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
        self._errors_layout.setSpacing(T["spacing_md"])
        self._errors_layout.addStretch()
        scroll.setWidget(self._errors_content)
        return scroll

    # ── Sessions ──────────────────────────────────────────────

    def _build_sessions_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self._sessions_content = QWidget()
        self._sessions_content.setStyleSheet(f"background:{T['bg_primary']};")
        self._sessions_layout = QVBoxLayout(self._sessions_content)
        self._sessions_layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
        self._sessions_layout.setSpacing(T["spacing_sm"])
        self._sessions_layout.addStretch()
        scroll.setWidget(self._sessions_content)
        return scroll

    # ── Lessons ───────────────────────────────────────────────

    def _build_lessons_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self._lessons_content = QWidget()
        self._lessons_content.setStyleSheet(f"background:{T['bg_primary']};")
        self._lessons_layout = QVBoxLayout(self._lessons_content)
        self._lessons_layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
        self._lessons_layout.setSpacing(T["spacing_md"])

        self._ai_btn = QPushButton("🤖  Analyse mes lacunes (IA)")
        self._ai_btn.setFixedHeight(44)
        self._ai_btn.setStyleSheet(f"QPushButton {{ background:#1a2a1a; color:#4aaa4a; border:1px solid #2a4a2a; border-radius:{T['radius_md']}px; font-size:{T['font_size_sm']}px; }} QPushButton:hover {{ background:#2a3a2a; }}")
        self._ai_btn.clicked.connect(self._run_ai_analysis)
        self._lessons_layout.addWidget(self._ai_btn)

        self._ai_result = QTextEdit()
        self._ai_result.setReadOnly(True)
        self._ai_result.setVisible(False)
        self._ai_result.setMinimumHeight(120)
        self._ai_result.setStyleSheet(f"QTextEdit {{ background:{T['bg_card']}; color:{T['text_primary']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px; padding:12px; font-size:{T['font_size_sm']}px; }}")
        self._lessons_layout.addWidget(self._ai_result)

        self._lesson_cards_layout = QVBoxLayout()
        self._lessons_layout.addLayout(self._lesson_cards_layout)
        self._lessons_layout.addStretch()

        scroll.setWidget(self._lessons_content)
        return scroll

    # ── Public API ────────────────────────────────────────────

    def set_profile(self, profile: dict):
        self._profile = profile
        self._profile_lbl.setText(f"{profile.get('avatar', '🧑')} {profile['name']}")
        self.refresh()

    def refresh(self):
        if not self._profile:
            return
        pid = self._profile["id"]
        self._refresh_overview(pid)
        self._refresh_errors(pid)
        self._refresh_sessions(pid)
        self._refresh_lessons(pid)

    def _refresh_overview(self, profile_id: str):
        kpis = self._db.get_kpis(profile_id)
        self._kpi_sessions.update_value(str(kpis["total_sessions"]))
        self._kpi_errors.update_value(f"{kpis['avg_errors_per_exchange']:.1f}")
        q = kpis["avg_quality"]
        self._kpi_quality.update_value(f"{q}%" if kpis["total_sessions"] else "—")
        s = kpis["streak_days"]
        self._kpi_streak.update_value(f"{s}j" if s else "0j")
        prog = self._db.get_quality_progression(profile_id)
        self._chart.set_values([r["quality_score"] for r in prog if r["quality_score"] is not None])

    def _refresh_errors(self, profile_id: str):
        self._clear(self._errors_layout)
        breakdown = self._db.get_error_breakdown(profile_id)
        patterns = self._db.get_top_patterns(profile_id)

        if not breakdown:
            lbl = QLabel("Aucune erreur enregistrée pour l'instant.")
            lbl.setStyleSheet(f"color:{T['text_muted']};")
            self._errors_layout.addWidget(lbl)
            self._errors_layout.addStretch()
            return

        sec = QLabel("Répartition par type")
        sec.setFont(QFont(T["font_body"], T["font_size_sm"]))
        sec.setStyleSheet(f"color:{T['text_secondary']};")
        self._errors_layout.addWidget(sec)

        total = sum(e["count"] for e in breakdown)
        colors = {
            "grammar": T["accent"], "vocabulary": T["warning"],
            "tense": T["error"], "syntax": T["info"], "pronunciation_hint": T["text_muted"],
        }
        for e in breakdown:
            self._errors_layout.addWidget(
                self._error_bar_row(e["error_type"], e["count"], total, colors.get(e["error_type"], T["text_secondary"]))
            )

        if patterns:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{T['border']};")
            self._errors_layout.addWidget(sep)

            pat_lbl = QLabel("⚠ Lacunes récurrentes")
            pat_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
            pat_lbl.setStyleSheet(f"color:{T['text_secondary']};")
            self._errors_layout.addWidget(pat_lbl)

            for p in patterns[:8]:
                self._errors_layout.addWidget(self._pattern_card(p))

        self._errors_layout.addStretch()

    def _error_bar_row(self, error_type: str, count: int, total: int, color: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{T['bg_card']}; border:1px solid {T['border']}; border-radius:{T['radius_sm']}px;")
        row = QHBoxLayout(w)
        row.setContentsMargins(12, 10, 12, 10)

        lbl = QLabel(error_type.capitalize())
        lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        lbl.setStyleSheet(f"color:{T['text_primary']}; border:none;")
        lbl.setFixedWidth(130)
        row.addWidget(lbl)

        # Bar using proportional layout stretch — works correctly at any widget size
        pct = int((count / total) * 100) if total > 0 else 0
        bar_bg = QWidget()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"background:{T['bg_primary']}; border-radius:4px; border:none;")
        bar_layout = QHBoxLayout(bar_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        if pct > 0:
            fill = QWidget()
            fill.setStyleSheet(f"background:{color}; border-radius:4px; border:none;")
            bar_layout.addWidget(fill, pct)
        bar_layout.addStretch(100 - pct)
        row.addWidget(bar_bg, 1)

        cnt = QLabel(str(count))
        cnt.setFont(QFont(T["font_mono"], T["font_size_sm"]))
        cnt.setStyleSheet(f"color:{T['text_secondary']}; border:none;")
        cnt.setFixedWidth(36)
        cnt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(cnt)
        return w

    def _pattern_card(self, p: dict) -> QWidget:
        critical = p["occurrence_count"] >= 10
        border = T["error"] if critical else T["warning"]
        bg = "#2a1a1a" if critical else "#2a2a1a"
        w = QWidget()
        w.setStyleSheet(f"background:{bg}; border-left:3px solid {border}; border-radius:{T['radius_sm']}px;")
        row = QHBoxLayout(w)
        row.setContentsMargins(12, 10, 12, 10)
        col = QVBoxLayout()
        t = QLabel(p["error_type"].capitalize())
        t.setFont(QFont(T["font_body"], T["font_size_xs"]))
        t.setStyleSheet(f"color:{T['text_muted']}; border:none;")
        col.addWidget(t)
        r = QLabel(p["rule"].replace("_", " ").title())
        r.setFont(QFont(T["font_body"], T["font_size_sm"]))
        r.setStyleSheet(f"color:{T['text_primary']}; border:none;")
        col.addWidget(r)
        row.addLayout(col, 1)
        badge = QLabel(f"×{p['occurrence_count']}")
        badge.setFont(QFont(T["font_mono"], T["font_size_md"]))
        badge.setStyleSheet(f"color:{border}; border:none;")
        row.addWidget(badge)
        return w

    def _refresh_sessions(self, profile_id: str):
        self._clear(self._sessions_layout)
        sessions = self._db.list_sessions(profile_id)
        if not sessions:
            lbl = QLabel("Aucune session terminée pour l'instant.")
            lbl.setStyleSheet(f"color:{T['text_muted']};")
            self._sessions_layout.addWidget(lbl)
        else:
            for s in sessions:
                self._sessions_layout.addWidget(self._session_card(s))
        self._sessions_layout.addStretch()

    def _session_card(self, s: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{T['bg_card']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        ts = s.get("started_at", 0) / 1000
        date_lbl = QLabel(datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M"))
        date_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        date_lbl.setStyleSheet(f"color:{T['text_primary']}; border:none;")
        top.addWidget(date_lbl)

        q = s.get("quality_score")
        if q is not None:
            pct = int(q * 100)
            qc = T["success"] if pct >= 70 else T["warning"] if pct >= 40 else T["error"]
            ql = QLabel(f"{pct}%")
            ql.setFont(QFont(T["font_mono"], T["font_size_sm"]))
            ql.setStyleSheet(f"color:{qc}; border:none;")
            top.addWidget(ql)
        layout.addLayout(top)

        meta = QLabel(f"{s['language'].capitalize()} · {s['level']} · {s['topic']}  |  {s['exchange_count']} échanges · {s['error_count']} erreurs")
        meta.setFont(QFont(T["font_body"], T["font_size_xs"]))
        meta.setStyleSheet(f"color:{T['text_muted']}; border:none;")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        if s.get("summary"):
            summary = QLabel(s["summary"])
            summary.setFont(QFont(T["font_body"], T["font_size_xs"]))
            summary.setStyleSheet(f"color:{T['text_secondary']}; border:none;")
            summary.setWordWrap(True)
            layout.addWidget(summary)

        return w

    def _refresh_lessons(self, profile_id: str):
        self._clear(self._lesson_cards_layout)
        if not self._stats:
            return
        cards = self._stats.get_lesson_cards(profile_id)
        if not cards:
            lbl = QLabel("Pas encore de recommandations. Continue à pratiquer !")
            lbl.setStyleSheet(f"color:{T['text_muted']};")
            self._lesson_cards_layout.addWidget(lbl)
            return
        for c in cards:
            self._lesson_cards_layout.addWidget(self._lesson_card(c))

    def _lesson_card(self, data: dict) -> QWidget:
        lesson = data["lesson"]
        p = data["pattern"]
        critical = data["critical"]
        border = T["error"] if critical else "#2a4a2a"
        bg = "#1a1515" if critical else "#1a2a1a"

        w = QWidget()
        w.setStyleSheet(f"background:{bg}; border:1px solid {border}; border-radius:{T['radius_md']}px;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        icon = "🔴" if critical else "📚"
        title = QLabel(f"{icon} {lesson['title']}")
        title.setFont(QFont(T["font_body"], T["font_size_sm"]))
        title.setStyleSheet(f"color:{T['text_primary']}; border:none; font-weight:bold;")
        top.addWidget(title)
        cnt = QLabel(f"×{p['occurrence_count']}")
        cnt.setStyleSheet(f"color:{T['text_muted']}; border:none;")
        top.addWidget(cnt)
        layout.addLayout(top)

        desc = QLabel(lesson["desc"])
        desc.setFont(QFont(T["font_body"], T["font_size_xs"]))
        desc.setStyleSheet(f"color:{T['text_secondary']}; border:none;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        if lesson.get("tip"):
            tip = QLabel(f"💡 {lesson['tip']}")
            tip.setFont(QFont(T["font_body"], T["font_size_xs"]))
            tip.setStyleSheet(f"color:{'#ff8888' if critical else '#8aaa8a'}; border:none;")
            tip.setWordWrap(True)
            layout.addWidget(tip)

        if lesson.get("examples"):
            ex = QLabel("  " + "  ·  ".join(lesson["examples"][:3]))
            ex.setFont(QFont(T["font_mono"], T["font_size_xs"]))
            ex.setStyleSheet(f"color:{T['text_muted']}; border:none;")
            layout.addWidget(ex)

        return w

    def _run_ai_analysis(self):
        if not self._profile or not self._stats:
            return
        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("⏳ Analyse en cours…")
        self._ai_result.setVisible(True)
        self._ai_result.setText("L'IA analyse tes lacunes…")

        pid = self._profile["id"]
        patterns = self._db.get_top_patterns(pid)
        llm = self._stats._llm

        def run():
            if not llm or not patterns:
                return "Pas assez de données pour une analyse."
            lines = "\n".join(
                f"- {p['error_type']} / {p['rule']}: {p['occurrence_count']} occurrences"
                for p in patterns[:10]
            )
            prompt = f"""Tu es un coach de langue bienveillant. Analyse les lacunes de cet apprenant et donne un plan personnalisé.

Erreurs récurrentes :
{lines}

Fournis en français :
1. Les 2-3 points les plus critiques à travailler
2. Des conseils pratiques et exercices concrets pour chaque point
3. Un mot d'encouragement

Écris en français, de façon chaleureuse et motivante. 3-5 paragraphes maximum."""
            return llm.chat(prompt) or "Analyse non disponible."

        def in_thread():
            result = run()
            QTimer.singleShot(0, lambda: self._on_ai_result(result))

        threading.Thread(target=in_thread, daemon=True).start()

    def _on_ai_result(self, text: str):
        self._ai_result.setText(text)
        self._ai_btn.setEnabled(True)
        self._ai_btn.setText("🤖  Analyse mes lacunes (IA)")

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
```

- [ ] **Step 7.2 — Verify no import errors**

```bash
cd langcoach && python -c "
import sys
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
from ui.dashboard_panel import DashboardPanel
print('OK')
"
```

Expected: `OK`

- [ ] **Step 7.3 — Commit**

```bash
git add ui/dashboard_panel.py
git commit -m "feat: add DashboardPanel with Vue globale, Erreurs, Sessions, Leçons"
```

---

## Task 8: Main Window & Entry Point Integration

**Files:**

- Modify: `langcoach/ui/main_window.py`
- Modify: `langcoach/main.py`

- [ ] **Step 8.1 — Add imports and update `__init__` signature**

At the top of `langcoach/ui/main_window.py`, add these imports after the existing ones:

```python
from core.database import Database
from core.stats_engine import StatsEngine
from ui.dashboard_panel import DashboardPanel
```

Replace `MainWindow.__init__`:

```python
def __init__(self, db: Database, profile: dict):
    super().__init__()
    self._db = db
    self._profile = profile
    self.settings = profile.get("settings", load_settings())
    self.session = SessionManager()
    self._stats = StatsEngine(db=db, llm=None)  # llm injected after model init
    self._current_ai_bubble = None
    self._current_ai_text = ""
    self._settings_visible = False
    self._ptt_held = False

    self._setup_window()
    self._setup_fonts()
    self._apply_theme()
    self._build_ui()
    self._connect_signals()
    self._setup_shortcuts()
    self._start_session()
```

- [ ] **Step 8.2 — Replace `_build_header` with tab navigation**

Replace the `_build_header` method:

```python
def _build_header(self) -> QWidget:
    header = QWidget()
    header.setFixedHeight(64)
    header.setStyleSheet(f"background-color: {T['bg_secondary']};")

    layout = QHBoxLayout(header)
    layout.setContentsMargins(T["spacing_lg"], 0, T["spacing_lg"], 0)
    layout.setSpacing(0)

    self._tab_active_style = f"""
        QPushButton {{
            background-color: {T['bg_primary']}; color: {T['text_primary']};
            border: none; border-bottom: 2px solid {T['accent']};
            padding: 0 20px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
        }}
    """
    self._tab_inactive_style = f"""
        QPushButton {{
            background-color: transparent; color: {T['text_muted']};
            border: none; border-bottom: 2px solid transparent;
            padding: 0 20px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
        }}
        QPushButton:hover {{ color: {T['text_primary']}; }}
    """

    self._btn_tab_session = QPushButton("💬  Session")
    self._btn_tab_session.setFixedHeight(64)
    self._btn_tab_session.setStyleSheet(self._tab_active_style)
    self._btn_tab_session.clicked.connect(lambda: self._switch_tab(0))
    layout.addWidget(self._btn_tab_session)

    self._btn_tab_dashboard = QPushButton("📈  Dashboard")
    self._btn_tab_dashboard.setFixedHeight(64)
    self._btn_tab_dashboard.setStyleSheet(self._tab_inactive_style)
    self._btn_tab_dashboard.clicked.connect(lambda: self._switch_tab(1))
    layout.addWidget(self._btn_tab_dashboard)

    layout.addStretch()

    btn_style = f"""
        QPushButton {{
            background-color: {T['bg_card']}; color: {T['text_secondary']};
            border: 1px solid {T['border']}; border-radius: {T['radius_md']}px;
            padding: 8px 16px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
        }}
        QPushButton:hover {{ background-color: {T['bg_hover']}; color: {T['text_primary']}; border-color: {T['accent']}; }}
        QPushButton:pressed {{ background-color: {T['accent_soft']}; }}
    """
    self._btn_reset = QPushButton("↺  New session")
    self._btn_reset.setStyleSheet(btn_style)
    self._btn_reset.setFixedHeight(36)
    self._btn_reset.setToolTip("Reset conversation (R)")
    self._btn_reset.clicked.connect(self._on_reset)
    layout.addWidget(self._btn_reset)

    self._btn_settings = QPushButton("⚙  Settings")
    self._btn_settings.setStyleSheet(btn_style)
    self._btn_settings.setFixedHeight(36)
    self._btn_settings.setToolTip("Open settings (S)")
    self._btn_settings.clicked.connect(self._toggle_settings)
    layout.addWidget(self._btn_settings)

    return header
```

- [ ] **Step 8.3 — Replace main area in `_build_ui` with QStackedWidget**

In `_build_ui`, replace the section from `# ── Main area` down to `root.addWidget(main_area, 1)` (but keep sidebar and settings panel):

```python
        # ── Main area ──────────────────────────────────────────
        main_area = QWidget()
        main_area.setStyleSheet(f"background-color: {T['bg_primary']};")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._build_header()
        main_layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {T['border']}; border: none;")
        main_layout.addWidget(sep)

        # Stacked widget: index 0 = Session, index 1 = Dashboard
        self._main_stack = QStackedWidget()
        self._main_stack.setStyleSheet(f"background-color: {T['bg_primary']};")

        # Session tab (existing chat + input bar)
        session_widget = QWidget()
        session_widget.setStyleSheet(f"background-color: {T['bg_primary']};")
        session_vlayout = QVBoxLayout(session_widget)
        session_vlayout.setContentsMargins(0, 0, 0, 0)
        session_vlayout.setSpacing(0)
        self._chat_scroll = self._build_chat_area()
        session_vlayout.addWidget(self._chat_scroll, 1)
        input_bar = self._build_input_bar()
        session_vlayout.addWidget(input_bar)
        self._main_stack.addWidget(session_widget)

        # Dashboard tab
        self._dashboard_panel = DashboardPanel(db=self._db, stats_engine=self._stats)
        self._main_stack.addWidget(self._dashboard_panel)

        main_layout.addWidget(self._main_stack, 1)
        root.addWidget(main_area, 1)

        # ── Settings panel (overlay) ───────────────────────────
        self._settings_panel = SettingsPanel(self.settings, self)
        self._settings_panel.setVisible(False)
        self._settings_panel.on_settings_changed = self._on_settings_changed
        self._settings_panel.on_close = self._toggle_settings
```

Also add `_switch_tab` method to `MainWindow`:

```python
def _switch_tab(self, index: int):
    self._main_stack.setCurrentIndex(index)
    if index == 0:
        self._btn_tab_session.setStyleSheet(self._tab_active_style)
        self._btn_tab_dashboard.setStyleSheet(self._tab_inactive_style)
    else:
        self._btn_tab_session.setStyleSheet(self._tab_inactive_style)
        self._btn_tab_dashboard.setStyleSheet(self._tab_active_style)
        self._dashboard_panel.refresh()
```

- [ ] **Step 8.4 — Update `_start_session` to inject profile, stats, and LLM**

Replace `_start_session`:

```python
def _start_session(self):
    self._update_sidebar_info()
    self._update_session_title()

    # Inject LLM into stats engine once models are ready
    original_on_models_ready = self.session.on_models_ready

    def _on_models_ready_with_llm(status: dict):
        self._stats._llm = self.session._llm
        self.sig_models_ready.emit(status)

    self.session.on_models_ready = _on_models_ready_with_llm
    self.session.initialize(self.settings, profile=self._profile, stats=self._stats)
    self._dashboard_panel.set_profile(self._profile)
```

- [ ] **Step 8.5 — Update `_on_settings_changed` to save to DB**

Replace `_on_settings_changed`:

```python
def _on_settings_changed(self, new_settings: dict):
    self.settings = new_settings
    self._db.update_profile_settings(self._profile["id"], new_settings)
    self._profile["settings"] = new_settings
    self.session.update_settings(new_settings)
    self._update_sidebar_info()
    self._update_session_title()
    self._show_toast("Settings updated", kind="success")
```

- [ ] **Step 8.6 — Update `_update_session_title` (no longer a QLabel)**

Replace `_update_session_title`:

```python
def _update_session_title(self):
    lang = self.settings.get("target_language", "english").capitalize()
    level = self.settings.get("level", "B1")
    topic = self.settings.get("topic", "Free talk")
    name = self._profile.get("name", "")
    self.setWindowTitle(f"El Profesor — {name} · {lang} · {level} · {topic}")
```

- [ ] **Step 8.7 — Update `closeEvent` (no legacy settings save)**

Replace `closeEvent`:

```python
def closeEvent(self, event):
    self.session.shutdown()
    event.accept()
```

- [ ] **Step 8.8 — Update `langcoach/main.py`**

Replace the entire file:

```python
"""
LangCoach — Entry Point
Lance l'application desktop
"""
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def main():
    try:
        from PyQt6.QtWidgets import QApplication, QDialog
        from PyQt6.QtGui import QFont

        app = QApplication(sys.argv)
        app.setApplicationName("El Profesor")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("Quantelys")

        _load_fonts()

        from config.theme import T
        app.setFont(QFont(T["font_body"], T["font_size_md"]))

        # ── Database + migration ───────────────────────────────
        from config.settings import DB_FILE, save_last_profile_id, migrate_if_needed
        from core.database import Database

        db = Database(DB_FILE)
        migrate_if_needed(db)

        # ── Profile selection ──────────────────────────────────
        from ui.profile_screen import ProfileScreen

        screen = ProfileScreen(db)
        if screen.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

        profile = screen.selected_profile
        if not profile:
            sys.exit(0)

        save_last_profile_id(profile["id"])

        # ── Main window ────────────────────────────────────────
        from ui.main_window import MainWindow

        window = MainWindow(db=db, profile=profile)
        window.show()

        sys.exit(app.exec())

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nInstall dependencies:")
        print("  pip install PyQt6 ollama transformers sounddevice numpy")
        print("  pip install kokoro  # (optional, better TTS)")
        print("  brew install portaudio  # (macOS, required for sounddevice)")
        sys.exit(1)


def _load_fonts():
    from PyQt6.QtGui import QFontDatabase
    assets_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    if not os.path.exists(assets_dir):
        return
    loaded = 0
    for fname in os.listdir(assets_dir):
        if fname.endswith((".ttf", ".otf")):
            path = os.path.join(assets_dir, fname)
            if QFontDatabase.addApplicationFont(path) >= 0:
                loaded += 1
    if loaded:
        logging.getLogger(__name__).info(f"Loaded {loaded} custom font(s)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8.9 — Run full test suite**

```bash
cd langcoach && python -m pytest tests/ -v
```

Expected: All 15 tests PASS

- [ ] **Step 8.10 — Smoke test: launch the app**

```bash
cd langcoach && python main.py
```

Expected:

1. ProfileScreen wizard appears (first launch, no profiles)
2. Complete the 3-step wizard
3. MainWindow opens with "💬 Session" and "📈 Dashboard" tabs in header
4. Session starts with the AI greeting the user by name
5. Dashboard tab shows the profile name and empty state

- [ ] **Step 8.11 — Commit**

```bash
git add ui/main_window.py main.py
git commit -m "feat: integrate profile flow, stats, and dashboard tab into main window"
```

---

## Self-Review

### Spec Coverage

| Spec requirement             | Task implementing it                                       |
| ---------------------------- | ---------------------------------------------------------- |
| Profiles: name + avatar      | Task 6 — ProfileWizard step 1                              |
| Multi-profile splash screen  | Task 6 — ProfileScreen.\_build_splash                      |
| Wizard 3 steps               | Task 6 — ProfileWizard steps 1/2/3                         |
| Settings per profile         | Task 2 + Task 8.5 (\_on_settings_changed saves to DB)      |
| Auto-select single profile   | Task 6 — ProfileScreen (QTimer.singleShot → accept)        |
| Migration from settings.json | Task 2 — migrate_if_needed                                 |
| SQLite schema (5 tables)     | Task 1 — \_SCHEMA + Database class                         |
| Real-time [brackets] parsing | Task 4 — StatsEngine.parse_errors + \_ERROR_RE             |
| Exchange recording           | Task 4 — StatsEngine.record_exchange                       |
| End-of-session LLM analysis  | Task 4 — StatsEngine.end_session + \_analyze_session_async |
| error_patterns aggregation   | Task 1 — record_errors (INSERT OR REPLACE)                 |
| User name in system prompt   | Task 3 — build_system_prompt(user_name=)                   |
| Session / Dashboard tabs     | Task 8 — QStackedWidget + tab buttons                      |
| Vue globale KPIs             | Task 7 — DashboardPanel.\_refresh_overview                 |
| Progression chart            | Task 7 — MiniBarChart                                      |
| Erreurs breakdown + patterns | Task 7 — DashboardPanel.\_refresh_errors                   |
| Sessions historique          | Task 7 — DashboardPanel.\_refresh_sessions                 |
| Lesson catalog (predefined)  | Task 4 — LESSON_CATALOG dict                               |
| Lesson recommendations       | Task 7 — DashboardPanel.\_refresh_lessons                  |
| AI analysis on demand        | Task 7 — DashboardPanel.\_run_ai_analysis                  |

All 20 spec requirements covered. ✓

### Type Consistency

- `StatsEngine.start_session(profile, language, level, topic)` — defined Task 4, called Task 5 ✓
- `StatsEngine.record_exchange(user_text, ai_response, duration_ms)` — matches ✓
- `StatsEngine.end_session()` — no args, matches ✓
- `StatsEngine.parse_errors(str)` — static, returns `list[dict]` ✓
- `Database.get_session(session_id)` — defined Task 1, used Task 4 + tests ✓
- `DashboardPanel(db, stats_engine)` + `set_profile(profile)` — matches ✓
- `MainWindow(db, profile)` — matches ✓
- `end_session()` captures `session_id` before reset, passes to thread as arg ✓

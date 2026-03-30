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
        self._migrate_schema()

    def _migrate_schema(self):
        """Ajoute les colonnes manquantes pour les anciennes bases de données."""
        cursor = self._conn.execute("PRAGMA table_info(sessions)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "title" not in columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
            self._conn.commit()
            logger.info("Migration DB : colonne sessions.title ajoutée")

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

    def update_session_title(self, session_id: str, title: str):
        self._conn.execute(
            "UPDATE sessions SET title=? WHERE id=?", (title, session_id)
        )
        self._conn.commit()

    def get_session_exchanges(self, session_id: str) -> list:
        rows = self._conn.execute(
            "SELECT user_text, ai_response FROM exchanges WHERE session_id=? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_session_summary(self, session_id: str, quality_score: float, summary: str):
        self._conn.execute(
            "UPDATE sessions SET quality_score=?, summary=? WHERE id=?",
            (quality_score, summary, session_id),
        )
        self._conn.commit()

    def update_profile(self, profile_id: str, name: str, avatar: str):
        self._conn.execute(
            "UPDATE profiles SET name=?, avatar=? WHERE id=?",
            (name, avatar, profile_id),
        )
        self._conn.commit()

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

    def delete_session(self, session_id: str):
        """Supprime une session et toutes ses données (échanges, erreurs)."""
        self._conn.execute("DELETE FROM errors WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM exchanges WHERE session_id=?", (session_id,))
        self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self._conn.commit()

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
            "FROM sessions WHERE profile_id=?",
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
            "WHERE profile_id=? "
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

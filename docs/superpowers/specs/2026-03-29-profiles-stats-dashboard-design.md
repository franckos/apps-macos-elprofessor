# Profiles, Statistics & Dashboard — Design Spec

**Date:** 2026-03-29
**Project:** Echo / LangCoach (MacOS, PyQt6)
**Status:** Approved

---

## 1. Overview

Add a multi-profile system, per-exchange error tracking, and a full analytics dashboard to Echo. Each profile owns its settings and statistics. The app tracks oral errors in real time by parsing structured correction markers from LLM responses, then runs a silent end-of-session LLM analysis to score quality. A dedicated Dashboard tab exposes all metrics per profile with automatic lesson recommendations.

---

## 2. Profile System

### 2.1 Splash Screen

- Displayed at launch **only if multiple profiles exist**. With a single profile, the app starts directly.
- Layout: centered cards, one per profile (avatar emoji + name + language + level).
- "+" card to create a new profile.
- Pressing Enter or clicking a card loads that profile and opens the main window.

### 2.2 Profile Creation Wizard (3 steps)

**Step 1 — Identity**
- Text field: first name (the AI will address the user by this name)
- Avatar picker: grid of emoji options (🧑 👩 🧒 👨‍💼 👩‍🎓 …)

**Step 2 — Language**
- Dropdown: target language (English, Spanish, …)
- Level selector: A1 / A2 / B1 / B2 / C1 / C2 (pill buttons)

**Step 3 — Coach & Style**
- Coach selector (cards with flag + name, filtered by language)
- Teaching style selector (Bienveillant / Natif / Académique / Strict / Socratique)

On completion, a UUID is generated and the profile is inserted into the database. The last-used profile ID is persisted in `~/.langcoach/settings.json`.

### 2.3 Profile Data Model

Each profile stores:
- `id` (UUID), `name`, `avatar` (emoji), `created_at`, `last_used`
- `settings` (JSON blob): `target_language`, `level`, `coach`, `teacher_style`, `topic`, `native_language`, `input_mode`, `show_transcript`, `show_corrections`

Settings are loaded from the profile's `settings` JSON on profile selection and saved back on every change (replacing the current global `settings.json` approach for per-user state).

**Migration:** On first launch after this feature ships, if `~/.langcoach/settings.json` exists and no profiles are in the DB, a default profile named "Moi" is auto-created using the existing settings, then the user is prompted to set their name.

---

## 3. Error Detection & Statistics Pipeline

### 3.1 LLM Output Format

The system prompt is updated to instruct the coach to use a structured correction format:

```
[grammar: "I go yesterday" → "I went yesterday" | simple past irregular]
[vocabulary: "I am boring" → "I am bored" | adjective vs participle]
[tense: "I have went" → "I have gone" | present perfect irregular]
```

Categories: `grammar`, `vocabulary`, `tense`, `pronunciation_hint`, `syntax`.

Minor corrections (reformulations without explicit brackets) are **not** captured — only bracketed corrections are parsed. This avoids false positives.

### 3.2 Real-Time Parsing

`StatsEngine.parse_errors(ai_response: str) -> list[ErrorRecord]` extracts all bracketed corrections using a regex:

```
\[(?P<type>\w+): "(?P<original>[^"]+)" → "(?P<corrected>[^"]+)" \| (?P<rule>[^\]]+)\]
```

Each extracted error is inserted into the `errors` table immediately after the AI response is finalized (in the `on_assistant_done` callback).

### 3.3 End-of-Session Analysis

Triggered by `session.reset_session()` or `window.closeEvent()`.

A **silent LLM call** (non-blocking, background thread) sends:
- The session's exchange count, error count, error breakdown
- A prompt asking for: `quality_score` (0.0–1.0) and a 2–3 sentence `summary` in the user's native language

The result is stored in the `sessions` table. If the session has < 3 exchanges, the analysis is skipped (not enough data).

### 3.4 Error Pattern Aggregation

The `error_patterns` table maintains a live running count per `(profile_id, error_type, rule)`. It is updated via `INSERT OR REPLACE` on every new error — no batch aggregation needed. This makes dashboard queries instant.

---

## 4. Database Schema

File: `~/.langcoach/data.db` (SQLite)

```sql
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    avatar      TEXT NOT NULL DEFAULT '🧑',
    created_at  INTEGER NOT NULL,
    last_used   INTEGER NOT NULL,
    settings    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE sessions (
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

CREATE TABLE exchanges (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    timestamp    INTEGER NOT NULL,
    user_text    TEXT NOT NULL,
    ai_response  TEXT NOT NULL,
    error_count  INTEGER NOT NULL DEFAULT 0,
    duration_ms  INTEGER
);

CREATE TABLE errors (
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

CREATE TABLE error_patterns (
    profile_id        TEXT NOT NULL REFERENCES profiles(id),
    error_type        TEXT NOT NULL,
    rule              TEXT NOT NULL,
    occurrence_count  INTEGER NOT NULL DEFAULT 1,
    last_seen         INTEGER NOT NULL,
    PRIMARY KEY (profile_id, error_type, rule)
);

CREATE INDEX idx_sessions_profile ON sessions(profile_id);
CREATE INDEX idx_errors_profile ON errors(profile_id);
CREATE INDEX idx_errors_session ON errors(session_id);
```

---

## 5. Architecture

### 5.1 New Files

| File | Responsibility |
|------|---------------|
| `core/database.py` | SQLite manager: schema creation, CRUD for all tables, dashboard query methods |
| `core/stats_engine.py` | Parses `[brackets]` from LLM responses, records exchanges/errors, triggers end-of-session analysis |
| `ui/profile_screen.py` | Splash screen widget + 3-step profile creation wizard |
| `ui/dashboard_panel.py` | Dashboard tab: Vue globale, Erreurs, Sessions, Leçons sub-tabs |

### 5.2 Modified Files

| File | Change |
|------|--------|
| `config/settings.py` | Add `DB_FILE` path constant; `load_settings(profile_id)` / `save_settings(profile_id, data)` read/write from DB instead of flat JSON |
| `core/session.py` | Accept `profile` object on `initialize()`; emit exchange events to `StatsEngine`; call `stats_engine.end_session()` on reset/close |
| `core/prompt_builder.py` | Inject `user_name` into system prompt ("Your student's name is {name}"); update correction format instructions |
| `ui/main_window.py` | Add tab navigation (Session / Dashboard); show `ProfileScreen` on startup if needed; pass active profile to `SessionManager` |

### 5.3 Data Flow

```
[App launch]
  → ProfileScreen shown (if >1 profile or no profile)
  → User selects / creates profile
  → MainWindow(profile) opens

[Each exchange]
  STT transcript → SessionManager._get_ai_response()
  → LLM response → StatsEngine.record_exchange(user_text, ai_response)
    → parse_errors() → INSERT into errors + error_patterns
    → INSERT into exchanges

[Session end (reset or close)]
  → StatsEngine.end_session()
    → UPDATE sessions SET ended_at, exchange_count, error_count
    → background LLM call → UPDATE sessions SET quality_score, summary

[Dashboard opened]
  → Database.get_dashboard_data(profile_id)
    → KPIs, error breakdown, progression, patterns
  → DashboardPanel renders
```

---

## 6. Dashboard

### 6.1 Navigation

Top-level tabs in `MainWindow`: **Session** | **Dashboard**

Dashboard has internal sub-tabs: **Vue globale** | **Erreurs** | **Sessions** | **Leçons**

### 6.2 Vue Globale

- 4 KPI cards: Sessions total · Erreurs/échange (avg) · Qualité moyenne (%) · Streak (consecutive days)
- Progression chart: quality score per session (last 10 sessions), rendered as a bar chart using QPainter

### 6.3 Onglet Erreurs

- Breakdown by type (grammar / vocabulary / tense / …) with horizontal bar + count
- "Lacunes récurrentes" list: top 5 `error_patterns` ordered by `occurrence_count DESC`, with alert badges (red if ≥ 10, orange if ≥ 5)

### 6.4 Onglet Sessions

- Scrollable list of past sessions, newest first
- Each row: date, language, level, topic, exchange count, error count, quality score badge, summary (expandable)

### 6.5 Onglet Leçons

**Automatic alerts:** Rules fire when `error_patterns.occurrence_count` exceeds a threshold:
- ≥ 5 occurrences → lesson card shown
- ≥ 10 occurrences → card highlighted in red ("point critique")

Predefined lesson catalog (Python dict): maps `(error_type, rule_keyword)` → lesson title + description + example.

**On-demand AI analysis:** "Analyse mes lacunes 🤖" button → silent LLM call with the top 5 error patterns → returns a personalized multi-paragraph coaching plan displayed in a scrollable text area.

---

## 7. User Name in Conversations

`build_system_prompt()` gains a `user_name` parameter. The system prompt includes:

```
Your student's name is {user_name}. Address them by name occasionally to make the session feel personal.
```

---

## 8. Lesson Catalog Structure

```python
LESSON_CATALOG = {
    ("tense", "simple past"): {
        "title": "Simple past — verbes irréguliers",
        "desc": "Les verbes irréguliers ne prennent pas -ed au prétérit.",
        "examples": ["go → went", "have → had", "see → saw"],
        "tip": "Mémorise les 20 verbes irréguliers les plus courants.",
    },
    ("tense", "present perfect"): {
        "title": "Present perfect vs Simple past",
        "desc": "Present perfect = lien avec le présent. Simple past = passé révolu.",
        "examples": ["I have seen it (still relevant)", "I saw it yesterday (fixed time)"],
        "tip": "Si tu peux dire 'yesterday/last week', utilise simple past.",
    },
    # ... autres règles
}
```

---

## 9. Out of Scope

- Export CSV/PDF des stats (possible future feature)
- Synchronisation cloud des profils
- Analyse de la prononciation (le STT ne retourne pas de score de confiance exploitable)
- Gamification (badges, niveaux XP) — peut être ajouté par-dessus ce système

---

## 10. Open Questions (resolved)

| Question | Decision |
|----------|----------|
| Error detection method | Hybrid: real-time [brackets] parsing + end-of-session LLM analysis |
| Dashboard placement | Tab navigation (Session / Dashboard) |
| Lesson recommendations | Hybrid: predefined rules + on-demand AI |
| Profile screen | Dedicated splash screen (like Netflix) |
| Settings scope | Per-profile |
| Storage | SQLite (`~/.langcoach/data.db`) |
| Dashboard layout | Sub-tabs (Vue globale / Erreurs / Sessions / Leçons) |
| Profile creation | 3-step wizard |

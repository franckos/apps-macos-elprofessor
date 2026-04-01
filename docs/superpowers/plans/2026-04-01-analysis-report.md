# Analysis Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken post-session modal with a full-screen rich analysis report (résumé, erreurs, améliorations, vocabulaire, mémoires), fix DB threading corruption, and stop the chat from clearing before analysis completes.

**Architecture:** Add `AnalysisReportWidget` as `_session_stack` index 2 (alongside existing topic picker at 0 and chat at 1). Enrich the LLM analysis prompt to return structured JSON with errors/improvements/vocabulary. Fix concurrent SQLite corruption with a threading.RLock in Database.

**Tech Stack:** Python 3.9, PyQt6, SQLite (sqlite3), threading

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `langcoach/core/database.py` | Modify | Add `threading.RLock` to serialize all DB access |
| `langcoach/core/stats_engine.py` | Modify | Enrich LLM prompt; update `_parse_analysis_response`, `analyze_session_by_id`, `analyze_and_extract_async` signatures |
| `langcoach/ui/analysis_report.py` | **Create** | `ScoreCircle` + `AnalysisReportWidget` (all sections + memory accept/ignore) |
| `langcoach/ui/main_window.py` | Modify | Wire report to `_session_stack[2]`, fix flow (no premature clear), update signal |
| `langcoach/tests/test_database_threading.py` | **Create** | Concurrent-write test verifying no corruption |
| `langcoach/tests/test_stats_engine.py` | Modify | Tests for new `_parse_analysis_response` + `_build_full_analysis_prompt` |

---

## Task 1: DB Threading Lock

**Files:**
- Modify: `langcoach/core/database.py`
- Create: `langcoach/tests/test_database_threading.py`

- [ ] **Step 1: Write the failing concurrent-write test**

Create `langcoach/tests/test_database_threading.py`:

```python
import threading
import pytest
from core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def profile(db):
    return db.create_profile("Franck", "🧑", {})


def test_concurrent_writes_do_not_corrupt(db, profile):
    """Two threads writing memories simultaneously must not raise or corrupt."""
    errors = []

    def write_memories():
        try:
            for i in range(20):
                db.create_memory(profile["id"], f"Memory {i}", ["perso"])
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=write_memories)
    t2 = threading.Thread(target=write_memories)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"Concurrent write errors: {errors}"
    memories = db.list_memories(profile["id"])
    assert len(memories) == 40
```

- [ ] **Step 2: Run test to verify it fails (or passes trivially — confirm behavior)**

```bash
cd langcoach && .venv/bin/python -m pytest tests/test_database_threading.py -v
```

- [ ] **Step 3: Add RLock to Database**

In `langcoach/core/database.py`, add `import threading` at the top (after `import sqlite3`), then update `__init__` and wrap every public method:

```python
import threading  # add after import sqlite3
```

In `Database.__init__`, add after the `_migrate_schema()` call:
```python
        self._lock = threading.RLock()
```

Then wrap every public method body with `with self._lock:`. The full list of methods to wrap:

- `create_profile` 
- `get_profile`
- `list_profiles`
- `update_session_title`
- `get_session_exchanges`
- `update_session_summary`
- `update_profile`
- `update_profile_settings`
- `touch_profile`
- `delete_profile`
- `open_session`
- `get_session`
- `close_session`
- `list_sessions`
- `delete_session`
- `record_exchange`
- `record_errors`
- `get_kpis`
- `get_error_breakdown`
- `get_top_patterns`
- `get_quality_progression`
- `create_memory`
- `list_memories`
- `update_memory`
- `update_memory_last_used`
- `update_memory_weight`
- `delete_memory`
- `create_memory_suggestion`
- `list_memory_suggestions`
- `delete_memory_suggestion`
- `accept_memory_suggestion`

Example pattern for `get_profile`:
```python
def get_profile(self, profile_id: str) -> Optional[dict]:
    with self._lock:
        row = self._conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return self._profile_dict(row) if row else None
```

Apply the same `with self._lock:` wrapping to all methods listed above. Private helpers (`_profile_dict`, `_memory_dict`, `_suggestion_dict`, `_compute_streak`, `_migrate_schema`) do NOT get the lock (they are only called from within locked methods).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd langcoach && .venv/bin/python -m pytest tests/test_database_threading.py tests/test_database.py tests/test_memory_db.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd langcoach && git add core/database.py tests/test_database_threading.py
git commit -m "fix: add RLock to Database to prevent concurrent-write corruption"
```

---

## Task 2: Enriched LLM Analysis Prompt

**Files:**
- Modify: `langcoach/core/stats_engine.py`
- Modify: `langcoach/tests/test_stats_engine.py`

- [ ] **Step 1: Write failing tests for new parse + prompt**

Add at the end of `langcoach/tests/test_stats_engine.py`:

```python
def test_parse_analysis_response_full_json():
    """New _parse_analysis_response returns (score, analysis_dict) with all fields."""
    text = '''{
        "quality_score": 0.82,
        "summary": "Bonne session, continue comme ça.",
        "errors": [{"original": "I go yesterday", "corrected": "I went yesterday", "type": "tense", "rule": "simple past"}],
        "improvements": ["Travailler le prétérit", "Utiliser des connecteurs"],
        "vocabulary": [{"word": "commute", "translation": "trajet", "example": "My commute takes 30 min."}]
    }'''
    score, analysis = StatsEngine._parse_analysis_response(text)
    assert score == pytest.approx(0.82)
    assert analysis["summary"] == "Bonne session, continue comme ça."
    assert len(analysis["errors"]) == 1
    assert analysis["errors"][0]["original"] == "I go yesterday"
    assert len(analysis["improvements"]) == 2
    assert len(analysis["vocabulary"]) == 1
    assert analysis["vocabulary"][0]["word"] == "commute"


def test_parse_analysis_response_fallback():
    """Returns safe defaults when JSON is malformed."""
    score, analysis = StatsEngine._parse_analysis_response("not json at all")
    assert score == pytest.approx(0.5)
    assert analysis["summary"] == ""
    assert analysis["errors"] == []
    assert analysis["improvements"] == []
    assert analysis["vocabulary"] == []


def test_build_full_analysis_prompt_contains_conversation():
    """Prompt includes conversation excerpt and all required JSON fields."""
    engine = StatsEngine(db=None, llm=None)
    session = {
        "language": "english", "level": "B1", "topic": "Travel",
        "exchange_count": 5, "error_count": 2,
    }
    exchanges = [
        {"user_text": "I go to Paris yesterday", "ai_response": "Great! [tense: ...]"},
    ]
    prompt = engine._build_full_analysis_prompt(session, exchanges)
    assert "I go to Paris yesterday" in prompt
    assert "quality_score" in prompt
    assert "improvements" in prompt
    assert "vocabulary" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd langcoach && .venv/bin/python -m pytest tests/test_stats_engine.py::test_parse_analysis_response_full_json tests/test_stats_engine.py::test_parse_analysis_response_fallback tests/test_stats_engine.py::test_build_full_analysis_prompt_contains_conversation -v
```
Expected: FAIL (AttributeError or AssertionError)

- [ ] **Step 3: Replace `_parse_analysis_response` in `stats_engine.py`**

Replace the existing `_parse_analysis_response` static method (lines 324-335) with:

```python
@staticmethod
def _parse_analysis_response(text: str) -> tuple:
    """Returns (score: float, analysis: dict) with full structured data."""
    empty = {"summary": "", "errors": [], "improvements": [], "vocabulary": []}
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            score = max(0.0, min(1.0, float(data.get("quality_score", 0.5))))
            analysis = {
                "summary": str(data.get("summary", "")),
                "errors": data.get("errors", []) if isinstance(data.get("errors"), list) else [],
                "improvements": data.get("improvements", []) if isinstance(data.get("improvements"), list) else [],
                "vocabulary": data.get("vocabulary", []) if isinstance(data.get("vocabulary"), list) else [],
            }
            return score, analysis
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    return 0.5, empty
```

- [ ] **Step 4: Add `_build_full_analysis_prompt` method to `StatsEngine`**

Add this new method after `_build_analysis_prompt` (around line 322):

```python
def _build_full_analysis_prompt(self, session: dict, exchanges: list) -> str:
    """Builds the enriched analysis prompt used by 'Analyser' button."""
    convo = "\n".join(
        f"Apprenant : {e['user_text']}\nCoach : {e['ai_response'][:200]}"
        for e in exchanges[:10]
    )
    return (
        "Analyse cette séance d'apprentissage de langue. Réponds UNIQUEMENT avec un objet JSON valide.\n\n"
        f"Séance :\n"
        f"- Langue : {session['language']} ({session['level']})\n"
        f"- Sujet : {session['topic']}\n"
        f"- Échanges : {session['exchange_count']}\n"
        f"- Erreurs détectées : {session['error_count']}\n\n"
        f"Conversation :\n{convo[:2000]}\n\n"
        "Réponds avec UNIQUEMENT ce JSON (pas d'autre texte) :\n"
        '{"quality_score": 0.75, '
        '"summary": "2-3 phrases bienveillantes en français résumant la session.", '
        '"errors": [{"original": "phrase originale", "corrected": "phrase corrigée", "type": "grammar", "rule": "nom de la règle"}], '
        '"improvements": ["Axe d\'amélioration 1 en français", "Axe d\'amélioration 2 en français"], '
        '"vocabulary": [{"word": "mot_anglais", "translation": "traduction française", "example": "exemple en anglais."}]}\n\n'
        "Règles :\n"
        "- quality_score : 0.0 (très mauvais) à 1.0 (excellent)\n"
        "- summary : en français, bienveillant, 2-3 phrases\n"
        "- errors : toutes les erreurs réelles corrigées dans la conversation (max 8), ou [] si aucune\n"
        "- improvements : 2 à 4 axes d'amélioration concrets en français\n"
        "- vocabulary : 3 à 6 mots/expressions importants de la conversation, avec traduction et exemple"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd langcoach && .venv/bin/python -m pytest tests/test_stats_engine.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
cd langcoach && git add core/stats_engine.py tests/test_stats_engine.py
git commit -m "feat: enrich LLM analysis prompt with errors, improvements, vocabulary"
```

---

## Task 3: Update `analyze_session_by_id` and `analyze_and_extract_async` Signatures

**Files:**
- Modify: `langcoach/core/stats_engine.py`

- [ ] **Step 1: Replace `analyze_session_by_id` method**

Replace the entire `analyze_session_by_id` method (lines 163–209) with:

```python
def analyze_session_by_id(self, session_id: str, on_done):
    """Analyse à la demande d'une session. Appelle on_done(score, analysis_dict)."""
    _empty = {"summary": "LLM non disponible.", "errors": [], "improvements": [], "vocabulary": []}
    if not self._llm:
        on_done(None, _empty)
        return

    def run():
        try:
            session = self._db.get_session(session_id)
            if not session:
                on_done(None, {"summary": "Session introuvable.", "errors": [], "improvements": [], "vocabulary": []})
                return
            exchanges = self._db.get_session_exchanges(session_id)
            if not exchanges:
                on_done(None, {"summary": "Aucun échange à analyser.", "errors": [], "improvements": [], "vocabulary": []})
                return
            prompt = self._build_full_analysis_prompt(session, exchanges)
            response = self._llm.chat_oneshot(
                "Tu es un coach de langue expert. Tu analyses des séances et fournis des rapports détaillés. Réponds toujours en JSON valide.",
                prompt,
            )
            if response:
                score, analysis = self._parse_analysis_response(response)
                self._db.update_session_summary(session_id, score, analysis["summary"])
                on_done(score, analysis)
            else:
                on_done(None, {"summary": "Analyse non disponible.", "errors": [], "improvements": [], "vocabulary": []})
        except Exception as e:
            logger.error(f"Analyse échouée : {e}")
            on_done(None, {"summary": f"Erreur : {e}", "errors": [], "improvements": [], "vocabulary": []})

    threading.Thread(target=run, daemon=True).start()
```

- [ ] **Step 2: Replace `analyze_and_extract_async` method**

Replace the entire `analyze_and_extract_async` method (lines 236–286) with:

```python
def analyze_and_extract_async(self, on_done):
    """Used by 'Analyser' button. Calls on_done(score, analysis_dict, suggestions_list)."""
    if not self._session_id:
        on_done(None, {"summary": "Aucune session en cours.", "errors": [], "improvements": [], "vocabulary": []}, [])
        return

    session_id = self._session_id
    profile = self._profile
    exchange_count = self._exchange_count

    self._db.close_session(session_id, quality_score=None, summary=None)
    self._session_id = None
    self._exchange_count = 0
    self._error_count = 0

    if not self._llm or not profile:
        on_done(None, {"summary": "LLM non disponible.", "errors": [], "improvements": [], "vocabulary": []}, [])
        return

    analysis_result = [None, None]   # [score, analysis_dict]
    done_events = [False, False]     # [analysis_done, extraction_done]

    def _check_both_done():
        if all(done_events):
            score, analysis = analysis_result
            suggestions = self._db.list_memory_suggestions(profile["id"])
            on_done(score, analysis, suggestions)

    def _on_analysis(score, analysis):
        analysis_result[0] = score
        analysis_result[1] = analysis
        done_events[0] = True
        _check_both_done()

    def _on_extraction(count):
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

- [ ] **Step 3: Update `dashboard_panel.py` — `analyze_session_by_id` call**

The dashboard uses `analyze_session_by_id` with the old `on_done(score, summary)` signature. Update the callback in `langcoach/ui/dashboard_panel.py` around line 484.

Find the `on_done` callback in the dashboard that calls `analyze_session_by_id`. It currently expects `(score, summary)`. Update it to `(score, analysis)` and extract `analysis["summary"]`:

```python
# Find this pattern in dashboard_panel.py (around line 480-490):
def on_done(score, summary):
    # ... uses score and summary
```

Replace with:
```python
def on_done(score, analysis):
    summary = analysis.get("summary", "") if isinstance(analysis, dict) else str(analysis)
    # rest of the existing callback body unchanged, using score and summary
```

- [ ] **Step 4: Run all tests**

```bash
cd langcoach && .venv/bin/python -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd langcoach && git add core/stats_engine.py ui/dashboard_panel.py
git commit -m "feat: update analyze callbacks to return structured analysis dict"
```

---

## Task 4: Create `ScoreCircle` Widget

**Files:**
- Create: `langcoach/ui/analysis_report.py`

- [ ] **Step 1: Create the file with `ScoreCircle`**

Create `langcoach/ui/analysis_report.py`:

```python
"""
LangCoach — Analysis Report Widget
Écran plein de rapport post-session — _session_stack index 2
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QPen, QFont, QColor

from config.theme import T


class ScoreCircle(QWidget):
    """Circular score indicator drawn with QPainter."""

    def __init__(self, score: Optional[float] = None, parent=None):
        super().__init__(parent)
        self._score = score
        self.setFixedSize(80, 80)
        self.setStyleSheet("background: transparent;")

    def set_score(self, score: Optional[float]):
        self._score = score
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRect(10, 10, 60, 60)

        # Background track
        painter.setPen(QPen(QColor(T["border"]), 7))
        painter.drawEllipse(rect)

        # Colored arc
        pct = self._score if self._score is not None else 0.0
        if pct >= 0.75:
            arc_color = QColor(T["success"])
        elif pct >= 0.5:
            arc_color = QColor(T["warning"])
        else:
            arc_color = QColor(T["error"])

        pen = QPen(arc_color, 7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        start_angle = 90 * 16
        span_angle = -int(pct * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Score text
        painter.setPen(QPen(QColor(T["text_primary"])))
        font = QFont(T["font_display"], 15)
        font.setBold(True)
        painter.setFont(font)
        score_text = str(round(pct * 100)) if self._score is not None else "—"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, score_text)

        painter.end()
```

- [ ] **Step 2: Verify syntax (no QApplication needed)**

```bash
cd langcoach && .venv/bin/python -c "from ui.analysis_report import ScoreCircle; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd langcoach && git add ui/analysis_report.py
git commit -m "feat: add ScoreCircle widget"
```

---

## Task 5: Build `AnalysisReportWidget` Skeleton + Content Sections

**Files:**
- Modify: `langcoach/ui/analysis_report.py`

- [ ] **Step 1: Add `AnalysisReportWidget` to `analysis_report.py`**

Append the following class to `langcoach/ui/analysis_report.py` (after `ScoreCircle`):

```python

class AnalysisReportWidget(QWidget):
    """Full-screen post-session analysis report — sits at _session_stack index 2."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self.on_new_session = None   # callable() — set by main_window
        self.on_go_dashboard = None  # callable() — set by main_window
        self._suggestion_cards = {}  # suggestion_id -> QFrame
        self._suggestions_section = None
        self._setStyleSheet()
        self._build_ui()

    def _setStyleSheet(self):
        self.setStyleSheet(f"background-color: {T['bg_primary']};")

    # ── Build UI ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_separator())
        layout.addWidget(self._build_scroll_area(), 1)
        layout.addWidget(self._build_separator())
        layout.addWidget(self._build_footer())

    def _build_separator(self):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {T['border']}; border: none;")
        return sep

    def _build_header(self):
        header = QFrame()
        header.setFixedHeight(84)
        header.setStyleSheet(f"background-color: {T['bg_secondary']};")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_md"], T["spacing_xl"], T["spacing_md"])
        layout.setSpacing(T["spacing_lg"])

        self._score_circle = ScoreCircle(None)
        layout.addWidget(self._score_circle)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        self._title_lbl = QLabel("Rapport de session")
        self._title_lbl.setFont(QFont(T["font_display"], T["font_size_lg"]))
        self._title_lbl.setStyleSheet(
            f"color: {T['text_primary']}; background: transparent; font-weight: 600;"
        )
        info_col.addWidget(self._title_lbl)

        self._subtitle_lbl = QLabel("")
        self._subtitle_lbl.setStyleSheet(
            f"color: {T['text_muted']}; background: transparent; font-size: {T['font_size_sm']}px;"
        )
        info_col.addWidget(self._subtitle_lbl)

        layout.addLayout(info_col)
        layout.addStretch()

        return header

    def _build_scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {T['bg_primary']};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            T["spacing_xl"], T["spacing_lg"], T["spacing_xl"], T["spacing_lg"]
        )
        self._content_layout.setSpacing(T["spacing_md"])

        scroll.setWidget(self._content)
        return scroll

    def _build_footer(self):
        footer = QFrame()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"background-color: {T['bg_secondary']};")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_md"], T["spacing_xl"], T["spacing_md"])
        layout.setSpacing(T["spacing_md"])
        layout.addStretch()

        dashboard_btn = QPushButton("Tableau de bord")
        dashboard_btn.setFixedHeight(36)
        dashboard_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 20px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {T['bg_hover']}; }}
        """)
        dashboard_btn.clicked.connect(lambda: self.on_go_dashboard and self.on_go_dashboard())
        layout.addWidget(dashboard_btn)

        new_btn = QPushButton("Nouvelle discussion")
        new_btn.setFixedHeight(36)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']};
                color: white;
                border: none;
                border-radius: {T['radius_md']}px;
                padding: 0 20px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {T['accent_hover']}; }}
        """)
        new_btn.clicked.connect(lambda: self.on_new_session and self.on_new_session())
        layout.addWidget(new_btn)

        return footer

    # ── Section builders ──────────────────────────────────────

    def _make_section_card(self, title: str) -> tuple:
        """Returns (card QFrame, body_layout QVBoxLayout)."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {T['bg_card']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(T["spacing_lg"], T["spacing_md"], T["spacing_lg"], T["spacing_lg"])
        layout.setSpacing(T["spacing_sm"])

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        title_lbl.setStyleSheet(
            f"color: {T['text_muted']}; background: transparent; "
            f"font-weight: 700; letter-spacing: 1px; text-transform: uppercase;"
        )
        layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {T['border']}; border: none;")
        layout.addWidget(sep)

        return card, layout

    def _build_summary_card(self, summary: str) -> QFrame:
        card, body = self._make_section_card("RÉSUMÉ")
        lbl = QLabel(summary)
        lbl.setFont(QFont(T["font_body"], T["font_size_md"]))
        lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; line-height: 1.6;")
        lbl.setWordWrap(True)
        body.addWidget(lbl)
        return card

    def _build_errors_card(self, errors: list) -> QFrame:
        card, body = self._make_section_card(f"ERREURS CORRIGÉES  ({len(errors)})")
        for err in errors[:8]:
            row = QFrame()
            row.setStyleSheet(
                f"background-color: {T['bg_secondary']}; "
                f"border-radius: {T['radius_sm']}px; border: none;"
            )
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(T["spacing_md"], T["spacing_sm"], T["spacing_md"], T["spacing_sm"])
            row_layout.setSpacing(2)

            orig = QLabel(f"✗  {err.get('original', '')}")
            orig.setStyleSheet(f"color: {T['error']}; background: transparent; font-size: {T['font_size_sm']}px;")
            orig.setWordWrap(True)
            row_layout.addWidget(orig)

            corr = QLabel(f"✓  {err.get('corrected', '')}")
            corr.setStyleSheet(f"color: {T['success']}; background: transparent; font-size: {T['font_size_sm']}px;")
            corr.setWordWrap(True)
            row_layout.addWidget(corr)

            rule = err.get("rule", "")
            if rule:
                rule_lbl = QLabel(rule)
                rule_lbl.setStyleSheet(
                    f"color: {T['text_muted']}; background: transparent; "
                    f"font-size: {T['font_size_xs']}px; font-style: italic;"
                )
                row_layout.addWidget(rule_lbl)

            body.addWidget(row)
        return card

    def _build_improvements_card(self, improvements: list) -> QFrame:
        card, body = self._make_section_card("POINTS À AMÉLIORER")
        for item in improvements:
            row = QHBoxLayout()
            bullet = QLabel("•")
            bullet.setFixedWidth(16)
            bullet.setStyleSheet(f"color: {T['accent']}; background: transparent; font-weight: 700;")
            row.addWidget(bullet)
            lbl = QLabel(item)
            lbl.setStyleSheet(f"color: {T['text_secondary']}; background: transparent; font-size: {T['font_size_sm']}px;")
            lbl.setWordWrap(True)
            row.addWidget(lbl, 1)
            body.addLayout(row)
        return card

    def _build_vocabulary_card(self, vocabulary: list) -> QFrame:
        card, body = self._make_section_card("VOCABULAIRE CLÉ")
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QHBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(T["spacing_sm"])
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for vocab in vocabulary[:6]:
            chip = QFrame()
            chip.setFixedWidth(160)
            chip.setStyleSheet(f"""
                QFrame {{
                    background-color: {T['bg_secondary']};
                    border: 1px solid {T['border']};
                    border-radius: {T['radius_sm']}px;
                }}
            """)
            chip_layout = QVBoxLayout(chip)
            chip_layout.setContentsMargins(T["spacing_sm"], T["spacing_sm"], T["spacing_sm"], T["spacing_sm"])
            chip_layout.setSpacing(2)

            word_lbl = QLabel(vocab.get("word", ""))
            word_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
            word_lbl.setStyleSheet(
                f"color: {T['accent']}; background: transparent; font-weight: 700;"
            )
            chip_layout.addWidget(word_lbl)

            trans_lbl = QLabel(vocab.get("translation", ""))
            trans_lbl.setStyleSheet(
                f"color: {T['text_secondary']}; background: transparent; font-size: {T['font_size_xs']}px;"
            )
            chip_layout.addWidget(trans_lbl)

            example = vocab.get("example", "")
            if example:
                ex_lbl = QLabel(f""{example}"")
                ex_lbl.setStyleSheet(
                    f"color: {T['text_muted']}; background: transparent; "
                    f"font-size: {T['font_size_xs']}px; font-style: italic;"
                )
                ex_lbl.setWordWrap(True)
                chip_layout.addWidget(ex_lbl)

            grid_layout.addWidget(chip)

        grid_layout.addStretch()
        body.addWidget(grid_widget)
        return card

    # ── Load report ───────────────────────────────────────────

    def load_report(
        self,
        score: Optional[float],
        analysis: dict,
        suggestions: list,
        session_info: Optional[dict] = None,
    ):
        """Populate all sections. Must be called from the main (Qt) thread."""
        # Clear previous content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._suggestion_cards.clear()
        self._suggestions_section = None

        # Update header
        self._score_circle.set_score(score)
        if session_info:
            parts = [
                session_info.get("language", ""),
                session_info.get("level", ""),
                session_info.get("topic", ""),
            ]
            self._subtitle_lbl.setText("  ·  ".join(p for p in parts if p))

        summary = analysis.get("summary", "")
        errors = analysis.get("errors", [])
        improvements = analysis.get("improvements", [])
        vocabulary = analysis.get("vocabulary", [])

        if summary:
            self._content_layout.addWidget(self._build_summary_card(summary))
        if errors:
            self._content_layout.addWidget(self._build_errors_card(errors))
        if improvements:
            self._content_layout.addWidget(self._build_improvements_card(improvements))
        if vocabulary:
            self._content_layout.addWidget(self._build_vocabulary_card(vocabulary))

        self._suggestions_section = self._build_suggestions_section(suggestions)
        if suggestions:
            self._content_layout.addWidget(self._suggestions_section)

        self._content_layout.addStretch()
```

- [ ] **Step 2: Verify import**

```bash
cd langcoach && .venv/bin/python -c "from ui.analysis_report import AnalysisReportWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd langcoach && git add ui/analysis_report.py
git commit -m "feat: add AnalysisReportWidget with summary, errors, improvements, vocabulary sections"
```

---

## Task 6: Memory Suggestions Section

**Files:**
- Modify: `langcoach/ui/analysis_report.py`

- [ ] **Step 1: Add `_build_suggestions_section` method to `AnalysisReportWidget`**

Add this method to `AnalysisReportWidget` (before `load_report`):

```python
    def _build_suggestions_section(self, suggestions: list) -> QFrame:
        """Builds the memory suggestions card. Each card has Accept/Ignore buttons."""
        card, body = self._make_section_card(f"MÉMOIRES SUGGÉRÉES  ({len(suggestions)})")
        self._suggestions_body = body

        for s in suggestions:
            self._add_suggestion_card(s, body)

        if not suggestions:
            empty_lbl = QLabel("Aucune mémoire suggérée pour cette session.")
            empty_lbl.setStyleSheet(
                f"color: {T['text_muted']}; background: transparent; font-size: {T['font_size_sm']}px;"
            )
            body.addWidget(empty_lbl)

        return card

    def _add_suggestion_card(self, suggestion: dict, parent_layout):
        """Creates one suggestion row with Accept/Ignore buttons."""
        sid = suggestion["id"]
        row = QFrame()
        row.setObjectName(f"suggestion_{sid}")
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {T['bg_secondary']};
                border-radius: {T['radius_sm']}px;
                border: 1px solid {T['border']};
            }}
        """)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(T["spacing_md"], T["spacing_sm"], T["spacing_sm"], T["spacing_sm"])
        row_layout.setSpacing(T["spacing_sm"])

        icon = QLabel("💡")
        icon.setFixedWidth(24)
        icon.setStyleSheet("background: transparent;")
        row_layout.addWidget(icon)

        content_lbl = QLabel(suggestion.get("content", ""))
        content_lbl.setStyleSheet(
            f"color: {T['text_primary']}; background: transparent; font-size: {T['font_size_sm']}px;"
        )
        content_lbl.setWordWrap(True)
        row_layout.addWidget(content_lbl, 1)

        accept_btn = QPushButton("Accepter")
        accept_btn.setFixedHeight(28)
        accept_btn.setFixedWidth(80)
        accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['success']}22;
                color: {T['success']};
                border: 1px solid {T['success']}44;
                border-radius: {T['radius_sm']}px;
                font-size: {T['font_size_xs']}px;
                font-family: '{T['font_body']}';
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {T['success']}44; }}
        """)
        accept_btn.clicked.connect(lambda checked, s=sid, r=row: self._on_accept_suggestion(s, r))
        row_layout.addWidget(accept_btn)

        ignore_btn = QPushButton("Ignorer")
        ignore_btn.setFixedHeight(28)
        ignore_btn.setFixedWidth(70)
        ignore_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T['text_muted']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                font-size: {T['font_size_xs']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ color: {T['text_secondary']}; }}
        """)
        ignore_btn.clicked.connect(lambda checked, s=sid, r=row: self._on_ignore_suggestion(s, r))
        row_layout.addWidget(ignore_btn)

        self._suggestion_cards[sid] = row
        parent_layout.addWidget(row)

    def _on_accept_suggestion(self, suggestion_id: str, row: QFrame):
        try:
            self._db.accept_memory_suggestion(suggestion_id)
        except Exception:
            pass
        self._remove_suggestion_card(suggestion_id, row)

    def _on_ignore_suggestion(self, suggestion_id: str, row: QFrame):
        try:
            self._db.delete_memory_suggestion(suggestion_id)
        except Exception:
            pass
        self._remove_suggestion_card(suggestion_id, row)

    def _remove_suggestion_card(self, suggestion_id: str, row: QFrame):
        row.hide()
        row.deleteLater()
        self._suggestion_cards.pop(suggestion_id, None)
```

- [ ] **Step 2: Verify import**

```bash
cd langcoach && .venv/bin/python -c "from ui.analysis_report import AnalysisReportWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd langcoach && git add ui/analysis_report.py
git commit -m "feat: add memory suggestions section with accept/ignore to analysis report"
```

---

## Task 7: Integrate Report into `main_window.py`

**Files:**
- Modify: `langcoach/ui/main_window.py`

- [ ] **Step 1: Add import at top of `main_window.py`**

After the existing `from ui.widgets import (...)` block, add:

```python
from ui.analysis_report import AnalysisReportWidget
```

- [ ] **Step 2: Add `_analysis_report` to `_session_stack` in `_build_ui`**

In `_build_ui`, after `self._session_stack.addWidget(chat_widget)` (line 218), add:

```python
        # Index 2: analysis report
        self._analysis_report = AnalysisReportWidget(db=self._db)
        self._analysis_report.on_new_session = self._on_analysis_new_session
        self._analysis_report.on_go_dashboard = self._on_analysis_go_dashboard
        self._session_stack.addWidget(self._analysis_report)
```

- [ ] **Step 3: Update the PyQt signal in `_on_finir_analyser`**

In `_on_finir_analyser`, change the Emitter signal from `_sig(object, object, int)` to `_sig(object, object, object)`:

```python
class Emitter(QObject):
    done = _sig(object, object, object)
```

- [ ] **Step 4: Fix `_on_finir_analyser` — remove premature chat clear**

Replace the entire `_on_finir_analyser` method with:

```python
def _on_finir_analyser(self):
    """Triggers quality analysis + memory extraction, then shows analysis report screen."""
    if not self._stats.session_id:
        self._show_toast("Aucune session active à analyser", kind="info")
        return

    self._btn_finir.setEnabled(False)
    self._btn_finir.setText("Analyse…")

    from PyQt6.QtCore import QObject, pyqtSignal as _sig

    class Emitter(QObject):
        done = _sig(object, object, object)

    emitter = Emitter()
    emitter.done.connect(self._on_finir_result)
    self._finir_emitter = emitter  # keep alive

    def _on_done(score, analysis, suggestions):
        emitter.done.emit(score, analysis, suggestions)

    self._stats.analyze_and_extract_async(_on_done)
```

- [ ] **Step 5: Update `_on_finir_result` to populate the report screen**

Replace `_on_finir_result` and `_show_analysis_recap` with:

```python
def _on_finir_result(self, score, analysis, suggestions):
    self._btn_finir.setEnabled(True)
    self._btn_finir.setText("Analyser")

    session_info = {
        "language": self.settings.get("target_language", ""),
        "level": self.settings.get("level", ""),
        "topic": self.settings.get("topic", ""),
    }
    self._analysis_report.load_report(score, analysis, suggestions, session_info)
    self._session_stack.setCurrentIndex(2)

    # Update memory badge if suggestions exist
    if suggestions and hasattr(self, '_settings_panel'):
        self._settings_panel.update_suggestion_badge(len(suggestions))
```

(Delete the `_show_analysis_recap` method entirely — it is replaced by the report screen.)

- [ ] **Step 6: Add the two navigation callbacks**

Add these two methods after `_on_finir_result`:

```python
def _on_analysis_new_session(self):
    """Called from analysis report 'Nouvelle discussion' button."""
    # Clear chat
    while self._chat_layout.count() > 1:
        item = self._chat_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    self.session.reset_session()
    self._refresh_topic_picker()
    self._session_stack.setCurrentIndex(0)

def _on_analysis_go_dashboard(self):
    """Called from analysis report 'Tableau de bord' button."""
    self._switch_tab(1)
```

- [ ] **Step 7: Verify import works**

```bash
cd langcoach && .venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from ui.analysis_report import AnalysisReportWidget
print('import OK')
"
```
Expected: `import OK`

- [ ] **Step 8: Run all tests**

```bash
cd langcoach && .venv/bin/python -m pytest tests/ -v
```
Expected: all PASS (57+ tests)

- [ ] **Step 9: Commit**

```bash
cd langcoach && git add ui/main_window.py
git commit -m "feat: replace analysis modal with full-screen AnalysisReportWidget in session stack"
```

---

## Task 8: Verify `_chat_layout` reference in `_on_analysis_new_session`

**Files:**
- Modify: `langcoach/ui/main_window.py` (verification only)

- [ ] **Step 1: Confirm `_chat_layout` attribute name**

Search the file to confirm the chat layout attribute name used in `_on_reset`:

```bash
cd langcoach && grep -n "_chat_layout" ui/main_window.py | head -10
```

Expected output: lines referencing `self._chat_layout`. If the attribute is named differently (e.g. `_chat_container_layout`), update `_on_analysis_new_session` to match.

- [ ] **Step 2: Final test run**

```bash
cd langcoach && .venv/bin/python -m pytest tests/ -q
```
Expected: all PASS

- [ ] **Step 3: Final commit**

```bash
cd langcoach && git add -A
git commit -m "feat: complete analysis report — rich post-session screen with errors, vocabulary, memories"
```

---

## Self-Review

### Spec Coverage Check

| Spec requirement | Task |
|---|---|
| DB threading corruption fix | Task 1 |
| No premature chat clear | Task 7, Step 4 |
| Enriched LLM prompt (errors, improvements, vocabulary) | Task 2 |
| New callback signature `(score, analysis, suggestions)` | Task 3 |
| ScoreCircle widget | Task 4 |
| Résumé section | Task 5 |
| Erreurs corrigées section | Task 5 |
| Points à améliorer section | Task 5 |
| Vocabulaire clé section | Task 5 |
| Mémoires suggérées with Accept/Ignore | Task 6 |
| "Nouvelle discussion" CTA | Task 7 |
| "Tableau de bord" CTA | Task 7 |
| `_session_stack` index 2 integration | Task 7 |
| `dashboard_panel` callback updated | Task 3 |

All spec requirements are covered. No gaps found.

### Type Consistency Check

- `_parse_analysis_response` returns `(float, dict)` — used consistently in Tasks 2, 3, 7
- `analyze_session_by_id` callback is `on_done(score, analysis_dict)` — defined Task 3, consumed Task 3 (dashboard) and Task 7
- `analyze_and_extract_async` callback is `on_done(score, analysis_dict, suggestions_list)` — defined Task 3, wired Task 7
- `load_report(score, analysis, suggestions, session_info)` — defined Task 5, called Task 7
- Signal `done = _sig(object, object, object)` — updated Task 7 Step 3, connected Task 7 Step 5

All consistent.

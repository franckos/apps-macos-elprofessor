# Star Rating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5-star rating display alongside the existing % score in the report header and dashboard session list.

**Architecture:** A pure helper function `score_to_stars(score)` handles the float→Unicode conversion; a new `StarBadge` QFrame widget renders the star badge in the report header; the dashboard appends a star QLabel inline after the existing `%` label.

**Tech Stack:** Python 3, PyQt6, pytest

---

## File Map

| File | Change |
|---|---|
| `langcoach/ui/analysis_report.py` | Add `score_to_stars()`, `StarBadge`, update `_build_header()` and `load_report()` |
| `langcoach/ui/dashboard_panel.py` | Import `score_to_stars`, add star `QLabel` after `%` label |
| `tests/test_score_to_stars.py` | Unit tests for the helper function (new file) |

---

## Task 1: `score_to_stars` helper — TDD

**Files:**
- Create: `tests/test_score_to_stars.py`
- Modify: `langcoach/ui/analysis_report.py` (top of file, before `ScoreCircle`)

- [ ] **Step 1: Create the test file**

```python
# tests/test_score_to_stars.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langcoach.ui.analysis_report import score_to_stars


def test_perfect_score():
    assert score_to_stars(1.0) == "★★★★★"


def test_zero_score():
    assert score_to_stars(0.0) == "☆☆☆☆☆"


def test_none_score():
    assert score_to_stars(None) == "☆☆☆☆☆"


def test_round_up():
    # 0.78 * 5 = 3.9 → round → 4
    assert score_to_stars(0.78) == "★★★★☆"


def test_round_down():
    # 0.62 * 5 = 3.1 → round → 3
    assert score_to_stars(0.62) == "★★★☆☆"


def test_midpoint():
    # 0.50 * 5 = 2.5 → round → 2 (Python banker's rounding)
    assert score_to_stars(0.50) == "★★☆☆☆"


def test_high_score():
    # 0.95 * 5 = 4.75 → round → 5
    assert score_to_stars(0.95) == "★★★★★"


def test_low_score():
    # 0.18 * 5 = 0.9 → round → 1
    assert score_to_stars(0.18) == "★☆☆☆☆"


def test_always_five_chars():
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        s = score_to_stars(v)
        assert len(s) == 5, f"score_to_stars({v}) returned {s!r} (len {len(s)})"
```

- [ ] **Step 2: Run tests — expect ImportError (function not yet defined)**

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS
python3 -m pytest tests/test_score_to_stars.py -v
```

Expected: `ImportError: cannot import name 'score_to_stars'`

- [ ] **Step 3: Add `score_to_stars` to `analysis_report.py`**

Insert immediately after the imports block, before `class ScoreCircle` (line ~16):

```python
def score_to_stars(score: Optional[float]) -> str:
    """Convert a 0.0–1.0 score to a 5-char Unicode star string (e.g. '★★★☆☆')."""
    if score is None:
        return "☆☆☆☆☆"
    n = round(score * 5)
    return "★" * n + "☆" * (5 - n)
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
python3 -m pytest tests/test_score_to_stars.py -v
```

Expected: 9 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_score_to_stars.py langcoach/ui/analysis_report.py
git commit -m "feat: add score_to_stars helper with tests"
```

---

## Task 2: `StarBadge` widget + report header

**Files:**
- Modify: `langcoach/ui/analysis_report.py`
  - Add `StarBadge` class after `ScoreCircle` class
  - Update `_build_header()` (lines 102–133)
  - Update `load_report()` (line 462)

- [ ] **Step 1: Add `StarBadge` class**

Insert after the `ScoreCircle` class (after line 64), before `class AnalysisReportWidget`:

```python
class StarBadge(QFrame):
    """Compact gold badge showing star rating (e.g. ★★★★☆  4/5)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background: #c8a84b18;"
            "border: 1px solid #c8a84b44;"
            "border-radius: 8px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._stars_lbl = QLabel("☆☆☆☆☆")
        self._stars_lbl.setStyleSheet(
            "color: #c8a84b; background: transparent; border: none; font-size: 15px;"
        )
        layout.addWidget(self._stars_lbl)

        self._num_lbl = QLabel("—/5")
        self._num_lbl.setStyleSheet(
            f"color: #c8a84b; background: transparent; border: none;"
            f" font-size: {T['font_size_sm']}px; font-weight: 600;"
        )
        layout.addWidget(self._num_lbl)

    def set_score(self, score: Optional[float]):
        self._stars_lbl.setText(score_to_stars(score))
        if score is None:
            self._num_lbl.setText("—/5")
        else:
            self._num_lbl.setText(f"{round(score * 5)}/5")
```

- [ ] **Step 2: Update `_build_header()` to add `self._star_badge`**

In `_build_header()`, replace the last two lines:

```python
        layout.addLayout(info_col)
        layout.addStretch()
```

with:

```python
        layout.addLayout(info_col)
        layout.addStretch()
        self._star_badge = StarBadge(header)
        layout.addWidget(self._star_badge)
```

- [ ] **Step 3: Update `load_report()` to refresh the badge**

In `load_report()`, after the existing line `self._score_circle.set_score(score)` (line 462), add:

```python
        self._star_badge.set_score(score)
```

- [ ] **Step 4: Manual smoke test**

Run the app and open an analysed session report. Verify:
- The `StarBadge` appears on the right side of the report header
- Score `None` shows `☆☆☆☆☆  —/5`
- A real score (e.g. 0.78) shows `★★★★☆  4/5`
- The `ScoreCircle` arc is unchanged

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS
python3 -m langcoach
```

- [ ] **Step 5: Commit**

```bash
git add langcoach/ui/analysis_report.py
git commit -m "feat: add StarBadge widget to report header"
```

---

## Task 3: Stars in dashboard session list

**Files:**
- Modify: `langcoach/ui/dashboard_panel.py` (around line 412)

- [ ] **Step 1: Add import of `score_to_stars`**

At the top of `dashboard_panel.py`, find the existing imports from `langcoach.ui` (or add after the last `from langcoach` import) and add:

```python
from langcoach.ui.analysis_report import score_to_stars
```

- [ ] **Step 2: Add stars `QLabel` after the `%` label**

In `dashboard_panel.py`, find the block (lines 412–419):

```python
        q = s.get("quality_score")
        if q is not None:
            pct = int(q * 100)
            qc = T["success"] if pct >= 70 else T["warning"] if pct >= 40 else T["error"]
            ql = QLabel(f"{pct}%")
            ql.setFont(QFont(T["font_mono"], T["font_size_sm"]))
            ql.setStyleSheet(f"color:{qc}; border:none;")
            top.addWidget(ql)
```

Replace with:

```python
        q = s.get("quality_score")
        if q is not None:
            pct = int(q * 100)
            qc = T["success"] if pct >= 70 else T["warning"] if pct >= 40 else T["error"]
            ql = QLabel(f"{pct}%")
            ql.setFont(QFont(T["font_mono"], T["font_size_sm"]))
            ql.setStyleSheet(f"color:{qc}; border:none;")
            top.addWidget(ql)
            sl = QLabel(score_to_stars(q))
            sl.setFont(QFont(T["font_mono"], T["font_size_sm"]))
            sl.setStyleSheet("color:#c8a84b; border:none;")
            top.addWidget(sl)
```

- [ ] **Step 3: Manual smoke test**

Run the app and open the dashboard. Verify:
- Sessions with a `quality_score` show both `78%` and `★★★★☆` side by side
- Sessions without a score show neither (unchanged behaviour)
- Layout doesn't overflow or push other elements off-screen

```bash
cd /Users/franckmarandet/Documents/WORK/QUANTELYS/APPs/ElProfessor/MacOS
python3 -m langcoach
```

- [ ] **Step 4: Commit**

```bash
git add langcoach/ui/dashboard_panel.py
git commit -m "feat: add star rating to dashboard session list"
```

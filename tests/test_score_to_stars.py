import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Mock PyQt6 and config to allow testing without full GUI dependencies
from unittest.mock import MagicMock
sys.modules['PyQt6'] = MagicMock()
sys.modules['PyQt6.QtWidgets'] = MagicMock()
sys.modules['PyQt6.QtCore'] = MagicMock()
sys.modules['PyQt6.QtGui'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['config.theme'] = MagicMock()

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

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

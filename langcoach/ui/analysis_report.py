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
                ex_lbl = QLabel(f"\"{example}\"")
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

    def _build_suggestions_section(self, suggestions: list) -> QFrame:
        """Placeholder — full implementation in Task 6."""
        card, body = self._make_section_card(f"MÉMOIRES SUGGÉRÉES  ({len(suggestions)})")
        return card

    # ── Load report ───────────────────────────────────────────

    def load_report(
        self,
        score,
        analysis: dict,
        suggestions: list,
        session_info=None,
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

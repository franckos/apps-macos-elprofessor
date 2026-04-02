"""
LangCoach — Dashboard Panel
Per-profile analytics: Vue globale / Erreurs / Sessions / Leçons
"""
import datetime
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTabWidget, QTextEdit, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush

from config.theme import T
from core.database import Database
from core.stats_engine import StatsEngine
from langcoach.ui.analysis_report import score_to_stars


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

        # Bar using proportional layout stretch
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

        ts = s.get("started_at", 0) / 1000
        date_str = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

        top = QHBoxLayout()

        # Titre auto-généré ou date brute
        title_text = s.get("title") or date_str
        title_lbl = QLabel(title_text)
        title_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        title_lbl.setStyleSheet(
            f"color:{T['text_primary']}; border:none; font-weight:bold;"
            if s.get("title") else
            f"color:{T['text_primary']}; border:none;"
        )
        top.addWidget(title_lbl)

        # Date en secondaire si on a un titre
        if s.get("title"):
            date_sec = QLabel(date_str)
            date_sec.setFont(QFont(T["font_mono"], T["font_size_xs"]))
            date_sec.setStyleSheet(f"color:{T['text_muted']}; border:none;")
            top.addWidget(date_sec)

        top.addStretch()

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

        # Bouton Analyser si pas encore de résumé et au moins un échange
        if not s.get("summary") and s.get("exchange_count", 0) > 0:
            analyse_btn = QPushButton("🤖 Analyser")
            analyse_btn.setFixedHeight(26)
            analyse_btn.setStyleSheet(f"""
                QPushButton {{ background:#1a2a1a; color:#4aaa4a; border:1px solid #2a4a2a;
                    border-radius:{T['radius_sm']}px; padding:0 10px; font-size:{T['font_size_xs']}px; }}
                QPushButton:hover {{ background:#2a3a2a; }}
                QPushButton:disabled {{ color:{T['text_muted']}; border-color:{T['border']}; }}
            """)
            sid = s["id"]
            analyse_btn.clicked.connect(
                lambda _, sid=sid, btn=analyse_btn, lay=layout: self._analyse_session(sid, btn, lay)
            )
            top.addWidget(analyse_btn)

        # Bouton supprimer
        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("Supprimer cette session")
        del_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{T['text_muted']}; border:none;
                border-radius:{T['radius_sm']}px; font-size:{T['font_size_sm']}px; }}
            QPushButton:hover {{ color:{T['error']}; background:#2a1a1a; }}
        """)
        sid = s["id"]
        del_btn.clicked.connect(
            lambda _, sid=sid, card=w: self._delete_session(sid, card)
        )
        top.addWidget(del_btn)

        layout.addLayout(top)

        meta = QLabel(
            f"{s['language'].capitalize()} · {s['level']} · {s['topic']}  |  "
            f"{s['exchange_count']} échanges · {s['error_count']} erreurs"
        )
        meta.setFont(QFont(T["font_body"], T["font_size_xs"]))
        meta.setStyleSheet(f"color:{T['text_muted']}; border:none;")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        if s.get("summary"):
            summary_lbl = QLabel(s["summary"])
            summary_lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
            summary_lbl.setStyleSheet(f"color:{T['text_secondary']}; border:none;")
            summary_lbl.setWordWrap(True)
            layout.addWidget(summary_lbl)

        return w

    def _analyse_session(self, session_id: str, btn: QPushButton, layout: QVBoxLayout):
        if not self._stats:
            return
        btn.setEnabled(False)
        btn.setText("Analyse…")

        def on_done(score, analysis):
            summary = analysis.get("summary", "") if isinstance(analysis, dict) else str(analysis)
            def update_ui():
                if self._profile:
                    self._refresh_sessions(self._profile["id"])
            QTimer.singleShot(0, update_ui)

        self._stats.analyze_session_by_id(session_id, on_done)

    def _delete_session(self, session_id: str, card: QWidget):
        reply = QMessageBox.question(
            self,
            "Supprimer la session",
            "Supprimer définitivement cette session et tous ses échanges ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_session(session_id)
            card.setVisible(False)
            card.deleteLater()

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
            tip = QLabel(lesson["tip"])
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
        self._ai_btn.setText("Analyse en cours…")
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
            try:
                result = run()
            except Exception as e:
                result = f"Erreur lors de l'analyse : {e}"
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

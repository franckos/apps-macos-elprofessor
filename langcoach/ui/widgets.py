"""
LangCoach — Custom Widgets
StatusOrb, ChatBubble, AnimatedButton, WaveformWidget, ToastNotification
"""

import math
import time
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QGraphicsOpacityEffect, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QRect, QPoint, pyqtProperty, QSize,
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont,
    QLinearGradient, QRadialGradient, QPainterPath,
)

from config.theme import T


# ── Status Orb ────────────────────────────────────────────────

class StatusOrb(QWidget):
    """Indicateur d'état animé — cercle lumineux pulsant"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._color = QColor(T["text_muted"])
        self._animated = False
        self._alpha = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._phase = 0.0

    def set_color(self, hex_color: str):
        self._color = QColor(hex_color)
        self.update()

    def set_animated(self, active: bool):
        self._animated = active
        if active:
            self._timer.start(40)
        else:
            self._timer.stop()
            self._alpha = 1.0
            self.update()

    def _pulse(self):
        self._phase += 0.15
        self._alpha = 0.5 + 0.5 * math.sin(self._phase)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self._color)
        color.setAlphaF(self._alpha)

        # Glow effect
        glow = QRadialGradient(7, 7, 7)
        glow_color = QColor(self._color)
        glow_color.setAlphaF(self._alpha * 0.3)
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 14, 14)

        # Core dot
        p.setBrush(QBrush(color))
        p.drawEllipse(3, 3, 8, 8)


# ── Chat Bubble ───────────────────────────────────────────────

class ChatBubble(QWidget):
    """Bulle de conversation style WhatsApp dark"""

    def __init__(self, text: str, role: str = "user", assistant_name: str = "Coach", parent=None):
        super().__init__(parent)
        self._role = role
        self._finalized = False
        self.on_replay: Optional[Callable] = None
        self._replay_btn: Optional[QPushButton] = None

        is_user = role == "user"

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3)
        outer.setSpacing(0)

        if is_user:
            outer.addStretch()

        # ── Bubble container ──────────────────────────────────
        self._container = QWidget()
        self._container.setMaximumWidth(480)
        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(14, 10, 14, 8)
        inner.setSpacing(4)

        if is_user:
            # Fond terracotta solide, texte blanc
            self._container.setStyleSheet(f"""
                QWidget {{
                    background-color: #3D2010;
                    border-radius: 18px;
                    border-bottom-right-radius: 4px;
                }}
            """)
        else:
            # Fond sombre légèrement différent du bg, texte clair
            self._container.setStyleSheet(f"""
                QWidget {{
                    background-color: #252529;
                    border-radius: 18px;
                    border-bottom-left-radius: 4px;
                }}
            """)

        # Nom du coach (AI uniquement) — en accent, au-dessus du texte
        if not is_user:
            name_lbl = QLabel(assistant_name)
            name_lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
            name_lbl.setStyleSheet(f"""
                color: {T['accent']};
                background: transparent;
                font-weight: 600;
            """)
            inner.addWidget(name_lbl)

        # Texte principal
        self._text_label = QLabel(text)
        self._text_label.setFont(QFont(T["font_body"], T["font_size_md"]))
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_color = "#FFFFFF" if is_user else T["text_primary"]
        self._text_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        inner.addWidget(self._text_label)

        # Timestamp — aligné à droite dans une row
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(6)
        time_row.addStretch()

        if not is_user:
            self._replay_btn = QPushButton("▶")
            self._replay_btn.setFixedSize(20, 20)
            self._replay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._replay_btn.setToolTip("Rejouer")
            self._replay_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: rgba(255,255,255,0.25);
                    font-size: 9px;
                    padding: 0;
                }
                QPushButton:hover { color: rgba(255,255,255,0.75); }
            """)
            self._replay_btn.setVisible(False)
            self._replay_btn.clicked.connect(lambda: self.on_replay() if self.on_replay else None)
            time_row.addWidget(self._replay_btn)

        self._time_label = QLabel(self._get_time())
        self._time_label.setFont(QFont(T["font_mono"], T["font_size_xs"] - 1))
        time_color = "rgba(255,255,255,0.45)" if is_user else T["text_muted"]
        self._time_label.setStyleSheet(f"color: {time_color}; background: transparent;")
        time_row.addWidget(self._time_label)
        inner.addLayout(time_row)

        outer.addWidget(self._container)

        if not is_user:
            outer.addStretch()

        # Fade-in
        self._opacity = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(T["anim_normal"])
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def set_text(self, text: str):
        self._text_label.setText(text)

    def finalize(self):
        self._finalized = True
        self._time_label.setText(self._get_time())
        if self._replay_btn is not None:
            self._replay_btn.setVisible(True)

    def _get_time(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M")


# ── Animated Button ───────────────────────────────────────────

class AnimatedButton(QPushButton):
    """Bouton avec micro-animations hover/press"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._setup_style()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 {T['spacing_md']}px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {T['bg_hover']};
                color: {T['text_primary']};
                border-color: {T['accent']};
            }}
            QPushButton:pressed {{
                background-color: {T['accent_soft']};
                color: {T['accent']};
                border-color: {T['accent']};
            }}
            QPushButton:checked {{
                background-color: {T['accent_soft']};
                color: {T['accent']};
                border-color: {T['accent']};
            }}
            QPushButton:disabled {{
                opacity: {T['opacity_disabled']};
            }}
        """)


# ── Waveform Widget ───────────────────────────────────────────

class WaveformWidget(QWidget):
    """Visualiseur de forme d'onde animé (faux waveform décoratif)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._bars = [0.15] * 20
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_bars)
        self._phase = 0.0
        self.setStyleSheet("background: transparent;")

    def start(self):
        self._active = True
        self._timer.start(60)

    def stop(self):
        self._active = False
        self._timer.stop()
        self._bars = [0.1] * 20
        self.update()

    def _update_bars(self):
        import random
        self._phase += 0.2
        for i in range(len(self._bars)):
            if self._active:
                target = 0.2 + 0.7 * abs(math.sin(self._phase + i * 0.4)) * random.uniform(0.5, 1.0)
            else:
                target = 0.1
            self._bars[i] += (target - self._bars[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_width = max(2, (w - len(self._bars)) // len(self._bars))
        gap = 2
        total_w = len(self._bars) * (bar_width + gap)
        x_start = (w - total_w) // 2

        for i, val in enumerate(self._bars):
            bar_h = max(3, int(val * h))
            x = x_start + i * (bar_width + gap)
            y = (h - bar_h) // 2

            color = QColor(T["accent"])
            alpha = int(80 + 175 * val) if self._active else 40
            color.setAlpha(alpha)

            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, bar_width, bar_h, 1, 1)


# ── Toast Notification ────────────────────────────────────────

class ToastNotification(QWidget):
    """Notification moderne — bordure gauche colorée, icône cercle, titre + message + fermer."""

    _TYPES = {
        "success": {"title": "Succès",        "color": "#2ECC71", "icon": "✓", "auto_close": True},
        "error":   {"title": "Erreur",         "color": "#E74C3C", "icon": "✕", "auto_close": False},
        "warning": {"title": "Avertissement",  "color": "#F39C12", "icon": "!",  "auto_close": False},
        "info":    {"title": "Info",           "color": T["accent"], "icon": "i", "auto_close": True},
    }

    def __init__(self, message: str, kind: str = "success", parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._dismissed = False

        cfg = self._TYPES.get(kind, self._TYPES["info"])
        color = cfg["color"]

        self.setFixedWidth(320)
        self.setObjectName("toast")
        self.setStyleSheet(f"""
            QWidget#toast {{
                background: {T['bg_card']};
                border-top: 1px solid {T['border']};
                border-right: 1px solid {T['border']};
                border-bottom: 1px solid {T['border']};
                border-left: 4px solid {color};
                border-radius: {T['radius_md']}px;
            }}
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 12, 14)
        outer.setSpacing(12)

        # Icône cercle coloré
        icon_lbl = QLabel(cfg["icon"])
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        icon_lbl.setStyleSheet(f"""
            color: {color};
            background: transparent;
            border: 2px solid {color};
            border-radius: 16px;
            font-weight: bold;
        """)
        outer.addWidget(icon_lbl)

        # Titre + message
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(cfg["title"])
        title_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        title_lbl.setStyleSheet(f"color: {T['text_primary']}; font-weight: bold; background: transparent;")
        text_col.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
        msg_lbl.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        msg_lbl.setWordWrap(True)
        text_col.addWidget(msg_lbl)

        outer.addLayout(text_col, 1)

        # Bouton fermer
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T['text_muted']};
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{ color: {T['text_primary']}; }}
        """)
        close_btn.clicked.connect(self._dismiss)
        outer.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        # Opacité
        self._opacity = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(250)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self.close)

        if cfg["auto_close"]:
            QTimer.singleShot(4000, self._dismiss)

    def _dismiss(self):
        if not self._dismissed:
            self._dismissed = True
            self._fade_out.start()

    def show_at(self, x: int, y: int):
        """x, y sont des coordonnées écran (globales)."""
        self.move(x + 30, y)
        self.show()
        self.raise_()
        self.activateWindow()

        self._slide = QPropertyAnimation(self, b"pos")
        self._slide.setDuration(220)
        self._slide.setStartValue(QPoint(x + 30, y))
        self._slide.setEndValue(QPoint(x, y))
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide.start()

        self._fade_in.start()

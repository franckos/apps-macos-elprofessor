"""
LangCoach — Custom Widgets
StatusOrb, ChatBubble, AnimatedButton, WaveformWidget, ToastNotification
"""

import math
import time
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
    """Bulle de conversation avec animation d'apparition"""

    def __init__(self, text: str, role: str = "user", parent=None):
        super().__init__(parent)
        self._role = role
        self._finalized = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        if role == "user":
            layout.addStretch()

        # Container
        self._container = QWidget()
        self._container.setMaximumWidth(600)
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(14, 10, 14, 10)
        container_layout.setSpacing(4)

        # Role label
        role_label = QLabel("You" if role == "user" else "LangCoach")
        role_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        role_label.setStyleSheet(f"""
            color: {T['text_muted']};
            background: transparent;
            letter-spacing: 0.5px;
        """)
        container_layout.addWidget(role_label)

        # Text
        self._text_label = QLabel(text)
        self._text_label.setFont(QFont(T["font_body"], T["font_size_md"]))
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._text_label.setStyleSheet(f"""
            color: {T['text_primary']};
            background: transparent;
            line-height: 1.6;
        """)
        container_layout.addWidget(self._text_label)

        # Timestamp
        self._time_label = QLabel(self._get_time())
        self._time_label.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        self._time_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        container_layout.addWidget(self._time_label)

        if role == "user":
            self._container.setStyleSheet(f"""
                QWidget {{
                    background-color: {T['bubble_user_bg']};
                    border: 1px solid {T['bubble_user_border']};
                    border-radius: {T['radius_lg']}px;
                    border-bottom-right-radius: {T['radius_sm']}px;
                }}
            """)
        else:
            self._container.setStyleSheet(f"""
                QWidget {{
                    background-color: {T['bubble_ai_bg']};
                    border: 1px solid {T['bubble_ai_border']};
                    border-radius: {T['radius_lg']}px;
                    border-bottom-left-radius: {T['radius_sm']}px;
                }}
            """)

        layout.addWidget(self._container)

        if role == "assistant":
            layout.addStretch()

        # Fade-in animation
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
        """Marque la bulle comme complète"""
        self._finalized = True
        self._time_label.setText(self._get_time())

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
    """Notification flottante qui disparaît automatiquement"""

    COLORS = {
        "success": T["success"],
        "error":   T["error"],
        "warning": T["warning"],
        "info":    T["accent"],
    }

    def __init__(self, message: str, kind: str = "info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        color = self.COLORS.get(kind, T["accent"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        label = QLabel(message)
        label.setFont(QFont(T["font_body"], T["font_size_sm"]))
        label.setStyleSheet(f"""
            color: {T['text_primary']};
            background: transparent;
        """)
        layout.addWidget(label)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {color};
                border-radius: {T['radius_md']}px;
            }}
        """)
        self.setFixedWidth(300)
        self.adjustSize()

        # Fade in → wait → fade out
        self._opacity = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self._opacity)

        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.close)

        self._fade_in.start()
        QTimer.singleShot(2500, self._fade_out.start)

    def show_at(self, x: int, y: int):
        self.move(x, y)
        self.show()
        self.raise_()

"""
LangCoach — Main Window
UI principale de l'application
"""

import sys
import threading
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QFrame,
    QSizePolicy, QTextEdit, QLineEdit, QStackedWidget,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QThread, QSize, QRect,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QBrush, QPen,
    QLinearGradient, QFontDatabase, QIcon, QKeySequence,
    QShortcut, QPixmap,
)

from config.theme import T
from config.settings import (
    TEACHER_STYLES, LEVELS, TARGET_LANGUAGES,
    CONVERSATION_TOPICS, NATIVE_LANGUAGES, COACHES,
    load_settings, save_settings,
)
from core.session import SessionManager, SessionState
from ui.settings_panel import SettingsPanel
from ui.widgets import (
    StatusOrb, ChatBubble, AnimatedButton,
    WaveformWidget, ToastNotification,
)


class MainWindow(QMainWindow):

    # Signaux thread-safe pour les callbacks depuis les threads audio/LLM
    sig_state_changed = pyqtSignal(object)
    sig_user_transcript = pyqtSignal(str)
    sig_assistant_token = pyqtSignal(str)
    sig_assistant_done = pyqtSignal(str)
    sig_models_ready = pyqtSignal(dict)
    sig_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.session = SessionManager()
        self._current_ai_bubble = None
        self._current_ai_text = ""
        self._settings_visible = False
        self._ptt_held = False

        self._setup_window()
        self._setup_fonts()
        self._apply_theme()
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._start_session()

    # ── Setup ─────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("LangCoach")
        self.resize(T["window_width"], T["window_height"])
        self.setMinimumSize(T["window_min_width"], T["window_min_height"])
        self.setWindowFlags(Qt.WindowType.Window)

    def _setup_fonts(self):
        # Les polices système en fallback si Google Fonts pas disponibles
        self._font_display = QFont(T["font_display"], T["font_size_xl"])
        self._font_body = QFont(T["font_body"], T["font_size_md"])
        self._font_mono = QFont(T["font_mono"], T["font_size_sm"])

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {T['bg_primary']};
            }}
            QWidget {{
                background-color: transparent;
                color: {T['text_primary']};
                font-family: '{T['font_body']}', 'SF Pro Display', system-ui;
                font-size: {T['font_size_md']}px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {T['text_muted']};
                border-radius: 2px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QToolTip {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                padding: 6px 10px;
                font-size: {T['font_size_sm']}px;
            }}
        """)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"background-color: {T['bg_primary']};")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────
        self._sidebar = self._build_sidebar()
        root.addWidget(self._sidebar)

        # ── Main area ──────────────────────────────────────────
        main_area = QWidget()
        main_area.setStyleSheet(f"background-color: {T['bg_primary']};")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = self._build_header()
        main_layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {T['border']}; border: none;")
        main_layout.addWidget(sep)

        # Chat area
        self._chat_scroll = self._build_chat_area()
        main_layout.addWidget(self._chat_scroll, 1)

        # Input bar
        input_bar = self._build_input_bar()
        main_layout.addWidget(input_bar)

        root.addWidget(main_area, 1)

        # ── Settings panel (overlay) ───────────────────────────
        self._settings_panel = SettingsPanel(self.settings, self)
        self._settings_panel.setVisible(False)
        self._settings_panel.on_settings_changed = self._on_settings_changed
        self._settings_panel.on_close = self._toggle_settings

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(T["sidebar_width"])
        sidebar.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-right: 1px solid {T['border']};
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(T["spacing_md"], T["spacing_xl"], T["spacing_md"], T["spacing_md"])
        layout.setSpacing(T["spacing_sm"])

        # Logo / Title
        logo_area = QWidget()
        logo_layout = QVBoxLayout(logo_area)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(4)

        title = QLabel("LangCoach")
        title.setFont(QFont(T["font_display"], T["font_size_2xl"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        logo_layout.addWidget(title)

        tagline = QLabel("Your AI language partner")
        tagline.setFont(QFont(T["font_body"], T["font_size_sm"]))
        tagline.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        logo_layout.addWidget(tagline)

        layout.addWidget(logo_area)
        layout.addSpacing(T["spacing_xl"])

        # Status orb + état
        orb_row = QHBoxLayout()
        orb_row.setSpacing(T["spacing_sm"])
        self._status_orb = StatusOrb()
        orb_row.addWidget(self._status_orb)

        self._status_label = QLabel("Initializing…")
        self._status_label.setFont(QFont(T["font_body"], T["font_size_sm"]))
        self._status_label.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        orb_row.addWidget(self._status_label, 1)
        layout.addLayout(orb_row)

        layout.addSpacing(T["spacing_lg"])

        # Session info cards
        self._info_cards = {}
        infos = [
            ("coach", "🎓", "Coach", "Angela"),
            ("language", "🌐", "Language", "English"),
            ("level", "📊", "Level", "B1"),
            ("style", "🎭", "Style", "Bienveillant"),
            ("topic", "💬", "Topic", "Free talk"),
        ]
        for key, emoji, label, default in infos:
            card = self._make_info_card(emoji, label, default)
            self._info_cards[key] = card[1]  # store value label
            layout.addWidget(card[0])

        layout.addSpacing(T["spacing_lg"])

        # Waveform
        self._waveform = WaveformWidget()
        self._waveform.setFixedHeight(48)
        layout.addWidget(self._waveform)

        layout.addStretch()

        # Model badges
        self._model_badge = QLabel("● Offline models")
        self._model_badge.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        self._model_badge.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        self._model_badge.setWordWrap(True)
        layout.addWidget(self._model_badge)

        # Version
        version = QLabel("v1.0.0 — 100% local")
        version.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        version.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(version)

        return sidebar

    def _make_info_card(self, emoji: str, label: str, value: str):
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border-radius: {T['radius_md']}px;
                border: 1px solid {T['border']};
            }}
            QWidget:hover {{
                border-color: {T['accent']};
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        icon = QLabel(emoji)
        icon.setFont(QFont(T["font_body"], T["font_size_md"]))
        icon.setStyleSheet("background: transparent; border: none;")
        icon.setFixedWidth(22)
        layout.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        lbl = QLabel(label.upper())
        lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
        lbl.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none; letter-spacing: 1px;")
        text_col.addWidget(lbl)

        val = QLabel(value)
        val.setFont(QFont(T["font_body"], T["font_size_sm"]))
        val.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        val.setWordWrap(True)
        text_col.addWidget(val)

        layout.addLayout(text_col, 1)
        return card, val

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(f"background-color: {T['bg_secondary']};")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(T["spacing_lg"], 0, T["spacing_lg"], 0)
        layout.setSpacing(T["spacing_sm"])

        # Session title
        self._session_title = QLabel("New session")
        self._session_title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        self._session_title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        layout.addWidget(self._session_title, 1)

        # Header buttons
        btn_style = f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 8px 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{
                background-color: {T['bg_hover']};
                color: {T['text_primary']};
                border-color: {T['accent']};
            }}
            QPushButton:pressed {{
                background-color: {T['accent_soft']};
            }}
        """

        self._btn_reset = QPushButton("↺  New session")
        self._btn_reset.setStyleSheet(btn_style)
        self._btn_reset.setFixedHeight(36)
        self._btn_reset.setToolTip("Reset conversation (R)")
        self._btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self._btn_reset)

        self._btn_settings = QPushButton("⚙  Settings")
        self._btn_settings.setStyleSheet(btn_style)
        self._btn_settings.setFixedHeight(36)
        self._btn_settings.setToolTip("Open settings (S)")
        self._btn_settings.clicked.connect(self._toggle_settings)
        layout.addWidget(self._btn_settings)

        return header

    def _build_chat_area(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {T['bg_primary']};
                border: none;
            }}
        """)

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background-color: {T['bg_primary']};")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(
            T["spacing_xl"], T["spacing_lg"],
            T["spacing_xl"], T["spacing_lg"]
        )
        self._chat_layout.setSpacing(T["spacing_sm"])
        self._chat_layout.addStretch()

        scroll.setWidget(self._chat_container)
        self._chat_scroll = scroll
        return scroll

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(90)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-top: 1px solid {T['border']};
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_md"], T["spacing_xl"], T["spacing_md"])
        layout.setSpacing(T["spacing_md"])

        # VAD toggle
        self._btn_vad = AnimatedButton("◉  Auto")
        self._btn_vad.setToolTip("Toggle auto-detect mode (A)")
        self._btn_vad.setFixedSize(90, 44)
        self._btn_vad.setCheckable(True)
        self._btn_vad.clicked.connect(self._toggle_vad)
        layout.addWidget(self._btn_vad)

        # Text input
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Type a message or hold Space to talk…")
        self._text_input.setFixedHeight(44)
        self._text_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 {T['spacing_md']}px;
                font-size: {T['font_size_md']}px;
                font-family: '{T['font_body']}';
            }}
            QLineEdit:focus {{
                border-color: {T['border_active']};
                background-color: {T['bg_hover']};
            }}
            QLineEdit::placeholder {{
                color: {T['text_muted']};
            }}
        """)
        self._text_input.returnPressed.connect(self._on_text_send)
        layout.addWidget(self._text_input, 1)

        # Send button
        self._btn_send = AnimatedButton("→")
        self._btn_send.setFixedSize(44, 44)
        self._btn_send.setToolTip("Send (Enter)")
        self._btn_send.clicked.connect(self._on_text_send)
        layout.addWidget(self._btn_send)

        # PTT button
        self._btn_ptt = AnimatedButton("🎤  Hold")
        self._btn_ptt.setToolTip("Hold to talk (Space)")
        self._btn_ptt.setFixedSize(100, 44)
        self._btn_ptt.pressed.connect(self._on_ptt_press)
        self._btn_ptt.released.connect(self._on_ptt_release)
        layout.addWidget(self._btn_ptt)

        # Stop button
        self._btn_stop = QPushButton("■")
        self._btn_stop.setFixedSize(44, 44)
        self._btn_stop.setToolTip("Stop speaking (Esc)")
        self._btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['error']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                font-size: {T['font_size_lg']}px;
            }}
            QPushButton:hover {{
                background-color: {T['error']};
                color: white;
                border-color: {T['error']};
            }}
        """)
        self._btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self._btn_stop)

        return bar

    # ── Signal connections ────────────────────────────────────

    def _connect_signals(self):
        self.sig_state_changed.connect(self._handle_state_change)
        self.sig_user_transcript.connect(self._add_user_bubble)
        self.sig_assistant_token.connect(self._handle_ai_token)
        self.sig_assistant_done.connect(self._handle_ai_done)
        self.sig_models_ready.connect(self._handle_models_ready)
        self.sig_error.connect(self._handle_error)

        # Session callbacks → signals (thread-safe)
        self.session.on_state_change = lambda s: self.sig_state_changed.emit(s)
        self.session.on_user_transcript = lambda t: self.sig_user_transcript.emit(t)
        self.session.on_assistant_token = lambda t: self.sig_assistant_token.emit(t)
        self.session.on_assistant_done = lambda t: self.sig_assistant_done.emit(t)
        self.session.on_models_ready = lambda s: self.sig_models_ready.emit(s)
        self.session.on_error = lambda e: self.sig_error.emit(e)

    def _setup_shortcuts(self):
        def _if_not_typing(action):
            """Only trigger shortcut when text input doesn't have focus."""
            if not self._text_input.hasFocus():
                action()

        QShortcut(QKeySequence("R"), self, lambda: _if_not_typing(self._on_reset))
        QShortcut(QKeySequence("S"), self, lambda: _if_not_typing(self._toggle_settings))
        QShortcut(QKeySequence("A"), self, lambda: _if_not_typing(self._btn_vad.click))
        QShortcut(QKeySequence("Escape"), self, self._on_stop)

    # ── Session ───────────────────────────────────────────────

    def _start_session(self):
        self._update_sidebar_info()
        self._update_session_title()
        self.session.initialize(self.settings)

    # ── Slot handlers ─────────────────────────────────────────

    def _handle_state_change(self, state: SessionState):
        labels = {
            SessionState.IDLE:       ("Idle", T["text_muted"]),
            SessionState.LOADING:    ("Loading models…", T["warning"]),
            SessionState.READY:      ("Ready", T["success"]),
            SessionState.LISTENING:  ("Listening…", T["accent"]),
            SessionState.PROCESSING: ("Thinking…", T["info"]),
            SessionState.SPEAKING:   ("Speaking…", T["accent"]),
            SessionState.ERROR:      ("Error", T["error"]),
        }
        text, color = labels.get(state, ("Unknown", T["text_muted"]))
        self._status_label.setText(text)
        self._status_orb.set_color(color)
        self._status_orb.set_animated(state in (
            SessionState.LISTENING, SessionState.PROCESSING, SessionState.SPEAKING
        ))

        if state == SessionState.LISTENING:
            self._waveform.start()
        else:
            self._waveform.stop()

    def _handle_models_ready(self, status: dict):
        stt_ok = "✓" if status.get("stt") else "✗"
        tts_ok = "✓" if status.get("tts") else "✗"
        provider = self.session.tts_provider
        self._model_badge.setText(
            f"STT {stt_ok}  LLM ✓  TTS {tts_ok}\n{provider}"
        )
        self._model_badge.setStyleSheet(f"color: {T['success']}; background: transparent;")

    def _coach_name(self) -> str:
        lang_key = self.settings.get("target_language", "english")
        coach_key = self.settings.get("coach", "angela")
        lang_coaches = COACHES.get(lang_key, COACHES["english"])
        coach = lang_coaches.get(coach_key) or next(iter(lang_coaches.values()))
        return coach["name"]

    def _add_user_bubble(self, text: str):
        bubble = ChatBubble(text, role="user")
        self._chat_layout.addWidget(bubble)
        self._scroll_to_bottom()
        self._current_ai_bubble = None
        self._current_ai_text = ""

    def _handle_ai_token(self, token: str):
        self._current_ai_text += token
        if self._current_ai_bubble is None:
            self._current_ai_bubble = ChatBubble("", role="assistant", assistant_name=self._coach_name())
            self._chat_layout.addWidget(self._current_ai_bubble)
        self._current_ai_bubble.set_text(self._current_ai_text)
        self._scroll_to_bottom()

    def _handle_ai_done(self, text: str):
        if self._current_ai_bubble:
            self._current_ai_bubble.set_text(text)
            self._current_ai_bubble.finalize()
        self._scroll_to_bottom()

    def _handle_error(self, msg: str):
        self._show_toast(f"Error: {msg}", kind="error")

    def _toggle_vad(self, checked: bool):
        if checked:
            self.session.start_listening_vad()
            self._btn_vad.setText("◉  Active")
        else:
            self.session.stop_listening_vad()
            self._btn_vad.setText("◉  Auto")

    def _on_ptt_press(self):
        if not self._ptt_held:
            self._ptt_held = True
            self.session.start_ptt()

    def _on_ptt_release(self):
        if self._ptt_held:
            self._ptt_held = False
            self.session.stop_ptt()

    def _on_text_send(self):
        text = self._text_input.text().strip()
        if text:
            self._text_input.clear()
            self.session.send_text(text)

    def _on_stop(self):
        self.session.stop_speaking()

    def _on_reset(self):
        # Clear chat
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.session.reset_session()
        self._show_toast("Session reset", kind="info")

    def _toggle_settings(self):
        self._settings_visible = not self._settings_visible
        self._settings_panel.setVisible(self._settings_visible)
        if self._settings_visible:
            # Position overlay
            self._settings_panel.setParent(self.centralWidget())
            self._settings_panel.resize(400, self.height())
            self._settings_panel.move(self.width() - 400, 0)
            self._settings_panel.raise_()
            self._settings_panel.show()
            self._btn_settings.setText("✕  Close")
        else:
            self._settings_panel.hide()
            self._btn_settings.setText("⚙  Settings")

    def _on_settings_changed(self, new_settings: dict):
        self.settings = new_settings
        save_settings(new_settings)
        self.session.update_settings(new_settings)
        self._update_sidebar_info()
        self._update_session_title()
        self._show_toast("Settings updated", kind="success")

    def _update_sidebar_info(self):
        lang_key = self.settings.get("target_language", "english")
        coach_key = self.settings.get("coach", "angela")
        level_key = self.settings.get("level", "B1")
        style_key = self.settings.get("teacher_style", "bienveillant")
        topic = self.settings.get("topic", "Free talk")

        lang = TARGET_LANGUAGES.get(lang_key, {})
        style = TEACHER_STYLES.get(style_key, {})
        lang_coaches = COACHES.get(lang_key, COACHES["english"])
        coach = lang_coaches.get(coach_key) or next(iter(lang_coaches.values()))

        if "coach" in self._info_cards:
            self._info_cards["coach"].setText(f"{coach.get('flag', '')} {coach.get('name', coach_key)}")
        if "language" in self._info_cards:
            self._info_cards["language"].setText(lang.get("label", lang_key))
        if "level" in self._info_cards:
            self._info_cards["level"].setText(f"{level_key} — {LEVELS.get(level_key, {}).get('desc', '')}")
        if "style" in self._info_cards:
            self._info_cards["style"].setText(f"{style.get('emoji', '')} {style.get('label', style_key)}")
        if "topic" in self._info_cards:
            self._info_cards["topic"].setText(topic)

    def _update_session_title(self):
        lang = self.settings.get("target_language", "english").capitalize()
        level = self.settings.get("level", "B1")
        topic = self.settings.get("topic", "Free talk")
        self._session_title.setText(f"{lang} · {level} · {topic}")

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def _show_toast(self, message: str, kind: str = "info"):
        toast = ToastNotification(message, kind=kind, parent=self.centralWidget())
        toast.show_at(self.width() - 300, 80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._settings_visible and self._settings_panel.isVisible():
            self._settings_panel.resize(400, self.height())
            self._settings_panel.move(self.width() - 400, 0)

    def closeEvent(self, event):
        self.session.shutdown()
        save_settings(self.settings)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            if not self._text_input.hasFocus():
                self._on_ptt_press()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._on_ptt_release()
        super().keyReleaseEvent(event)

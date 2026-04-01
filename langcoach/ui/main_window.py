"""
LangCoach — Main Window
UI principale de l'application
"""

import sys
import threading
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QTextEdit,
    QLineEdit,
    QStackedWidget,
    QGraphicsDropShadowEffect,
    QMenu,
    QDialog,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    QThread,
    QSize,
    QRect,
)
from PyQt6.QtGui import (
    QFont,
    QColor,
    QPalette,
    QPainter,
    QBrush,
    QPen,
    QLinearGradient,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QShortcut,
    QPixmap,
)

from config.theme import T
from config.settings import (
    TEACHER_STYLES,
    LEVELS,
    TARGET_LANGUAGES,
    CONVERSATION_TOPICS,
    NATIVE_LANGUAGES,
    COACHES,
    load_settings,
)
from core.database import Database
from core.stats_engine import StatsEngine
from core.memory_manager import MemoryManager
from core.session import SessionManager, SessionState
from ui.settings_panel import SettingsPanel
from ui.dashboard_panel import DashboardPanel
from ui.profile_screen import ProfileEditDialog, ProfileScreen, ProfileWizard
from ui.widgets import (
    StatusOrb,
    ChatBubble,
    AnimatedButton,
    WaveformWidget,
    ToastNotification,
)


class MainWindow(QMainWindow):

    # Signaux thread-safe pour les callbacks depuis les threads audio/LLM
    sig_state_changed = pyqtSignal(object)
    sig_user_transcript = pyqtSignal(str)
    sig_assistant_token = pyqtSignal(str)
    sig_assistant_done = pyqtSignal(str)
    sig_models_ready = pyqtSignal(dict)
    sig_error = pyqtSignal(str)
    sig_status_detail = pyqtSignal(str)

    def __init__(self, db: Database, profile: dict):
        super().__init__()
        self._db = db
        self._profile = profile
        self.settings = profile.get("settings", load_settings())
        self.session = SessionManager()
        self._stats = StatsEngine(db=db, llm=None)  # llm injected after model init
        self._memory_manager = MemoryManager(db=db, llm=None)
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
        self.setWindowTitle("Echo")
        self.resize(T["window_width"], T["window_height"])
        self.setMinimumSize(T["window_min_width"], T["window_min_height"])
        self.setWindowFlags(Qt.WindowType.Window)

    def _setup_fonts(self):
        # Les polices système en fallback si Google Fonts pas disponibles
        self._font_display = QFont(T["font_display"], T["font_size_xl"])
        self._font_body = QFont(T["font_body"], T["font_size_md"])
        self._font_mono = QFont(T["font_mono"], T["font_size_sm"])

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
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
        """
        )

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"background-color: {T['bg_primary']};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # No sidebar — info lives in settings panel
        self._info_cards = {}

        # ── Main area ──────────────────────────────────────────
        main_area = QWidget()
        main_area.setStyleSheet(f"background-color: {T['bg_primary']};")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._build_header()
        main_layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {T['border']}; border: none;")
        main_layout.addWidget(sep)

        # Stacked widget: index 0 = Session, index 1 = Dashboard
        self._main_stack = QStackedWidget()
        self._main_stack.setStyleSheet(f"background-color: {T['bg_primary']};")

        # Session tab (topic picker + chat + input bar)
        session_widget = QWidget()
        session_widget.setStyleSheet(f"background-color: {T['bg_primary']};")
        session_outer_layout = QVBoxLayout(session_widget)
        session_outer_layout.setContentsMargins(0, 0, 0, 0)
        session_outer_layout.setSpacing(0)

        # Inner stack: index 0 = topic picker, index 1 = chat area
        self._session_stack = QStackedWidget()
        self._session_stack.setStyleSheet(f"background-color: {T['bg_primary']};")

        # Index 0: topic picker
        self._topic_picker = self._build_topic_picker()
        self._session_stack.addWidget(self._topic_picker)

        # Index 1: chat area + input bar
        chat_widget = QWidget()
        chat_widget.setStyleSheet(f"background-color: {T['bg_primary']};")
        chat_vlayout = QVBoxLayout(chat_widget)
        chat_vlayout.setContentsMargins(0, 0, 0, 0)
        chat_vlayout.setSpacing(0)
        self._chat_scroll = self._build_chat_area()
        chat_vlayout.addWidget(self._chat_scroll, 1)
        self._input_bar = self._build_input_bar()
        chat_vlayout.addWidget(self._input_bar)
        self._session_stack.addWidget(chat_widget)

        session_outer_layout.addWidget(self._session_stack, 1)
        self._main_stack.addWidget(session_widget)

        # Dashboard tab
        self._dashboard_panel = DashboardPanel(db=self._db, stats_engine=self._stats)
        self._main_stack.addWidget(self._dashboard_panel)

        main_layout.addWidget(self._main_stack, 1)
        root.addWidget(main_area, 1)

        # ── Bottom status bar ──────────────────────────────────
        self._bottom_bar = self._build_bottom_bar()
        root.addWidget(self._bottom_bar)

        # ── Settings panel (overlay) ───────────────────────────
        self._settings_panel = SettingsPanel(self.settings, self)
        self._settings_panel.setVisible(False)
        self._settings_panel.on_settings_changed = self._on_settings_changed
        self._settings_panel.on_close = self._toggle_settings

    def _build_bottom_bar(self) -> QWidget:
        """Bottom status bar — logo / engine state orbs / activity detail"""
        bar = QWidget()
        bar.setFixedHeight(T["bottom_bar_height"])
        bar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-top: 1px solid {T['border']};
            }}
        """
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(T["spacing_lg"], 0, T["spacing_lg"], 0)
        layout.setSpacing(0)

        # ── Logo ───────────────────────────────────────────────
        logo = QLabel("echo")
        logo.setFont(QFont(T["font_display"], T["font_size_md"]))
        logo.setStyleSheet(
            f"color: {T['accent']}; background: transparent; "
            f"font-weight: 600; letter-spacing: 2px;"
        )
        layout.addWidget(logo)

        # ── Separator ─────────────────────────────────────────
        def _vsep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setFixedHeight(20)
            s.setStyleSheet(f"color: {T['border']}; background: transparent;")
            return s

        layout.addSpacing(T["spacing_lg"])
        layout.addWidget(_vsep())
        layout.addSpacing(T["spacing_md"])

        # ── Main state orb + label ────────────────────────────
        self._status_orb = StatusOrb()
        layout.addWidget(self._status_orb)
        layout.addSpacing(6)

        self._status_label = QLabel("Initialisation…")
        self._status_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        self._status_label.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        self._status_label.setFixedWidth(80)
        layout.addWidget(self._status_label)

        layout.addSpacing(T["spacing_md"])
        layout.addWidget(_vsep())
        layout.addSpacing(T["spacing_md"])

        # ── STT orb ────────────────────────────────────────────
        self._stt_orb = StatusOrb()
        self._stt_orb.set_color(T["text_muted"])
        layout.addWidget(self._stt_orb)
        layout.addSpacing(4)

        stt_lbl = QLabel("STT")
        stt_lbl.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        stt_lbl.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(stt_lbl)
        layout.addSpacing(T["spacing_md"])

        # ── LLM orb ────────────────────────────────────────────
        self._llm_orb = StatusOrb()
        self._llm_orb.set_color(T["text_muted"])
        layout.addWidget(self._llm_orb)
        layout.addSpacing(4)

        llm_lbl = QLabel("LLM")
        llm_lbl.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        llm_lbl.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(llm_lbl)
        layout.addSpacing(T["spacing_md"])

        # ── TTS / Kokoro orb ───────────────────────────────────
        self._tts_orb = StatusOrb()
        self._tts_orb.set_color(T["text_muted"])
        layout.addWidget(self._tts_orb)
        layout.addSpacing(4)

        self._tts_label = QLabel("TTS")
        self._tts_label.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        self._tts_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(self._tts_label)
        layout.addSpacing(T["spacing_md"])

        # ── Waveform (compact) ────────────────────────────────
        self._waveform = WaveformWidget()
        self._waveform.setFixedSize(56, 24)
        layout.addWidget(self._waveform)

        layout.addSpacing(T["spacing_md"])
        layout.addWidget(_vsep())
        layout.addSpacing(T["spacing_md"])

        # ── Status detail (right, expandable) ─────────────────
        self._status_detail_label = QLabel("")
        self._status_detail_label.setFont(QFont(T["font_mono"], T["font_size_xs"]))
        self._status_detail_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        self._status_detail_label.setMaximumWidth(420)
        layout.addWidget(self._status_detail_label, 1)

        return bar

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(T["sidebar_width"])
        sidebar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-right: 1px solid {T['border']};
            }}
        """
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(T["spacing_md"], T["spacing_xl"], T["spacing_md"], T["spacing_md"])
        layout.setSpacing(T["spacing_sm"])

        # Logo / Title
        logo_area = QWidget()
        logo_layout = QVBoxLayout(logo_area)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(4)

        title = QLabel("Echo")
        title.setFont(QFont(T["font_display"], T["font_size_2xl"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        logo_layout.addWidget(title)

        tagline = QLabel("Le coach vocal qui vous répond")
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

        self._status_label_sidebar = QLabel("Initialisation…")
        self._status_label_sidebar.setFont(QFont(T["font_body"], T["font_size_sm"]))
        self._status_label_sidebar.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        orb_row.addWidget(self._status_label_sidebar, 1)
        layout.addLayout(orb_row)

        layout.addSpacing(T["spacing_lg"])

        # Session info cards
        self._info_cards = {}
        infos = [
            ("coach", "🎓", "Coach", "Angela"),
            ("language", "🌐", "Langue", "Anglais"),
            ("level", "📊", "Niveau", "B1"),
            ("style", "🎭", "Style", "Bienveillant"),
            ("topic", "💬", "Sujet", "Conversation libre"),
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
        self._model_badge = QLabel("● Modèles hors ligne")
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
        card.setStyleSheet(
            f"""
            QWidget {{
                background-color: {T['bg_card']};
                border-radius: {T['radius_md']}px;
                border: 1px solid {T['border']};
            }}
            QWidget:hover {{
                border-color: {T['accent']};
            }}
        """
        )
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
        layout.setSpacing(0)

        self._tab_active_style = f"""
            QPushButton {{
                background-color: {T['bg_primary']}; color: {T['text_primary']};
                border: none; border-bottom: 2px solid {T['accent']};
                padding: 0 20px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
            }}
        """
        self._tab_inactive_style = f"""
            QPushButton {{
                background-color: transparent; color: {T['text_muted']};
                border: none; border-bottom: 2px solid transparent;
                padding: 0 20px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ color: {T['text_primary']}; }}
        """

        self._btn_tab_session = QPushButton("Session")
        self._btn_tab_session.setFixedHeight(64)
        self._btn_tab_session.setStyleSheet(self._tab_active_style)
        self._btn_tab_session.clicked.connect(lambda: self._switch_tab(0))
        layout.addWidget(self._btn_tab_session)

        self._btn_tab_dashboard = QPushButton("Dashboard")
        self._btn_tab_dashboard.setFixedHeight(64)
        self._btn_tab_dashboard.setStyleSheet(self._tab_inactive_style)
        self._btn_tab_dashboard.clicked.connect(lambda: self._switch_tab(1))
        layout.addWidget(self._btn_tab_dashboard)

        layout.addStretch()

        btn_style = f"""
            QPushButton {{
                background-color: {T['bg_card']}; color: {T['text_secondary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px;
                padding: 8px 16px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ background-color: {T['bg_hover']}; color: {T['text_primary']}; border-color: {T['accent']}; }}
            QPushButton:pressed {{ background-color: {T['accent_soft']}; }}
        """
        self._btn_finir = QPushButton("Analyser")
        self._btn_finir.setStyleSheet(btn_style)
        self._btn_finir.setFixedHeight(36)
        self._btn_finir.setToolTip("Analyser la session et extraire des mémoires")
        self._btn_finir.clicked.connect(self._on_finir_analyser)
        layout.addWidget(self._btn_finir)

        layout.addSpacing(4)

        self._btn_reset = QPushButton("↺  Nouveau")
        self._btn_reset.setStyleSheet(btn_style)
        self._btn_reset.setFixedHeight(36)
        self._btn_reset.setToolTip("Réinitialiser la conversation (R)")
        self._btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self._btn_reset)

        self._btn_settings = QPushButton("Paramètres")
        self._btn_settings.setStyleSheet(btn_style)
        self._btn_settings.setFixedHeight(36)
        self._btn_settings.setToolTip("Ouvrir les paramètres (S)")
        self._btn_settings.clicked.connect(self._toggle_settings)
        layout.addWidget(self._btn_settings)

        layout.addSpacing(4)

        self._btn_profile = QPushButton("")
        self._btn_profile.setStyleSheet(btn_style)
        self._btn_profile.setFixedHeight(36)
        self._btn_profile.setToolTip("Profil")
        self._btn_profile.clicked.connect(self._on_profile_menu)
        layout.addWidget(self._btn_profile)

        return header

    def _switch_tab(self, index: int):
        self._main_stack.setCurrentIndex(index)
        if index == 0:
            self._btn_tab_session.setStyleSheet(self._tab_active_style)
            self._btn_tab_dashboard.setStyleSheet(self._tab_inactive_style)
        else:
            self._btn_tab_session.setStyleSheet(self._tab_inactive_style)
            self._btn_tab_dashboard.setStyleSheet(self._tab_active_style)
            self._dashboard_panel.refresh()

    def _build_chat_area(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: {T['bg_primary']};
                border: none;
            }}
        """
        )

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background-color: {T['bg_primary']};")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(T["spacing_xl"], T["spacing_lg"], T["spacing_xl"], T["spacing_lg"])
        self._chat_layout.setSpacing(T["spacing_sm"])
        self._chat_layout.addStretch()

        scroll.setWidget(self._chat_container)
        self._chat_scroll = scroll
        return scroll

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(90)
        bar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-top: 1px solid {T['border']};
            }}
        """
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_md"], T["spacing_xl"], T["spacing_md"])
        layout.setSpacing(T["spacing_md"])

        # VAD toggle
        self._btn_vad = AnimatedButton("Auto")
        self._btn_vad.setToolTip("Activer/désactiver la détection automatique (A)")
        self._btn_vad.setFixedSize(72, 44)
        self._btn_vad.setCheckable(True)
        self._btn_vad.clicked.connect(self._toggle_vad)
        layout.addWidget(self._btn_vad)

        # Text input
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Écris un message ou maintiens Espace pour parler…")
        self._text_input.setFixedHeight(44)
        self._text_input.setStyleSheet(
            f"""
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
        """
        )
        self._text_input.returnPressed.connect(self._on_text_send)
        layout.addWidget(self._text_input, 1)

        # Send button
        self._btn_send = AnimatedButton("→")
        self._btn_send.setFixedSize(44, 44)
        self._btn_send.setToolTip("Send (Enter)")
        self._btn_send.clicked.connect(self._on_text_send)
        layout.addWidget(self._btn_send)

        # PTT button
        self._btn_ptt = AnimatedButton("Parler")
        self._btn_ptt.setToolTip("Maintenir pour parler (Espace)")
        self._btn_ptt.setFixedSize(100, 44)
        self._btn_ptt.pressed.connect(self._on_ptt_press)
        self._btn_ptt.released.connect(self._on_ptt_release)
        layout.addWidget(self._btn_ptt)

        # Stop button
        self._btn_stop = QPushButton("■")
        self._btn_stop.setFixedSize(44, 44)
        self._btn_stop.setToolTip("Arrêter la parole (Échap)")
        self._btn_stop.setStyleSheet(
            f"""
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
        """
        )
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
        self.sig_status_detail.connect(self._handle_status_detail)
        self._connect_session_signals()

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

        # Inject LLM into stats engine and memory manager once models are ready
        def _on_models_ready_with_llm(status: dict):
            self._stats._llm = self.session._llm
            self._memory_manager._llm = self.session._llm
            self._stats.set_memory_manager(self._memory_manager)
            # Inject memories into LLM system prompt
            memories = self._memory_manager.get_context_memories(self._profile["id"])
            if memories:
                from core.prompt_builder import build_system_prompt
                prompt = build_system_prompt(
                    self.settings,
                    user_name=self._profile.get("name", ""),
                    memories=memories,
                )
                self.session._llm.set_system_prompt(prompt)
            self.sig_models_ready.emit(status)

        self.session.on_models_ready = _on_models_ready_with_llm
        self.session.initialize(self.settings, profile=self._profile, stats=self._stats)
        self._settings_panel.set_profile_context(self._db, self._profile)
        self._dashboard_panel.set_profile(self._profile)

        # Show topic picker on startup
        self._refresh_topic_picker()
        self._session_stack.setCurrentIndex(0)

    # ── Slot handlers ─────────────────────────────────────────

    def _handle_state_change(self, state: SessionState):
        labels = {
            SessionState.IDLE: ("Prêt", T["text_muted"]),
            SessionState.LOADING: ("Chargement…", T["warning"]),
            SessionState.READY: ("Prêt", T["success"]),
            SessionState.LISTENING: ("Écoute…", T["accent"]),
            SessionState.PROCESSING: ("Réflexion…", T["info"]),
            SessionState.SPEAKING: ("Parole…", T["accent"]),
            SessionState.ERROR: ("Erreur", T["error"]),
        }
        text, color = labels.get(state, ("Unknown", T["text_muted"]))
        self._status_label.setText(text)
        self._status_orb.set_color(color)
        self._status_orb.set_animated(state in (SessionState.LISTENING, SessionState.PROCESSING, SessionState.SPEAKING))

        # Individual engine orbs
        self._stt_orb.set_animated(state == SessionState.LISTENING)
        self._llm_orb.set_animated(state == SessionState.PROCESSING)
        self._tts_orb.set_animated(state == SessionState.SPEAKING)

        if state == SessionState.LISTENING:
            self._waveform.start()
        else:
            self._waveform.stop()

    def _handle_status_detail(self, msg: str):
        self._status_detail_label.setText(msg)

    def _handle_models_ready(self, status: dict):
        stt_ok = status.get("stt", False)
        tts_ok = status.get("tts", False)
        self._stt_orb.set_color(T["success"] if stt_ok else T["error"])
        self._llm_orb.set_color(T["success"])
        self._tts_orb.set_color(T["success"] if tts_ok else T["warning"])
        provider = self.session.tts_provider
        self._tts_label.setText(provider.capitalize() if provider not in ("none", "") else "TTS")

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
            self._current_ai_bubble.on_replay = lambda t=text: self.session.replay(t)
            self._current_ai_bubble.finalize()
        self._scroll_to_bottom()

    def _handle_error(self, msg: str):
        self._show_toast(f"Erreur : {msg}", kind="error")

    def _toggle_vad(self, checked: bool):
        if checked:
            self.session.start_listening_vad()
            self._btn_vad.setText("Actif")
        else:
            self.session.stop_listening_vad()
            self._btn_vad.setText("Auto")

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
        """Quick new session — shows topic picker without analysis."""
        self._btn_finir.setEnabled(True)
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.session.reset_session()
        self._refresh_topic_picker()
        if hasattr(self, '_session_stack'):
            self._session_stack.setCurrentIndex(0)
        self._show_toast("Nouvelle session", kind="info")

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
            self._btn_settings.setText("Fermer")
        else:
            self._settings_panel.hide()
            self._btn_settings.setText("Paramètres")

    def _on_settings_changed(self, new_settings: dict):
        self.settings = new_settings
        self._db.update_profile_settings(self._profile["id"], new_settings)
        self._profile["settings"] = new_settings
        self.session.update_settings(new_settings)
        self._update_sidebar_info()
        self._update_session_title()
        self._show_toast("Paramètres mis à jour", kind="success")

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
        name = self._profile.get("name", "")
        avatar = self._profile.get("avatar", "🧑")
        self.setWindowTitle(f"El Profesor — {name} · {lang} · {level} · {topic}")
        if hasattr(self, "_btn_profile"):
            self._btn_profile.setText(f"{avatar}  {name}  ▾")

    # ── Profile management ────────────────────────────────────

    def _on_profile_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {T['bg_card']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px;
                padding: 4px 0;
            }}
            QMenu::item {{ padding: 10px 20px; }}
            QMenu::item:selected {{ background-color: {T['bg_hover']}; color: {T['text_primary']}; }}
            QMenu::separator {{ height: 1px; background: {T['border']}; margin: 4px 12px; }}
        """
        )
        edit_action = menu.addAction("Modifier le profil")
        menu.addSeparator()
        switch_action = menu.addAction("Changer de profil")
        new_action = menu.addAction("Nouveau profil")

        action = menu.exec(self._btn_profile.mapToGlobal(self._btn_profile.rect().bottomLeft()))
        if action == edit_action:
            self._edit_profile()
        elif action == switch_action:
            self._switch_profile_screen()
        elif action == new_action:
            self._create_new_profile()

    def _edit_profile(self):
        dlg = ProfileEditDialog(self._db, self._profile, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._update_session_title()
            self._show_toast("Profil mis à jour", kind="success")

    def _switch_profile_screen(self):
        profiles = self._db.list_profiles()
        if len(profiles) <= 1:
            self._show_toast("Aucun autre profil disponible", kind="info")
            return
        self.session.shutdown()
        screen = ProfileScreen(self._db, parent=None)
        if screen.exec() == QDialog.DialogCode.Accepted and screen.selected_profile:
            self._reload_profile(screen.selected_profile)
        else:
            # Restart session with current profile
            self._reload_profile(self._profile)

    def _create_new_profile(self):
        self.session.shutdown()
        wizard = ProfileWizard(self._db, parent=None)
        created_id = []
        wizard.profile_created.connect(lambda pid: created_id.append(pid))
        if wizard.exec() == QDialog.DialogCode.Accepted and created_id:
            new_profile = self._db.get_profile(created_id[0])
            if new_profile:
                self._reload_profile(new_profile)
                return
        # Restart session with current profile if cancelled
        self._reload_profile(self._profile)

    def _reload_profile(self, new_profile: dict):
        from config.settings import save_last_profile_id
        from core.session import SessionManager
        from core.stats_engine import StatsEngine

        self._profile = new_profile
        self.settings = new_profile.get("settings", self.settings)
        save_last_profile_id(new_profile["id"])

        # Clear chat
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # New session + stats + memory manager
        self.session = SessionManager()
        self._stats = StatsEngine(db=self._db, llm=None)
        self._memory_manager = MemoryManager(db=self._db, llm=None)
        self._connect_session_signals()
        self._start_session()
        self._show_toast(f"Profil : {new_profile['name']}", kind="success")

    def _connect_session_signals(self):
        self.session.on_state_change = lambda s: self.sig_state_changed.emit(s)
        self.session.on_user_transcript = lambda t: self.sig_user_transcript.emit(t)
        self.session.on_assistant_token = lambda t: self.sig_assistant_token.emit(t)
        self.session.on_assistant_done = lambda t: self.sig_assistant_done.emit(t)
        self.session.on_models_ready = lambda s: self.sig_models_ready.emit(s)
        self.session.on_error = lambda e: self.sig_error.emit(e)
        self.session.on_status_detail = lambda m: self.sig_status_detail.emit(m)

    def _scroll_to_bottom(self):
        QTimer.singleShot(
            50, lambda: self._chat_scroll.verticalScrollBar().setValue(self._chat_scroll.verticalScrollBar().maximum())
        )

    def _show_toast(self, message: str, kind: str = "info"):
        toast = ToastNotification(message, kind=kind)
        global_pos = self.mapToGlobal(self.rect().topRight())
        toast.show_at(global_pos.x() - 340, global_pos.y() + 16)

    # ── Finir et Analyser ─────────────────────────────────────

    def _on_finir_analyser(self):
        """Closes session, runs quality analysis + memory extraction, shows recap modal."""
        if not self._stats.session_id:
            self._show_toast("Aucune session active à analyser", kind="info")
            return

        self._btn_finir.setEnabled(False)
        self._btn_finir.setText("Analyse…")

        from PyQt6.QtCore import QObject, pyqtSignal as _sig

        class Emitter(QObject):
            done = _sig(object, object, int)

        emitter = Emitter()
        emitter.done.connect(self._on_finir_result)
        self._finir_emitter = emitter  # keep alive

        def _on_done(score, summary, suggestion_count):
            emitter.done.emit(score, summary, suggestion_count)

        self._stats.analyze_and_extract_async(_on_done)

        # Clear chat for new session
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.session.reset_session()

    def _on_finir_result(self, score, summary, suggestion_count):
        self._btn_finir.setEnabled(True)
        self._btn_finir.setText("Analyser")
        self._show_analysis_recap(score, summary, suggestion_count)

    def _show_analysis_recap(self, score, summary, suggestion_count):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
        from PyQt6.QtGui import QFont
        dlg = QDialog(self)
        dlg.setWindowTitle("Résumé de session")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"background-color: {T['bg_card']}; color: {T['text_primary']};")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Résumé de session")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        layout.addWidget(title)

        if score is not None:
            score_pct = round(score * 100)
            score_lbl = QLabel(f"Score qualité : {score_pct} / 100")
            score_lbl.setFont(QFont(T["font_body"], T["font_size_md"]))
            score_lbl.setStyleSheet(f"color: {T['accent']}; background: transparent; font-weight: 600;")
            layout.addWidget(score_lbl)

        if summary:
            summary_edit = QTextEdit()
            summary_edit.setPlainText(summary)
            summary_edit.setReadOnly(True)
            summary_edit.setFixedHeight(80)
            summary_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {T['bg_secondary']};
                    color: {T['text_secondary']};
                    border: 1px solid {T['border']};
                    border-radius: {T['radius_sm']}px;
                    padding: 8px;
                    font-size: {T['font_size_sm']}px;
                }}
            """)
            layout.addWidget(summary_edit)

        if suggestion_count > 0:
            mem_lbl = QLabel(f"{suggestion_count} mémoire(s) suggérée(s) — Consultez l'onglet Mémoires dans les paramètres.")
            mem_lbl.setStyleSheet(f"color: {T['accent']}; background: transparent; font-size: {T['font_size_sm']}px;")
            mem_lbl.setWordWrap(True)
            layout.addWidget(mem_lbl)
            if hasattr(self, '_settings_panel'):
                self._settings_panel.update_suggestion_badge(suggestion_count)

        ok_btn = QPushButton("Fermer")
        ok_btn.setFixedHeight(36)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: white;
                border: none; border-radius: {T['radius_md']}px;
                padding: 0 20px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}'; font-weight: 600;
            }}
        """)
        ok_btn.clicked.connect(dlg.accept)
        from PyQt6.QtCore import Qt
        layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    # ── Topic picker ──────────────────────────────────────────

    def _build_topic_picker(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background-color: {T['bg_primary']};")
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
        from PyQt6.QtGui import QFont
        from PyQt6.QtCore import Qt
        layout = QVBoxLayout(w)
        layout.setContentsMargins(T["spacing_xl"], T["spacing_xl"], T["spacing_xl"], T["spacing_xl"])
        layout.setSpacing(T["spacing_lg"])
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Choisissez un thème pour cette session")
        title.setFont(QFont(T["font_display"], T["font_size_xl"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        layout.addWidget(title)

        sub = QLabel("Ou saisissez un thème libre en bas")
        sub.setFont(QFont(T["font_body"], T["font_size_sm"]))
        sub.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(sub)

        layout.addSpacing(T["spacing_md"])

        # Memory-based suggestions block (populated at runtime by _refresh_topic_picker)
        self._memory_topics_section = QWidget()
        self._memory_topics_section.setStyleSheet("background: transparent;")
        self._memory_topics_layout = QVBoxLayout(self._memory_topics_section)
        self._memory_topics_layout.setContentsMargins(0, 0, 0, 0)
        self._memory_topics_layout.setSpacing(8)
        layout.addWidget(self._memory_topics_section)

        # Default topics
        default_label = QLabel("THÈMES HABITUELS")
        default_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        default_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent; letter-spacing: 1px;")
        layout.addWidget(default_label)

        default_topics = [
            "Conversation libre", "Actualités", "Voyage", "Travail",
            "Culture & cinéma", "Sport", "Gastronomie", "Technologie",
        ]
        topics_grid = QWidget()
        topics_grid.setStyleSheet("background: transparent;")
        grid_layout = QHBoxLayout(topics_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(8)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        btn_style = f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{
                background-color: {T['accent_soft']};
                color: {T['accent']};
                border-color: {T['accent']};
            }}
        """
        for topic in default_topics:
            btn = QPushButton(topic)
            btn.setFixedHeight(36)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _, t=topic: self._start_with_topic(t))
            grid_layout.addWidget(btn)

        grid_layout.addStretch()
        layout.addWidget(topics_grid)

        layout.addStretch()

        # Free input row
        free_row = QHBoxLayout()
        self._topic_free_input = QLineEdit()
        self._topic_free_input.setPlaceholderText("Ou saisir un thème libre…")
        self._topic_free_input.setFixedHeight(44)
        self._topic_free_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 {T['spacing_md']}px;
                font-size: {T['font_size_md']}px;
                font-family: '{T['font_body']}';
            }}
            QLineEdit:focus {{ border-color: {T['border_active']}; }}
        """)
        self._topic_free_input.returnPressed.connect(self._start_with_free_topic)
        free_row.addWidget(self._topic_free_input, 1)

        start_btn = QPushButton("Démarrer →")
        start_btn.setFixedHeight(44)
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: white;
                border: none; border-radius: {T['radius_md']}px;
                padding: 0 20px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}'; font-weight: 600;
            }}
        """)
        start_btn.clicked.connect(self._start_with_free_topic)
        free_row.addWidget(start_btn)
        layout.addLayout(free_row)

        return w

    def _refresh_topic_picker(self):
        """Repopulates memory-based suggestions in topic picker."""
        if not hasattr(self, '_memory_topics_layout'):
            return
        while self._memory_topics_layout.count():
            item = self._memory_topics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._profile:
            self._memory_topics_section.setVisible(False)
            return

        last_sessions = self._db.list_sessions(self._profile["id"], limit=3)
        suggestions = self._memory_manager.get_topic_suggestions(self._profile["id"], last_sessions)

        if suggestions:
            from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout, QPushButton
            from PyQt6.QtGui import QFont
            mem_label = QLabel("ISSUS DE VOS MÉMOIRES")
            mem_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
            mem_label.setStyleSheet(f"color: {T['accent']}; background: transparent; letter-spacing: 1px;")
            self._memory_topics_layout.addWidget(mem_label)

            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            from PyQt6.QtCore import Qt
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(8)
            row_l.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for s in suggestions:
                btn = QPushButton(s)
                btn.setFixedHeight(36)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {T['accent_soft']};
                        color: {T['accent']};
                        border: 1px solid {T['accent']};
                        border-radius: {T['radius_md']}px;
                        padding: 0 16px;
                        font-size: {T['font_size_sm']}px;
                        font-family: '{T['font_body']}';
                    }}
                    QPushButton:hover {{ background-color: {T['accent']}; color: white; }}
                """)
                btn.clicked.connect(lambda _, t=s: self._start_with_topic(t))
                row_l.addWidget(btn)

            row_l.addStretch()
            self._memory_topics_layout.addWidget(row_w)
            self._memory_topics_layout.addSpacing(T["spacing_md"])

        self._memory_topics_section.setVisible(bool(suggestions))

    def _start_with_topic(self, topic: str):
        """Sets the topic in settings and switches to chat screen."""
        self.settings["topic"] = topic
        self._db.update_profile_settings(self._profile["id"], self.settings)
        self.session.update_settings(self.settings)
        self._update_sidebar_info()
        self._session_stack.setCurrentIndex(1)

    def _start_with_free_topic(self):
        topic = self._topic_free_input.text().strip()
        if not topic:
            topic = "Conversation libre"
        self._topic_free_input.clear()
        self._start_with_topic(topic)

    # ── Window events ─────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._settings_visible and self._settings_panel.isVisible():
            self._settings_panel.resize(400, self.height())
            self._settings_panel.move(self.width() - 400, 0)

    def closeEvent(self, event):
        self.session.shutdown()
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

"""
LangCoach — Settings Panel
Panneau de configuration coulissant
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QFrame, QScrollArea,
    QButtonGroup, QRadioButton, QCheckBox,
    QPushButton,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from config.theme import T
from config.settings import (
    TEACHER_STYLES, LEVELS, TARGET_LANGUAGES,
    CONVERSATION_TOPICS, NATIVE_LANGUAGES,
)


class SettingsPanel(QWidget):
    """
    Panneau paramètres en overlay sur la droite.
    Appelle on_settings_changed(dict) à chaque modification.
    """

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.on_settings_changed = None

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-left: 1px solid {T['border']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = self._make_header()
        root.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(T["spacing_lg"], T["spacing_md"], T["spacing_lg"], T["spacing_xl"])
        layout.setSpacing(T["spacing_lg"])

        # Sections
        layout.addWidget(self._section("🌐  Language"))
        layout.addWidget(self._build_language_selector())

        layout.addWidget(self._section("📊  Level"))
        layout.addWidget(self._build_level_selector())

        layout.addWidget(self._section("🎭  Teacher Style"))
        layout.addWidget(self._build_style_selector())

        layout.addWidget(self._section("💬  Topic"))
        layout.addWidget(self._build_topic_selector())

        layout.addWidget(self._section("🗣  Your Native Language"))
        layout.addWidget(self._build_native_lang_selector())

        layout.addWidget(self._section("🎙  Input Mode"))
        layout.addWidget(self._build_input_mode_selector())

        layout.addWidget(self._section("👁  Display"))
        layout.addWidget(self._build_display_options())

        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_secondary']};
                border-bottom: 1px solid {T['border']};
                border-left: 1px solid {T['border']};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(T["spacing_lg"], 0, T["spacing_lg"], 0)

        title = QLabel("Settings")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        layout.addWidget(title, 1)
        return header

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        label.setStyleSheet(f"""
            color: {T['text_muted']};
            background: transparent;
            letter-spacing: 1px;
            padding-top: 4px;
        """)
        return label

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 8px 12px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QComboBox:hover {{
                border-color: {T['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                selection-background-color: {T['accent_soft']};
                selection-color: {T['accent']};
                padding: 4px;
            }}
        """

    def _build_language_selector(self) -> QWidget:
        combo = QComboBox()
        combo.setStyleSheet(self._combo_style())
        for key, lang in TARGET_LANGUAGES.items():
            combo.addItem(lang["label"], key)

        current = self.settings.get("target_language", "english")
        idx = list(TARGET_LANGUAGES.keys()).index(current) if current in TARGET_LANGUAGES else 0
        combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda i: self._update("target_language", combo.itemData(i))
        )
        return combo

    def _build_level_selector(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        combo = QComboBox()
        combo.setStyleSheet(self._combo_style())
        for key, level in LEVELS.items():
            combo.addItem(level["label"], key)

        current = self.settings.get("level", "B1")
        idx = list(LEVELS.keys()).index(current) if current in LEVELS else 2
        combo.setCurrentIndex(idx)

        desc_label = QLabel(LEVELS.get(current, {}).get("desc", ""))
        desc_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        desc_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")

        def on_change(i):
            key = combo.itemData(i)
            desc_label.setText(LEVELS.get(key, {}).get("desc", ""))
            self._update("level", key)

        combo.currentIndexChanged.connect(on_change)
        layout.addWidget(combo)
        layout.addWidget(desc_label)
        return w

    def _build_style_selector(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        current = self.settings.get("teacher_style", "bienveillant")

        for key, style in TEACHER_STYLES.items():
            btn = self._style_radio_btn(key, style, key == current)
            layout.addWidget(btn)

        return w

    def _style_radio_btn(self, key: str, style: dict, selected: bool) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card'] if not selected else T['accent_soft']};
                border: 1px solid {T['accent'] if selected else T['border']};
                border-radius: {T['radius_md']}px;
            }}
            QWidget:hover {{
                border-color: {T['accent']};
                background-color: {T['accent_soft']};
            }}
        """)
        w.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        emoji = QLabel(style["emoji"])
        emoji.setFont(QFont(T["font_body"], T["font_size_lg"]))
        emoji.setStyleSheet("background: transparent; border: none;")
        emoji.setFixedWidth(28)
        layout.addWidget(emoji)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name = QLabel(style["label"])
        name.setFont(QFont(T["font_body"], T["font_size_sm"]))
        name.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none; font-weight: 600;")
        text_col.addWidget(name)

        desc = QLabel(style["description"])
        desc.setFont(QFont(T["font_body"], T["font_size_xs"]))
        desc.setStyleSheet(f"color: {T['text_secondary']}; background: transparent; border: none;")
        text_col.addWidget(desc)

        layout.addLayout(text_col, 1)

        def click(event):
            self._update("teacher_style", key)
            # Refresh all style buttons (rebuild parent)
            parent = w.parent()
            if parent:
                parent_layout = parent.layout()
                if parent_layout:
                    for i in range(parent_layout.count()):
                        item = parent_layout.itemAt(i)
                        if item and item.widget():
                            btn_widget = item.widget()
                            is_sel = (i == list(TEACHER_STYLES.keys()).index(key))
                            btn_widget.setStyleSheet(f"""
                                QWidget {{
                                    background-color: {T['accent_soft'] if is_sel else T['bg_card']};
                                    border: 1px solid {T['accent'] if is_sel else T['border']};
                                    border-radius: {T['radius_md']}px;
                                }}
                            """)

        w.mousePressEvent = click
        return w

    def _build_topic_selector(self) -> QWidget:
        combo = QComboBox()
        combo.setStyleSheet(self._combo_style())
        for topic in CONVERSATION_TOPICS:
            combo.addItem(topic)

        current = self.settings.get("topic", "Conversation libre")
        if current in CONVERSATION_TOPICS:
            combo.setCurrentIndex(CONVERSATION_TOPICS.index(current))

        combo.currentTextChanged.connect(lambda t: self._update("topic", t))
        return combo

    def _build_native_lang_selector(self) -> QWidget:
        combo = QComboBox()
        combo.setStyleSheet(self._combo_style())
        for key, name in NATIVE_LANGUAGES.items():
            combo.addItem(name, key)

        current = self.settings.get("native_language", "fr")
        keys = list(NATIVE_LANGUAGES.keys())
        if current in keys:
            combo.setCurrentIndex(keys.index(current))

        combo.currentIndexChanged.connect(
            lambda i: self._update("native_language", combo.itemData(i))
        )
        return combo

    def _build_input_mode_selector(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        current = self.settings.get("input_mode", "vad")

        modes = [
            ("vad", "Auto detect"),
            ("push_to_talk", "Push to talk"),
            ("both", "Both"),
        ]
        btn_style = lambda selected: f"""
            QPushButton {{
                background-color: {T['accent_soft'] if selected else T['bg_card']};
                color: {T['accent'] if selected else T['text_secondary']};
                border: 1px solid {T['accent'] if selected else T['border']};
                border-radius: {T['radius_md']}px;
                padding: 8px 12px;
                font-size: {T['font_size_xs']}px;
                font-family: '{T['font_body']}';
            }}
        """

        buttons = []
        for key, label in modes:
            btn = QPushButton(label)
            btn.setStyleSheet(btn_style(key == current))
            btn.setCheckable(True)
            btn.setChecked(key == current)
            layout.addWidget(btn)
            buttons.append((key, btn))

        def on_click(clicked_key, clicked_btn):
            self._update("input_mode", clicked_key)
            for k, b in buttons:
                b.setStyleSheet(btn_style(k == clicked_key))

        for key, btn in buttons:
            btn.clicked.connect(lambda checked, k=key, b=btn: on_click(k, b))

        return w

    def _build_display_options(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        checkbox_style = f"""
            QCheckBox {{
                color: {T['text_primary']};
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {T['border']};
                border-radius: 4px;
                background: {T['bg_card']};
            }}
            QCheckBox::indicator:checked {{
                background: {T['accent']};
                border-color: {T['accent']};
            }}
        """

        show_transcript = QCheckBox("Show transcript")
        show_transcript.setStyleSheet(checkbox_style)
        show_transcript.setChecked(self.settings.get("show_transcript", True))
        show_transcript.toggled.connect(lambda v: self._update("show_transcript", v))
        layout.addWidget(show_transcript)

        show_corrections = QCheckBox("Show corrections")
        show_corrections.setStyleSheet(checkbox_style)
        show_corrections.setChecked(self.settings.get("show_corrections", True))
        show_corrections.toggled.connect(lambda v: self._update("show_corrections", v))
        layout.addWidget(show_corrections)

        return w

    def _update(self, key: str, value):
        self.settings[key] = value
        if self.on_settings_changed:
            self.on_settings_changed(self.settings.copy())

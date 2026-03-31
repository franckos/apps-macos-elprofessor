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
    CONVERSATION_TOPICS, NATIVE_LANGUAGES, COACHES,
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
        self.on_close = None
        self.on_update_requested = None  # callback() → called when user confirms update
        self._check_in_progress = False

        self.setObjectName("SettingsPanel")
        # WA_StyledBackground + setAutoFillBackground force Qt to paint the solid background
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet(f"""
            QWidget#SettingsPanel {{
                background-color: {T['bg_secondary']};
                border-left: 1px solid {T['border']};
            }}
            QWidget#SettingsPanel QWidget {{
                background-color: {T['bg_secondary']};
            }}
            QWidget#SettingsPanel QScrollArea {{
                background-color: {T['bg_secondary']};
                border: none;
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
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {T['bg_secondary']}; }}")

        content = QWidget()
        content.setStyleSheet(f"background-color: {T['bg_secondary']};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(T["spacing_lg"], T["spacing_md"], T["spacing_lg"], T["spacing_xl"])
        layout.setSpacing(T["spacing_lg"])

        # Sections
        layout.addWidget(self._section("🌐  Language"))
        layout.addWidget(self._build_language_selector())

        layout.addWidget(self._section("🎓  Coach"))
        self._coach_container = QWidget()
        self._coach_container.setStyleSheet("background: transparent;")
        self._coach_layout = QVBoxLayout(self._coach_container)
        self._coach_layout.setContentsMargins(0, 0, 0, 0)
        self._coach_layout.setSpacing(6)
        self._rebuild_coach_selector()
        layout.addWidget(self._coach_container)

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

        layout.addWidget(self._section("⬆  App"))
        layout.addWidget(self._build_update_section())

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(64)
        header.setObjectName("SettingsPanelHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setStyleSheet(f"""
            QWidget#SettingsPanelHeader {{
                background-color: {T['bg_secondary']};
                border-bottom: 1px solid {T['border']};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(T["spacing_lg"], 0, T["spacing_lg"], 0)

        title = QLabel("Settings")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        layout.addWidget(title, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T['text_secondary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                font-size: {T['font_size_md']}px;
            }}
            QPushButton:hover {{
                background-color: {T['bg_hover']};
                color: {T['text_primary']};
                border-color: {T['accent']};
            }}
        """)
        close_btn.clicked.connect(lambda: self.on_close() if self.on_close else None)
        layout.addWidget(close_btn)

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
        def on_lang_change(i):
            self._update("target_language", combo.itemData(i))
            self._rebuild_coach_selector()

        combo.currentIndexChanged.connect(on_lang_change)
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

    def _rebuild_coach_selector(self):
        """Reconstruit les boutons coach selon la langue courante"""
        while self._coach_layout.count():
            item = self._coach_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lang_key = self.settings.get("target_language", "english")
        current_coach = self.settings.get("coach", "angela")
        lang_coaches = COACHES.get(lang_key, COACHES["english"])

        # Si le coach actuel n'existe pas dans cette langue, reset au premier
        if current_coach not in lang_coaches:
            current_coach = next(iter(lang_coaches.keys()))
            self.settings["coach"] = current_coach

        for key, coach in lang_coaches.items():
            btn = self._coach_btn(key, coach, key == current_coach, lang_coaches)
            self._coach_layout.addWidget(btn)

    def _coach_btn(self, key: str, coach: dict, selected: bool, lang_coaches: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{
                background-color: {T['accent_soft'] if selected else T['bg_card']};
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

        flag = QLabel(coach.get("flag", ""))
        flag.setFont(QFont(T["font_body"], T["font_size_lg"]))
        flag.setStyleSheet("background: transparent; border: none;")
        flag.setFixedWidth(28)
        layout.addWidget(flag)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_lbl = QLabel(coach["name"])
        name_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        name_lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none; font-weight: 600;")
        text_col.addWidget(name_lbl)

        gender_map = {"male": "Homme", "female": "Femme"}
        accent = "Anglais US" if coach["lang_code"] == "a" else \
                 "Anglais UK" if coach["lang_code"] == "b" else \
                 "Espagnol"
        sub = QLabel(f"{gender_map.get(coach['gender'], '')} · {accent}")
        sub.setFont(QFont(T["font_body"], T["font_size_xs"]))
        sub.setStyleSheet(f"color: {T['text_secondary']}; background: transparent; border: none;")
        text_col.addWidget(sub)

        layout.addLayout(text_col, 1)

        def click(event):
            self._update("coach", key)
            for i in range(self._coach_layout.count()):
                item = self._coach_layout.itemAt(i)
                if item and item.widget():
                    is_sel = (i == list(lang_coaches.keys()).index(key))
                    item.widget().setStyleSheet(f"""
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

    def _build_update_section(self) -> QWidget:
        from core.updater import fetch_latest_release, run_update, get_local_version

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        local_ver = get_local_version()
        version_label = QLabel(f"Version installée : {local_ver}")
        version_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        version_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(version_label)

        status_label = QLabel("")
        status_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        status_label.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)

        btn = QPushButton("Vérifier les mises à jour")
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{
                border-color: {T['accent']};
                background-color: {T['accent_soft']};
                color: {T['accent']};
            }}
            QPushButton:disabled {{
                color: {T['text_muted']};
            }}
        """)
        layout.addWidget(btn)

        update_btn = QPushButton("⬆  Mettre à jour")
        update_btn.setFixedHeight(36)
        update_btn.setVisible(False)
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']};
                color: #ffffff;
                border: none;
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {T['accent']};
                opacity: 0.9;
            }}
        """)
        layout.addWidget(update_btn)

        def on_check():
            if self._check_in_progress:
                return
            self._check_in_progress = True
            btn.setEnabled(False)
            btn.setText("Vérification…")
            status_label.setText("")
            update_btn.setVisible(False)

            import threading
            from PyQt6.QtCore import QObject, pyqtSignal

            class _Checker(QObject):
                finished = pyqtSignal(object)

            def _update_ui(info):
                self._check_in_progress = False
                btn.setEnabled(True)
                btn.setText("Vérifier les mises à jour")
                if info is None:
                    status_label.setText("Impossible de vérifier (pas de connexion ?)")
                    status_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
                elif info.update_available:
                    status_label.setText(f"Version {info.latest_version} disponible !")
                    status_label.setStyleSheet(f"color: {T['accent']}; background: transparent;")
                    update_btn.setVisible(True)
                    update_btn.setProperty("release_url", info.release_url)
                else:
                    status_label.setText(f"Vous avez la dernière version ({info.local_version}).")
                    status_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")

            checker = _Checker()
            checker.finished.connect(_update_ui)

            def _check():
                try:
                    info = fetch_latest_release()
                except Exception:
                    info = None
                checker.finished.emit(info)

            self._checker = checker  # keep reference alive
            threading.Thread(target=_check, daemon=True).start()

        def on_update():
            run_update()
            if self.on_update_requested:
                self.on_update_requested()

        btn.clicked.connect(on_check)
        update_btn.clicked.connect(on_update)
        return w

    def _update(self, key: str, value):
        self.settings[key] = value
        if self.on_settings_changed:
            self.on_settings_changed(self.settings.copy())

"""
LangCoach — Profile Screen
Splash screen for profile selection + 3-step creation wizard.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from config.theme import T
from config.settings import DEFAULT_SETTINGS, COACHES, LEVELS, TARGET_LANGUAGES, TEACHER_STYLES
from core.database import Database

_AVATARS = ["🧑", "👩", "🧒", "👨‍💼", "👩‍🎓", "👴", "👵", "🧑‍🎤", "🧑‍💻", "🦸"]


class ProfileCard(QWidget):
    """Clickable card for an existing profile."""

    def __init__(self, profile: dict, on_select, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._on_select = on_select
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(140, 160)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 2px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
            QWidget:hover {{ border-color: {T['accent']}; background-color: {T['bg_hover']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar = QLabel(profile.get("avatar", "🧑"))
        avatar.setFont(QFont(T["font_body"], 28))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(avatar)

        name = QLabel(profile["name"])
        name.setFont(QFont(T["font_display"], T["font_size_md"]))
        name.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        s = profile.get("settings", {})
        sub = QLabel(f"{s.get('target_language','english').capitalize()} · {s.get('level','B1')}")
        sub.setFont(QFont(T["font_body"], T["font_size_xs"]))
        sub.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

    def mousePressEvent(self, event):
        self._on_select(self._profile)
        super().mousePressEvent(event)


class ProfileScreen(QDialog):
    """
    Handles profile selection at launch.
    - No profiles → wizard immediately.
    - 1 profile → auto-select (accepts via QTimer).
    - 2+ profiles → splash screen with cards.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._selected_profile: Optional[dict] = None
        self.setModal(True)
        self.setWindowTitle("Echo")
        self.resize(680, 420)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        profiles = db.list_profiles()

        if not profiles:
            self._embed_wizard()
        elif len(profiles) == 1:
            self._selected_profile = profiles[0]
            db.touch_profile(profiles[0]["id"])
            QTimer.singleShot(0, self.accept)
            QVBoxLayout(self)  # empty layout to avoid Qt warnings
        else:
            self._build_splash(profiles)

    def _embed_wizard(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        wizard = ProfileWizard(self._db, parent=self)
        wizard.profile_created.connect(self._on_wizard_done)
        layout.addWidget(wizard)

    def _build_splash(self, profiles: list):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(28)

        title = QLabel("Qui apprend aujourd'hui ?")
        title.setFont(QFont(T["font_display"], T["font_size_xl"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for profile in profiles:
            card = ProfileCard(profile, on_select=self._on_profile_selected)
            cards_row.addWidget(card)

        new_btn = QPushButton("＋\nNouveau profil")
        new_btn.setFixedSize(140, 160)
        new_btn.setFont(QFont(T["font_body"], T["font_size_sm"]))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T['bg_card']}; color: {T['text_muted']};
                border: 2px dashed {T['border']}; border-radius: {T['radius_md']}px;
            }}
            QPushButton:hover {{ border-color: {T['accent']}; color: {T['text_primary']}; }}
        """)
        new_btn.clicked.connect(self._show_wizard_overlay)
        cards_row.addWidget(new_btn)

        layout.addLayout(cards_row)

    def _on_profile_selected(self, profile: dict):
        self._db.touch_profile(profile["id"])
        self._selected_profile = profile
        self.accept()

    def _show_wizard_overlay(self):
        wizard = ProfileWizard(self._db, parent=self)
        wizard.profile_created.connect(self._on_wizard_done)
        wizard.exec()

    def _on_wizard_done(self, profile_id: str):
        profile = self._db.get_profile(profile_id)
        if profile:
            self._selected_profile = profile
            self.accept()

    @property
    def selected_profile(self) -> Optional[dict]:
        return self._selected_profile


class ProfileWizard(QDialog):
    """3-step profile creation: Step 1 Name+Avatar, Step 2 Language+Level, Step 3 Coach+Style."""

    profile_created = pyqtSignal(str)  # emits profile_id on finish

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._name = ""
        self._avatar = _AVATARS[0]
        self._language = "english"
        self._level = "B1"
        self._coach = "angela"
        self._style = "bienveillant"

        self.setModal(True)
        self.setWindowTitle("Créer un profil")
        self.resize(440, 500)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        self._stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())

    # ── Step 1: Name + Avatar ──────────────────────────────────

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 1)

        title = QLabel("Comment t'appelles-tu ?")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("L'IA t'appellera par ton prénom")
        sub.setFont(QFont(T["font_body"], T["font_size_sm"]))
        sub.setStyleSheet(f"color: {T['text_muted']};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Ton prénom…")
        self._name_input.setFixedHeight(48)
        self._name_input.setFont(QFont(T["font_body"], T["font_size_lg"]))
        self._name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {T['bg_card']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px; padding: 8px 16px;
            }}
            QLineEdit:focus {{ border-color: {T['accent']}; }}
        """)
        layout.addWidget(self._name_input)

        avatar_lbl = QLabel("Avatar")
        avatar_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(avatar_lbl)

        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(8)
        self._avatar_btns: list[QPushButton] = []
        for emoji in _AVATARS[:6]:
            btn = QPushButton(emoji)
            btn.setFixedSize(48, 48)
            btn.setFont(QFont(T["font_body"], 18))
            btn.setCheckable(True)
            btn.setChecked(emoji == self._avatar)
            btn.clicked.connect(lambda _, e=emoji: self._select_avatar(e))
            self._avatar_btns.append(btn)
            avatar_row.addWidget(btn)
        self._update_avatar_styles()
        layout.addLayout(avatar_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(back=False, next_fn=self._go_step2))
        return page

    def _select_avatar(self, emoji: str):
        self._avatar = emoji
        self._update_avatar_styles()

    def _update_avatar_styles(self):
        for btn in self._avatar_btns:
            btn.setStyleSheet(self._pill(btn.text() == self._avatar))

    def _go_step2(self):
        self._name = self._name_input.text().strip()
        if not self._name:
            self._name_input.setFocus()
            return
        self._stack.setCurrentIndex(1)

    # ── Step 2: Language + Level ───────────────────────────────

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 2)

        title = QLabel("Quelle langue apprends-tu ?")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        lang_lbl = QLabel("Langue cible")
        lang_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(lang_lbl)

        lang_row = QHBoxLayout()
        self._lang_btns: dict[str, QPushButton] = {}
        for key, info in TARGET_LANGUAGES.items():
            btn = QPushButton(info["label"])
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_language(k))
            self._lang_btns[key] = btn
            lang_row.addWidget(btn)
        self._update_lang_styles()
        layout.addLayout(lang_row)

        level_lbl = QLabel("Ton niveau actuel")
        level_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(level_lbl)

        level_row = QHBoxLayout()
        self._level_btns: dict[str, QPushButton] = {}
        for key in LEVELS:
            btn = QPushButton(key)
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_level(k))
            self._level_btns[key] = btn
            level_row.addWidget(btn)
        self._update_level_styles()
        layout.addLayout(level_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(
            back=True, back_fn=lambda: self._stack.setCurrentIndex(0), next_fn=self._go_step3
        ))
        return page

    def _select_language(self, key: str):
        self._language = key
        self._update_lang_styles()

    def _update_lang_styles(self):
        for k, btn in self._lang_btns.items():
            btn.setStyleSheet(self._pill(k == self._language))

    def _select_level(self, key: str):
        self._level = key
        self._update_level_styles()

    def _update_level_styles(self):
        for k, btn in self._level_btns.items():
            btn.setStyleSheet(self._pill(k == self._level))

    def _go_step3(self):
        self._rebuild_coach_buttons()
        self._stack.setCurrentIndex(2)

    def _rebuild_coach_buttons(self):
        """Rebuild coach buttons for the currently selected language."""
        coach_layout = self._coach_container.layout()
        while coach_layout.count():
            item = coach_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._coach_btns = {}
        coaches = COACHES.get(self._language, COACHES["english"])
        if self._coach not in coaches:
            self._coach = next(iter(coaches))
        for key, info in coaches.items():
            btn = QPushButton(f"{info['flag']} {info['name']}")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_coach(k))
            self._coach_btns[key] = btn
            coach_layout.addWidget(btn)
        self._update_coach_styles()

    # ── Step 3: Coach + Style ──────────────────────────────────

    def _build_step3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        self._add_step_indicator(layout, 3)

        title = QLabel("Choisis ton coach")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        coach_lbl = QLabel("Coach")
        coach_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(coach_lbl)

        self._coach_container = QWidget()
        self._coach_container.setStyleSheet("background: transparent;")
        coach_row = QHBoxLayout(self._coach_container)
        coach_row.setContentsMargins(0, 0, 0, 0)
        self._coach_btns: dict[str, QPushButton] = {}
        for key, info in COACHES.get(self._language, COACHES["english"]).items():
            btn = QPushButton(f"{info['flag']} {info['name']}")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_coach(k))
            self._coach_btns[key] = btn
            coach_row.addWidget(btn)
        self._update_coach_styles()
        layout.addWidget(self._coach_container)

        style_lbl = QLabel("Style d'enseignement")
        style_lbl.setStyleSheet(f"color: {T['text_muted']};")
        layout.addWidget(style_lbl)

        style_row = QHBoxLayout()
        self._style_btns: dict[str, QPushButton] = {}
        for key, info in TEACHER_STYLES.items():
            btn = QPushButton(f"{info['emoji']} {info['label']}")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, k=key: self._select_style(k))
            self._style_btns[key] = btn
            style_row.addWidget(btn)
        self._update_style_styles()
        layout.addLayout(style_row)

        layout.addStretch()
        layout.addWidget(self._nav_row(
            back=True,
            back_fn=lambda: self._stack.setCurrentIndex(1),
            next_fn=self._finish,
            next_label="Créer mon profil →",
        ))
        return page

    def _select_coach(self, key: str):
        self._coach = key
        self._update_coach_styles()

    def _update_coach_styles(self):
        for k, btn in self._coach_btns.items():
            btn.setStyleSheet(self._pill(k == self._coach))

    def _select_style(self, key: str):
        self._style = key
        self._update_style_styles()

    def _update_style_styles(self):
        for k, btn in self._style_btns.items():
            btn.setStyleSheet(self._pill(k == self._style))

    def _finish(self):
        settings = {
            **DEFAULT_SETTINGS,
            "target_language": self._language,
            "level": self._level,
            "coach": self._coach,
            "teacher_style": self._style,
        }
        profile = self._db.create_profile(self._name, self._avatar, settings)
        self.profile_created.emit(profile["id"])
        self.accept()

    # ── Helpers ───────────────────────────────────────────────

    def _add_step_indicator(self, layout: QVBoxLayout, current: int):
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(6)
        for i in range(1, 4):
            dot = QLabel(str(i))
            dot.setFixedSize(28, 28)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFont(QFont(T["font_body"], T["font_size_sm"]))
            if i == current:
                dot.setStyleSheet(f"background:{T['accent']}; color:white; border-radius:14px;")
            elif i < current:
                dot.setStyleSheet(f"background:{T['success']}; color:white; border-radius:14px;")
            else:
                dot.setStyleSheet(f"background:{T['bg_card']}; color:{T['text_muted']}; border-radius:14px; border:1px solid {T['border']};")
            row.addWidget(dot)
            if i < 3:
                line = QFrame()
                line.setFixedSize(36, 2)
                line.setStyleSheet(f"background: {T['accent'] if i < current else T['border']};")
                row.addWidget(line)
        layout.addLayout(row)

    def _nav_row(self, back: bool, next_fn, back_fn=None, next_label: str = "Suivant →") -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        if back and back_fn:
            b = QPushButton("← Retour")
            b.setFixedHeight(44)
            b.setStyleSheet(f"QPushButton {{ background:{T['bg_card']}; color:{T['text_secondary']}; border:1px solid {T['border']}; border-radius:{T['radius_md']}px; }} QPushButton:hover {{ background:{T['bg_hover']}; }}")
            b.clicked.connect(back_fn)
            row.addWidget(b)
        n = QPushButton(next_label)
        n.setFixedHeight(44)
        n.setStyleSheet(f"QPushButton {{ background:{T['accent']}; color:white; border:none; border-radius:{T['radius_md']}px; font-weight:bold; }} QPushButton:hover {{ background:#5555ff; }}")
        n.clicked.connect(next_fn)
        row.addWidget(n, 2)
        return w

    def _pill(self, selected: bool) -> str:
        if selected:
            return f"QPushButton {{ background:#2a2a4e; color:{T['accent']}; border:2px solid {T['accent']}; border-radius:{T['radius_sm']}px; }}"
        return f"QPushButton {{ background:{T['bg_card']}; color:{T['text_secondary']}; border:1px solid {T['border']}; border-radius:{T['radius_sm']}px; }} QPushButton:hover {{ border-color:{T['accent']}; }}"

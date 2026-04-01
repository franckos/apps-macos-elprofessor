"""
LangCoach — Memory Panel
Dialog de gestion des mémoires du profil
"""
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QLineEdit, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config.theme import T
from core.memory_manager import SYSTEM_TAGS


class TagChip(QPushButton):
    """Clickable tag chip."""
    def __init__(self, tag: str, selected: bool = False, parent=None):
        super().__init__(tag, parent)
        self.tag = tag
        self._selected = selected
        self.setCheckable(True)
        self.setChecked(selected)
        self._refresh_style()
        self.toggled.connect(lambda _: self._refresh_style())

    def _refresh_style(self):
        sel = self.isChecked()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent_soft'] if sel else T['bg_card']};
                color: {T['accent'] if sel else T['text_secondary']};
                border: 1px solid {T['accent'] if sel else T['border']};
                border-radius: 10px;
                padding: 3px 10px;
                font-size: {T['font_size_xs']}px;
                font-family: '{T['font_body']}';
            }}
        """)


class MemoryRow(QWidget):
    """Single memory row: content + tags + delete button."""
    deleted = pyqtSignal(str)  # emits memory_id

    def __init__(self, memory: dict, parent=None):
        super().__init__(parent)
        self._memory_id = memory["id"]
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        tags = memory["tags"]
        source = memory.get("source", "manual")
        source_icon = "🤖" if source == "ai" else "✍️"

        src_lbl = QLabel(source_icon)
        src_lbl.setStyleSheet("background: transparent; border: none;")
        src_lbl.setFixedWidth(18)
        layout.addWidget(src_lbl)

        col = QVBoxLayout()
        col.setSpacing(3)

        content_lbl = QLabel(memory["content"])
        content_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        content_lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        content_lbl.setWordWrap(True)
        col.addWidget(content_lbl)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        tag_row.setContentsMargins(0, 0, 0, 0)
        for tag in tags:
            badge_text = tag
            if tag == "important":
                badge_text = "📌 important"
            elif tag == "confidentiel":
                badge_text = "🔒 confidentiel"
            badge = QLabel(badge_text)
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {T['accent_soft']};
                    color: {T['accent']};
                    border-radius: 8px;
                    padding: 1px 7px;
                    font-size: {T['font_size_xs']}px;
                    font-family: '{T['font_body']}';
                }}
            """)
            tag_row.addWidget(badge)
        tag_row.addStretch()
        col.addLayout(tag_row)

        layout.addLayout(col, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{ color: {T['error']}; }}
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self._memory_id))
        layout.addWidget(del_btn)


class AddMemoryForm(QWidget):
    """Inline form for adding a new memory."""
    submitted = pyqtSignal(str, list)  # content, tags

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['accent']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ex : Prépare un entretien chez Google en juin… (max 120 chars)")
        self._input.setMaxLength(120)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T['bg_secondary']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_sm']}px;
                padding: 6px 10px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QLineEdit:focus {{ border-color: {T['accent']}; }}
        """)
        layout.addWidget(self._input)

        self._counter = QLabel("0 / 120")
        self._counter.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none; font-size: {T['font_size_xs']}px;")
        self._counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._counter)
        self._input.textChanged.connect(lambda t: self._counter.setText(f"{len(t)} / 120"))

        tag_label = QLabel("Tags :")
        tag_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none; font-size: {T['font_size_xs']}px;")
        layout.addWidget(tag_label)

        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFixedHeight(80)
        chips_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        chips_widget = QWidget()
        chips_widget.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_widget)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._chips = {}
        for tag in SYSTEM_TAGS:
            chip = TagChip(tag)
            self._chips[tag] = chip
            chips_layout.addWidget(chip)
        chips_layout.addStretch()
        chips_scroll.setWidget(chips_widget)
        layout.addWidget(chips_scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
                padding: 0 12px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ color: {T['text_primary']}; }}
        """)
        cancel_btn.clicked.connect(lambda: self.hide())
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Enregistrer")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: white;
                border: none; border-radius: {T['radius_sm']}px;
                padding: 0 12px; font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}'; font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        content = self._input.text().strip()
        if not content:
            return
        tags = [tag for tag, chip in self._chips.items() if chip.isChecked()]
        self.submitted.emit(content, tags)
        self._input.clear()
        for chip in self._chips.values():
            chip.setChecked(False)
        self.hide()


class SuggestionRow(QWidget):
    """Suggestion row with Accept / Reject actions."""
    accepted = pyqtSignal(str)
    rejected = pyqtSignal(str)

    def __init__(self, suggestion: dict, parent=None):
        super().__init__(parent)
        self._suggestion_id = suggestion["id"]
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T['bg_card']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(3)

        content_lbl = QLabel(suggestion["content"])
        content_lbl.setFont(QFont(T["font_body"], T["font_size_sm"]))
        content_lbl.setStyleSheet(f"color: {T['text_primary']}; background: transparent; border: none;")
        content_lbl.setWordWrap(True)
        col.addWidget(content_lbl)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        for tag in suggestion["tags"]:
            badge = QLabel(tag)
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {T['accent_soft']}; color: {T['accent']};
                    border-radius: 8px; padding: 1px 7px;
                    font-size: {T['font_size_xs']}px; font-family: '{T['font_body']}';
                }}
            """)
            tag_row.addWidget(badge)
        tag_row.addStretch()
        col.addLayout(tag_row)
        layout.addLayout(col, 1)

        accept_btn = QPushButton("✓ Accepter")
        accept_btn.setFixedHeight(28)
        accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: white;
                border: none; border-radius: {T['radius_sm']}px;
                padding: 0 10px; font-size: {T['font_size_xs']}px; font-family: '{T['font_body']}';
            }}
        """)
        accept_btn.clicked.connect(lambda: self.accepted.emit(self._suggestion_id))
        layout.addWidget(accept_btn)

        reject_btn = QPushButton("✕")
        reject_btn.setFixedSize(28, 28)
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {T['error']}; border-color: {T['error']}; }}
        """)
        reject_btn.clicked.connect(lambda: self.rejected.emit(self._suggestion_id))
        layout.addWidget(reject_btn)


class MemoryDialog(QDialog):
    """Full memory management dialog."""

    def __init__(self, db, profile: dict, parent=None):
        super().__init__(parent)
        self._db = db
        self._profile = profile
        self.setWindowTitle("Mémoires")
        self.setMinimumSize(540, 620)
        self.setStyleSheet(f"background-color: {T['bg_primary']}; color: {T['text_primary']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background-color: {T['bg_secondary']}; border-bottom: 1px solid {T['border']};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 16, 0)
        title = QLabel("Mémoires")
        title.setFont(QFont(T["font_display"], T["font_size_lg"]))
        title.setStyleSheet(f"color: {T['text_primary']}; background: transparent;")
        h_layout.addWidget(title, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T['text_muted']};
                border: 1px solid {T['border']}; border-radius: {T['radius_sm']}px;
            }}
            QPushButton:hover {{ color: {T['text_primary']}; border-color: {T['accent']}; }}
        """)
        close_btn.clicked.connect(self.accept)
        h_layout.addWidget(close_btn)
        root.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {T['bg_primary']}; }}")
        content = QWidget()
        content.setStyleSheet(f"background-color: {T['bg_primary']};")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(20, 16, 20, 20)
        self._content_layout.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._refresh()

    def _refresh(self):
        """Clears and rebuilds the content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        suggestions = self._db.list_memory_suggestions(self._profile["id"])
        memories = self._db.list_memories(self._profile["id"])

        # Suggestions banner
        if suggestions:
            banner = QWidget()
            banner.setStyleSheet(f"""
                QWidget {{
                    background-color: {T['accent_soft']};
                    border: 1px solid {T['accent']};
                    border-radius: {T['radius_md']}px;
                }}
            """)
            b_layout = QVBoxLayout(banner)
            b_layout.setContentsMargins(12, 10, 12, 10)
            b_layout.setSpacing(8)

            b_title = QLabel(f"{len(suggestions)} mémoire(s) suggérée(s) — à valider")
            b_title.setFont(QFont(T["font_body"], T["font_size_sm"]))
            b_title.setStyleSheet(f"color: {T['accent']}; background: transparent; font-weight: 600;")
            b_layout.addWidget(b_title)

            for s in suggestions:
                row = SuggestionRow(s)
                row.accepted.connect(self._on_accept)
                row.rejected.connect(self._on_reject)
                b_layout.addWidget(row)

            self._content_layout.addWidget(banner)

        # Add memory button + form
        add_btn = QPushButton("＋  Ajouter une mémoire")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: {T['radius_md']}px;
                padding: 0 16px; font-size: {T['font_size_sm']}px; font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{ border-color: {T['accent']}; color: {T['accent']}; background: {T['accent_soft']}; }}
        """)
        self._content_layout.addWidget(add_btn)

        self._add_form = AddMemoryForm()
        self._add_form.hide()
        self._add_form.submitted.connect(self._on_add_memory)
        self._content_layout.addWidget(self._add_form)
        add_btn.clicked.connect(lambda: self._add_form.setVisible(not self._add_form.isVisible()))

        # Memories list
        if not memories:
            empty = QLabel("Aucune mémoire enregistrée.")
            empty.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(empty)
        else:
            section_lbl = QLabel(f"Mémoires ({len(memories)})")
            section_lbl.setFont(QFont(T["font_body"], T["font_size_xs"]))
            section_lbl.setStyleSheet(f"color: {T['text_muted']}; background: transparent; letter-spacing: 1px;")
            self._content_layout.addWidget(section_lbl)

            for m in memories:
                row = MemoryRow(m)
                row.deleted.connect(self._on_delete)
                self._content_layout.addWidget(row)

        self._content_layout.addStretch()

    def _on_add_memory(self, content: str, tags: list):
        self._db.create_memory(self._profile["id"], content, tags, source="manual")
        self._refresh()

    def _on_delete(self, memory_id: str):
        self._db.delete_memory(memory_id)
        self._refresh()

    def _on_accept(self, suggestion_id: str):
        self._db.accept_memory_suggestion(suggestion_id)
        self._refresh()

    def _on_reject(self, suggestion_id: str):
        self._db.delete_memory_suggestion(suggestion_id)
        self._refresh()

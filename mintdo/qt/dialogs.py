"""Qt dialogs: list editor, delete confirmation, shortcuts and about."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from mintdo import APP_NAME, __version__
from mintdo.qt.sidebar import LIST_COLORS

SHORTCUTS = (
    ("Ctrl+N", "New task", "Jump to the quick-add box"),
    ("Ctrl+Shift+N", "New list", "Create a new list"),
    ("Ctrl+F", "Search", "Find tasks by title, note or #tag"),
    ("Ctrl+Z", "Undo", "Undo the last completion or deletion"),
    ("Ctrl+D", "Dark mode", "Switch between light and dark theme"),
    ("Ctrl+B", "Sidebar", "Show or hide the sidebar"),
    ("Ctrl+I", "Stats", "Open the weekly progress dialog"),
    ("Delete", "Delete task", "Remove the selected task (undoable)"),
    ("F1", "Shortcuts", "Show this window"),
)


class ListDialog(QDialog):
    """Create or rename a list and pick its colour."""

    def __init__(self, parent=None, title="New list", initial_name="",
                 initial_color=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)
        root = QVBoxLayout(self)

        self.name_entry = QLineEdit(initial_name)
        self.name_entry.setPlaceholderText("List name, e.g. “Groceries”")
        root.addWidget(self.name_entry)

        root.addWidget(QLabel("Colour"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.color_buttons = []
        chosen = initial_color or LIST_COLORS[0]
        for index, color in enumerate(LIST_COLORS):
            btn = QRadioButton()
            btn.setFixedSize(34, 26)
            btn._mintdo_color = color
            btn.setStyleSheet(
                f"QRadioButton::indicator {{ width: 26px; height: 20px; "
                f"border-radius: 4px; background: {color}; }}"
                f"QRadioButton::indicator:checked {{ border: 2px solid "
                f"{color}; }}")
            btn.setChecked(color == chosen)
            self.color_group.addButton(btn)
            self.color_buttons.append(btn)
            grid.addWidget(btn, index // 8, index % 8)
        root.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.name_entry.setFocus()

    def accept(self):
        if not self.name_entry.text().strip():
            self.name_entry.setFocus()
            return
        super().accept()

    @property
    def values(self):
        color = LIST_COLORS[0]
        for btn in self.color_buttons:
            if btn.isChecked():
                color = btn._mintdo_color
                break
        return self.name_entry.text().strip(), color


def confirm_delete_list(parent, name) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Delete list")
    box.setText(f"Delete “{name}”?")
    box.setInformativeText("Tasks in this list move to the Inbox.")
    box.setStandardButtons(QMessageBox.StandardButton.Yes
                           | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


def show_shortcuts(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Keyboard shortcuts")
    dialog.setMinimumWidth(460)
    root = QVBoxLayout(dialog)
    title = QLabel("MintDo")
    title.setObjectName("viewTitle")
    root.addWidget(title)
    for accel, name, desc in SHORTCUTS:
        row = QHBoxLayout()
        key = QLabel(accel)
        key.setObjectName("chip")
        key.setProperty("chip", "plain")
        key.setFixedWidth(120)
        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(130)
        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("viewSub")
        row.addWidget(key)
        row.addWidget(name_lbl)
        row.addWidget(desc_lbl, 1)
        root.addLayout(row)
    dialog.exec()


def show_about(parent):
    logo_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "assets", "icon.svg")
    text = (f"<h2>{APP_NAME}</h2>"
            f"<p>Version {__version__}</p>"
            "<p>A friendly to-do list for Windows.<br>"
            "Lists, tags, subtasks, recurring tasks and daily streaks — "
            "completely offline.</p>")
    box = QMessageBox(parent)
    box.setWindowTitle(f"About {APP_NAME}")
    box.setText(text)
    box.setIconPixmap(_pixmap(logo_path))
    box.exec()


def _pixmap(path):
    from PySide6.QtGui import QPixmap
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray
    if not os.path.exists(path):
        return QPixmap()
    renderer = QSvgRenderer(path)
    pix = QPixmap(96, 96)
    pix.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix

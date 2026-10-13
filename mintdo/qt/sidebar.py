"""Left navigation pane (Qt): smart views, custom lists and live counts."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QLabel, QListWidget,
                               QListWidgetItem, QMenu, QVBoxLayout, QWidget)

from mintdo.db import Database

SMART_VIEWS = (
    ("today", "☀", "Today"),
    ("upcoming", "📆", "Upcoming"),
    ("all", "☰", "All Tasks"),
    ("starred", "★", "Starred"),
    ("inbox", "📥", "Inbox"),
    ("completed", "✓", "Completed"),
)

LIST_COLORS = ("#87cf3e", "#4a86c5", "#d8952a", "#d64f52",
               "#9b59b6", "#1abc9c", "#e67e91", "#7f8c8d")


def dot_icon(color: str, size: int = 12) -> QIcon:
    """A small filled circle in *color* (list bullet)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pix)


def text_icon(ch: str) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setPen(QColor("#757c72"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, ch)
    painter.end()
    return QIcon(pix)


class Sidebar(QWidget):
    """Navigation sidebar. Emits selection through signals."""

    selected = Signal(str, object)      # kind: "view"|"list", key
    new_list_requested = Signal()
    edit_list_requested = Signal(int)
    delete_list_requested = Signal(int)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("sidebar")
        self.setFixedWidth(205)
        self._selection = ("view", "today")
        self._blocks = False

        self.list = QListWidget()
        self.list.setObjectName("navList")
        self.list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(self._current_changed)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)

        self.footer = QLabel()
        self.footer.setObjectName("count")
        self.footer.setContentsMargins(14, 8, 14, 10)
        self.footer.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.footer)
        self.refresh()

    # ------------------------------------------------------------------ #
    def _section(self, text) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(Qt.ItemDataRole.UserRole, ("header", None))
        return item

    def _entry(self, kind, key, icon, title, count=None, color=None):
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, (kind, key))
        if color:
            item.setIcon(dot_icon(color))
        elif icon:
            item.setIcon(text_icon(icon))
        if count is not None:
            item.setToolTip(f"{count} open")
        item.setSizeHint(QSize(0, 34))
        return item

    def refresh(self):
        self._blocks = True
        self.list.clear()
        self.list.addItem(self._section("VIEWS"))
        for key, icon, title in SMART_VIEWS:
            self.list.addItem(
                self._entry("view", key, icon, title,
                            self.db.count_open(key)))
        self.list.addItem(self._section("LISTS"))
        for lst in self.db.lists():
            self.list.addItem(
                self._entry("list", lst["id"], None, lst["name"],
                            self.db.count_open("list", list_id=lst["id"]),
                            lst["color"]))
        add = self._entry("new-list", None, None, "＋  New list")
        add.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.list.addItem(add)

        kind, key = self._selection
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == (kind, key):
                self.list.setCurrentItem(item)
                break
        self._blocks = False

        stats = self.db.stats()
        streak = (f"  ·  🔥 {stats['streak']} day streak"
                  if stats["streak"] else "")
        self.footer.setText(f"✓ {stats['done_today']} done today{streak}")

    def select(self, kind, key):
        self._selection = (kind, key)
        self._blocks = True
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == (kind, key):
                self.list.setCurrentItem(item)
                break
        self._blocks = False

    # ------------------------------------------------------------------ #
    def _current_changed(self, item, _prev):
        if self._blocks or item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        kind, key = data
        if kind == "header":
            self.select(*self._selection)
            return
        if kind == "new-list":
            self.new_list_requested.emit()
            self.select(*self._selection)
            return
        if (kind, key) == self._selection:
            return
        self._selection = (kind, key)
        self.selected.emit(kind, key)

    def _context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        kind, key = data
        if kind != "list":
            return
        menu = QMenu(self)
        edit = menu.addAction("Rename / recolor…")
        delete = menu.addAction("Delete list")
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen is edit:
            self.edit_list_requested.emit(key)
        elif chosen is delete:
            self.delete_list_requested.emit(key)

"""A single task row (Qt): checkbox, title, metadata chips and star."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QToolButton, QVBoxLayout)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_due(due: str) -> tuple:
    """Return (label, chip-kind)."""
    d = date.fromisoformat(due[:10])
    today = date.today()
    if d < today:
        return f"⚠ {d.day} {MONTHS[d.month - 1]}", "overdue"
    if d == today:
        return "Today", "duetoday"
    if d == today + timedelta(days=1):
        return "Tomorrow", "plain"
    if (d - today).days < 7:
        return d.strftime("%A"), "plain"
    return f"{d.day} {MONTHS[d.month - 1]}", "plain"


class TaskRow(QFrame):
    """Card widget for one task; mirrors Gtk ui.taskrow.TaskRow."""

    toggled = Signal(int, bool)     # task_id, done
    starred = Signal(int, bool)     # task_id, starred
    activated = Signal(int)         # task_id (double-click)
    clicked = Signal(int)           # task_id (plain click -> select)

    def __init__(self, task, *, show_list=False, list_label=None, parent=None):
        super().__init__(parent)
        self.setObjectName("taskRow")
        self.task = task
        self.show_list = show_list
        self.list_label = list_label
        self._loading = False

        self.check = QCheckBox()
        self.check.setToolTip("Mark as done")
        self.check.toggled.connect(self._toggled)

        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setWordWrap(False)
        self.title.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        self.chips.setContentsMargins(0, 0, 0, 0)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.addWidget(self.title)
        text_box.addLayout(self.chips)

        self.star = QToolButton()
        self.star.setObjectName("star")
        self.star.setAutoRaise(True)
        self.star.setFixedWidth(28)
        self.star.setToolTip("Star this task")
        self.star.clicked.connect(self._star_clicked)

        box = QHBoxLayout()
        box.setSpacing(10)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.check)
        box.addLayout(text_box, 1)
        box.addWidget(self.star)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(11, 8, 11, 8)
        outer.addLayout(box)
        self.update(task)

    # ------------------------------------------------------------------ #
    def _chip(self, text: str, kind: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("chip", kind)
        return label

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self._repolish(self)

    def update(self, task):  # noqa: A003 - mirrors the GTK row API
        """Re-render row contents from a task dict."""
        self._loading = True
        try:
            done = task["status"] == "done"
            self.check.blockSignals(True)
            self.check.setChecked(done)
            self.check.blockSignals(False)
            self.check.setToolTip(
                "Mark as not done" if done else "Mark as done")

            self.title.setText(task["title"])
            self.title.setProperty("done", "true" if done else "false")
            self._repolish(self.title)

            while self.chips.count():
                item = self.chips.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

            if task.get("due"):
                label, kind = format_due(task["due"])
                self.chips.addWidget(self._chip(label, kind))

            if task.get("priority"):
                prio = task["priority"]
                self.chips.addWidget(self._chip(f"P{prio}", f"p{prio}"))

            if task.get("repeat"):
                unit = {"daily": "day", "weekly": "week",
                        "monthly": "month", "weekdays": "weekday"}[
                            task["repeat"]]
                self.chips.addWidget(self._chip(f"↻ every {unit}", "plain"))

            if self.show_list and self.list_label:
                self.chips.addWidget(self._chip(self.list_label, "plain"))

            tags = task.get("tags", [])
            for tag in tags[:3]:
                self.chips.addWidget(self._chip(f"#{tag}", "tag"))
            if len(tags) > 3:
                self.chips.addWidget(self._chip(f"+{len(tags) - 3}", "tag"))

            if task.get("notes"):
                self.chips.addWidget(self._chip("✎", "plain"))

            if task.get("_sub_progress"):
                done_n, total = task["_sub_progress"]
                self.chips.addWidget(self._chip(f"☑ {done_n}/{total}", "plain"))

            self.chips.addStretch(1)

            starred = bool(task.get("starred"))
            self.star.setText("★" if starred else "☆")
            self.star.setProperty("on", "true" if starred else "false")
            self._repolish(self.star)
        finally:
            self._loading = False
        self.task = task

    # ------------------------------------------------------------------ #
    @staticmethod
    def _repolish(widget):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def _toggled(self, checked):
        if self._loading:
            return
        self.toggled.emit(self.task["id"], checked)

    def _star_clicked(self):
        if self._loading:
            return
        self.starred.emit(self.task["id"], not self.task.get("starred"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task["id"])
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.task["id"])
        super().mouseDoubleClickEvent(event)

"""Right-hand editor panel for the selected task (Qt)."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCalendarWidget, QCheckBox,
                               QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QHBoxLayout, QLabel, QLayout, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QTextEdit, QVBoxLayout,
                               QWidget, QWidgetItem)

from mintdo.db import Database, now_ts as db_now

REPEAT_LABELS = (
    ("", "Never"),
    ("daily", "Every day"),
    ("weekdays", "Every weekday"),
    ("weekly", "Every week"),
    ("monthly", "Every month"),
)

PRIORITIES = (("None", 0), ("P1", 1), ("P2", 2), ("P3", 3), ("P4", 4))


class FlowLayout(QLayout):
    """Arranges child widgets in rows, wrapping like text (for tag chips)."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_h = 0
        space = self.spacing()
        for item in self._items:
            wid = item.sizeHint()
            nx = x + wid.width() + space
            if nx - space > effective.right() and line_h > 0:
                x = effective.x()
                y += line_h + space
                nx = x + wid.width() + space
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(x, y, wid.width(), wid.height()))
            x = nx
            line_h = max(line_h, wid.height())
        return y + line_h - rect.y() + m.bottom()


class DatePickerDialog(QDialog):
    """Modal calendar for choosing a due date."""

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("Pick a due date")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        start = initial or date.today()
        self.calendar.setSelectedDate(
            QDate(start.year, start.month, start.day))
        self.calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        layout.addWidget(self.calendar)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_date(self) -> date:
        q = self.calendar.selectedDate()
        return date(q.year(), q.month(), q.day())


class _ScrollForm(QWidget):
    """Thin wrapper so a QVBoxLayout can be scrolled inside a QScrollArea."""

    def __init__(self, layout):
        super().__init__()
        self.setLayout(layout)


class DetailPanel(QFrame):
    """Shows and edits every field of the currently selected task."""

    changed = Signal()
    delete_requested = Signal(int)
    done_requested = Signal(int)
    star_requested = Signal(int, bool)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.task_id = None
        self._loading = False
        self.setObjectName("detail")
        self.setFixedWidth(330)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_placeholder())
        self.stack.addWidget(self._build_editor())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _heading(text):
        label = QLabel(text)
        label.setObjectName("heading")
        return label

    def _build_placeholder(self):
        placeholder = QWidget()
        pl = QVBoxLayout(placeholder)
        pl.addStretch(1)
        icon = QLabel("👈")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Select a task")
        title.setObjectName("viewTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Click a task on the left to edit\nits details here.")
        sub.setObjectName("viewSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(icon)
        pl.addWidget(title)
        pl.addWidget(sub)
        pl.addStretch(1)
        return placeholder


    def _build_editor(self):
        editor = QWidget()
        root = QVBoxLayout(editor)
        root.setContentsMargins(0, 0, 0, 0)

        form = QVBoxLayout()
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(6)

        # top action row ------------------------------------------------ #
        self.done_btn = QPushButton("✓ Done")
        self.done_btn.clicked.connect(self._toggle_done)
        self.done_btn.setObjectName("primary")
        self.star_btn = QPushButton("☆")
        self.star_btn.setFixedWidth(44)
        self.star_btn.clicked.connect(self._toggle_star)
        self.star_btn.setObjectName("starBtn")
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(self._delete)
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(self.done_btn, 1)
        top.addWidget(self.star_btn)
        top.addWidget(self.del_btn)
        form.addLayout(top)

        # title ------------------------------------------------------ #
        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText("Task title")
        self.title_entry.editingFinished.connect(self._title_committed)
        form.addWidget(self.title_entry)

        self.status_label = QLabel()
        self.status_label.setObjectName("viewSub")
        form.addWidget(self.status_label)

        # due -------------------------------------------------------- #
        form.addWidget(self._heading("DUE DATE"))
        self.due_btn = QPushButton("📅  No date")
        self.due_btn.setObjectName("flat")
        self.due_menu_btn = QPushButton("Pick…")
        self.due_menu_btn.setFixedWidth(70)
        self.due_menu_btn.clicked.connect(self._open_calendar)
        due_row = QHBoxLayout()
        due_row.setSpacing(6)
        due_row.addWidget(self.due_btn, 1)
        due_row.addWidget(self.due_menu_btn)
        form.addLayout(due_row)

        self.quick_due_row = QHBoxLayout()
        self.quick_due_row.setSpacing(4)
        for label, days in (("Today", 0), ("Tomorrow", 1),
                            ("Next week", 7), ("Clear", None)):
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _c=False, d=days: self._due_quick(d))
            self.quick_due_row.addWidget(btn, 1)
        form.addLayout(self.quick_due_row)

        # priority --------------------------------------------------- #
        form.addWidget(self._heading("PRIORITY"))
        self.prio_group = QButtonGroup(self)
        self.prio_group.setExclusive(True)
        prio_row = QHBoxLayout()
        prio_row.setSpacing(0)
        self.prio_buttons = []
        for label, value in PRIORITIES:
            btn = QPushButton(label)
            btn.setObjectName("prio")
            btn.setCheckable(True)
            btn.toggled.connect(
                lambda checked=False, v=value: self._prio_picked(v, checked))
            self.prio_group.addButton(btn)
            self.prio_buttons.append(btn)
            prio_row.addWidget(btn, 1)
        form.addLayout(prio_row)

        # repeat + list ---------------------------------------------- #
        form.addWidget(self._heading("REPEAT"))
        self.repeat_combo = QComboBox()
        for value, label in REPEAT_LABELS:
            self.repeat_combo.addItem(label, userData=value)
        self.repeat_combo.currentIndexChanged.connect(self._repeat_changed)
        form.addWidget(self.repeat_combo)

        form.addWidget(self._heading("LIST"))
        self.list_combo = QComboBox()
        self.list_combo.currentIndexChanged.connect(self._list_changed)
        form.addWidget(self.list_combo)

        # tags ------------------------------------------------------- #
        form.addWidget(self._heading("TAGS"))
        self.tag_container = QWidget()
        self.tag_layout = FlowLayout(self.tag_container, spacing=4)
        self.tag_container.setLayout(self.tag_layout)
        form.addWidget(self.tag_container)
        self.tag_entry = QLineEdit()
        self.tag_entry.setPlaceholderText("Add tag + Enter")
        self.tag_entry.returnPressed.connect(self._add_tag)
        form.addWidget(self.tag_entry)

        # notes ------------------------------------------------------ #
        form.addWidget(self._heading("NOTES"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes…")
        self.notes.setMinimumHeight(96)
        self.notes.textChanged.connect(self._notes_changed)
        form.addWidget(self.notes)

        # subtasks --------------------------------------------------- #
        form.addWidget(self._heading("SUBTASKS"))
        self.sub_progress = QLabel("No steps yet")
        self.sub_progress.setObjectName("viewSub")
        form.addWidget(self.sub_progress)
        self.sub_container = QWidget()
        self.sub_layout = QVBoxLayout(self.sub_container)
        self.sub_layout.setContentsMargins(0, 0, 0, 0)
        self.sub_layout.setSpacing(2)
        form.addWidget(self.sub_container)
        self.sub_entry = QLineEdit()
        self.sub_entry.setPlaceholderText("Add a step + Enter")
        self.sub_entry.returnPressed.connect(self._add_subtask)
        form.addWidget(self.sub_entry)

        form.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(_ScrollForm(form))
        root.addWidget(scroll, 1)
        return editor

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def load(self, task_id):
        task = self.db.get_task(task_id)
        if task is None:
            self.clear()
            return
        self.task_id = task_id
        self._loading = True
        try:
            self.title_entry.setText(task["title"])
            self.notes.setPlainText(task["notes"] or "")
            self._show_due(task["due"])
            self.prio_buttons[int(task["priority"] or 0)].setChecked(True)
            self._set_combo(self.repeat_combo, task["repeat"] or "")

            self._populate_lists()
            self._set_combo(
                self.list_combo,
                str(task["list_id"]) if task["list_id"] else "")
            self._render_tags(task["tags"])

            done = task["status"] == "done"
            self.done_btn.setText("↩ Reopen" if done else "✓ Done")
            self.star_btn.setText("★" if task["starred"] else "☆")
            stamp = f"Created {task['created_at']}"
            if done and task["completed_at"]:
                stamp += f"  ·  Done {task['completed_at']}"
            self.status_label.setText(stamp)
            self._render_subtasks(task_id)
        finally:
            self._loading = False
        self.stack.setCurrentIndex(1)

    def clear(self):
        self.task_id = None
        self.stack.setCurrentIndex(0)

    def reload(self):
        if self.task_id is not None:
            self.load(self.task_id)

    @staticmethod
    def _set_combo(combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _repolish(widget):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    # ------------------------------------------------------------------ #
    # edit handlers
    # ------------------------------------------------------------------ #
    def _save(self, **fields):
        if self._loading or self.task_id is None:
            return
        self.db.update_task(self.task_id, **fields)
        self.changed.emit()

    def _title_committed(self):
        if self.task_id is None or self._loading:
            return
        text = self.title_entry.text().strip()
        if not text:
            task = self.db.get_task(self.task_id)
            self._loading = True
            self.title_entry.setText(task["title"] if task else "")
            self._loading = False
            return
        self._save(title=text)

    def _open_calendar(self):
        if self.task_id is None:
            return
        task = self.db.get_task(self.task_id)
        initial = None
        if task and task["due"]:
            try:
                initial = date.fromisoformat(task["due"][:10])
            except ValueError:
                initial = None
        dialog = DatePickerDialog(self, initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._set_due(dialog.selected_date().isoformat())

    def _due_quick(self, days):
        due = None if days is None else \
            (date.today() + timedelta(days=days)).isoformat()
        self._set_due(due)

    def _set_due(self, due):
        self._show_due(due)
        self._save(due=due)

    def _show_due(self, due):
        if not due:
            self.due_btn.setText("📅  No date")
            self.due_btn.setProperty("due", "")
            self._repolish(self.due_btn)
            return
        d = date.fromisoformat(due[:10])
        today = date.today()
        if d < today:
            text, cls = f"📅  Overdue · {d.day} {d.strftime('%b')}", "overdue"
        elif d == today:
            text, cls = "📅  Today", "today"
        elif d == today + timedelta(days=1):
            text, cls = "📅  Tomorrow", ""
        elif (d - today).days < 7:
            text, cls = f"📅  {d.strftime('%A')}", ""
        else:
            text, cls = f"📅  {d.day} {d.strftime('%b %Y')}", ""
        self.due_btn.setText(text)
        self.due_btn.setProperty("due", cls)
        self._repolish(self.due_btn)

    def _prio_picked(self, value, checked=True):
        if self._loading or not checked:
            return
        self._save(priority=value)

    def _repeat_changed(self, _index):
        if self._loading:
            return
        self._save(repeat=self.repeat_combo.currentData() or "")

    def _list_changed(self, _index):
        if self._loading:
            return
        active = self.list_combo.currentData()
        self._save(list_id=int(active) if active else None)

    def _populate_lists(self):
        was_loading = self._loading
        self._loading = True
        self.list_combo.clear()
        self.list_combo.addItem("📥 Inbox", userData="")
        for lst in self.db.lists():
            self.list_combo.addItem(lst["name"], userData=str(lst["id"]))
        self._loading = was_loading

    # -- tags --------------------------------------------------------- #
    def _add_tag(self):
        text = self.tag_entry.text().strip().lower().replace(",", " ")
        self.tag_entry.clear()
        if not text or self.task_id is None:
            return
        tags = self.db.tags_of(self.task_id)
        for token in text.split():
            token = token.lstrip("#")
            if token and token not in tags:
                tags.append(token)
        self.db.set_tags(self.task_id, tags)
        self._render_tags(self.db.tags_of(self.task_id))
        self.changed.emit()

    def _remove_tag(self, tag):
        if self.task_id is None:
            return
        tags = [t for t in self.db.tags_of(self.task_id) if t != tag]
        self.db.set_tags(self.task_id, tags)
        self._render_tags(tags)
        self.changed.emit()

    def _render_tags(self, tags):
        _clear_layout(self.tag_layout)
        for tag in tags:
            chip = QPushButton(f"{tag}  ×")
            chip.setObjectName("chip")
            chip.setProperty("tag", tag)
            chip.clicked.connect(lambda _c=False, t=tag: self._remove_tag(t))
            self.tag_layout.addWidget(chip)

    # -- notes -------------------------------------------------------- #
    def _notes_changed(self):
        if self._loading or self.task_id is None:
            return
        task = self.db.get_task(self.task_id)
        text = self.notes.toPlainText().rstrip("\n")
        if task is not None and (task["notes"] or "") != text:
            self._save(notes=text)

    # -- subtasks ----------------------------------------------------- #
    def _add_subtask(self):
        text = self.sub_entry.text().strip()
        self.sub_entry.clear()
        if not text or self.task_id is None:
            return
        parent = self.db.get_task(self.task_id)
        self.db.add_task(text, list_id=parent.get("list_id"),
                         parent_id=self.task_id)
        self._render_subtasks(self.task_id)
        self.changed.emit()

    def _sub_toggled(self, checked, sub_id):
        if self._loading:
            return
        if checked:
            self.db.update_task(sub_id, status="done", completed_at=db_now())
        else:
            self.db.update_task(sub_id, status="open", completed_at=None)
        self._render_subtasks(self.task_id)
        self.changed.emit()

    def _sub_delete(self, sub_id):
        self.db.delete_task(sub_id)
        self._render_subtasks(self.task_id)
        self.changed.emit()

    def _render_subtasks(self, task_id):
        _clear_layout(self.sub_layout)
        subs = self.db.fetch_subtasks(task_id)
        done = sum(1 for s in subs if s["status"] == "done")
        self.sub_progress.setText(
            f"{done} of {len(subs)} steps done" if subs else "No steps yet")
        for sub in subs:
            row = QHBoxLayout()
            row.setSpacing(4)
            check = QCheckBox(sub["title"])
            if sub["status"] == "done":
                font = check.font()
                font.setStrikeOut(True)
                check.setFont(font)
            check.setChecked(sub["status"] == "done")
            check.toggled.connect(
                lambda c=False, sid=sub["id"]: self._sub_toggled(c, sid))
            kill = QPushButton("×")
            kill.setObjectName("flat")
            kill.setFixedWidth(28)
            kill.setToolTip("Remove step")
            kill.clicked.connect(
                lambda _c=False, sid=sub["id"]: self._sub_delete(sid))
            row.addWidget(check, 1)
            row.addWidget(kill)
            self.sub_layout.addLayout(row)
        self.sub_layout.addStretch(1)

    # -- actions ------------------------------------------------------ #
    def _toggle_done(self):
        if self.task_id is not None:
            self.done_requested.emit(self.task_id)

    def _toggle_star(self):
        if self.task_id is None:
            return
        task = self.db.get_task(self.task_id)
        value = not task.get("starred")
        self.star_btn.setText("★" if value else "☆")
        self.star_requested.emit(self.task_id, value)

    def _delete(self):
        if self.task_id is not None:
            self.delete_requested.emit(self.task_id)


def _clear_layout(layout):
    """Remove and delete every item in *layout* (safe for nested layouts)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            child = item.layout()
            if child is not None:
                _clear_layout(child)

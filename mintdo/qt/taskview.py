"""Central pane (Qt): view header, quick-add, search, sort and task list."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from mintdo.qt.taskrow import TaskRow

SORTS = (
    ("smart", "Recommended"),
    ("due", "Due date"),
    ("priority", "Priority"),
    ("alpha", "Name (A–Z)"),
    ("created", "Newest first"),
    ("manual", "Manual order"),
)


class TaskView(QWidget):
    """Mirror of Gtk ui.taskview.TaskView."""

    quick_add_requested = Signal(str)
    select_requested = Signal(int)
    activate_requested = Signal(int)
    toggle_requested = Signal(int, bool)
    star_requested = Signal(int, bool)
    delete_requested = Signal(int)
    search_changed = Signal(str)
    sort_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskView")
        self.sort = "smart"
        self.show_list = False
        self.selected_id = None
        self.rows = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- header: title + subtitle + sort --- #
        self.title_label = QLabel()
        self.title_label.setObjectName("viewTitle")
        self.sub_label = QLabel()
        self.sub_label.setObjectName("viewSub")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)
        titles.addWidget(self.title_label)
        titles.addWidget(self.sub_label)

        self.sort_button = QPushButton("Sort ▾")
        self.sort_button.setObjectName("flat")
        self.sort_index = 0
        self.sort_button.clicked.connect(self._cycle_sort)

        head = QHBoxLayout()
        head.setContentsMargins(16, 14, 12, 6)
        head.addLayout(titles, 1)
        head.addWidget(self.sort_button)
        root.addLayout(head)

        # --- quick add --- #
        self.entry = QLineEdit()
        self.entry.setObjectName("quickAdd")
        self.entry.setPlaceholderText(
            "Add a task…  e.g.  !1 buy flowers #gift tomorrow")
        self.entry.returnPressed.connect(self._quick_add)
        entry_wrap = QWidget()
        ew = QVBoxLayout(entry_wrap)
        ew.setContentsMargins(16, 0, 16, 0)
        ew.addWidget(self.entry)
        root.addWidget(entry_wrap)

        hint = QLabel("!1–!4 priority · #tag · today/tomorrow/weekday · "
                      "every day/week")
        hint.setObjectName("viewSub")
        hint_wrap = QWidget()
        hw = QVBoxLayout(hint_wrap)
        hw.setContentsMargins(18, 0, 16, 2)
        hw.addWidget(hint)
        root.addWidget(hint_wrap)

        # --- search --- #
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search tasks…")
        self.search_entry.textChanged.connect(self.search_changed)
        search_wrap = QWidget()
        sw = QVBoxLayout(search_wrap)
        sw.setContentsMargins(16, 6, 16, 0)
        sw.addWidget(self.search_entry)
        self.search_wrap = search_wrap
        self.search_wrap.setVisible(False)
        root.addWidget(search_wrap)

        # --- task list (scrollable) --- #
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.inner = QWidget()
        self.inner.setObjectName("taskListInner")
        self.list_layout = QVBoxLayout(self.inner)
        self.list_layout.setContentsMargins(16, 8, 16, 12)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.inner)

        # --- empty state --- #
        self.empty_box = QWidget()
        eb = QVBoxLayout(self.empty_box)
        eb.addStretch(1)
        self.empty_big = QLabel()
        self.empty_big.setObjectName("viewTitle")
        self.empty_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("viewTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_sub = QLabel()
        self.empty_sub.setObjectName("viewSub")
        self.empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eb.addWidget(self.empty_big)
        eb.addWidget(self.empty_title)
        eb.addWidget(self.empty_sub)
        eb.addStretch(1)

        root.addWidget(self.scroll, 1)
        root.addWidget(self.empty_box, 1)
        self.empty_box.setVisible(False)

        # keyboard: Delete removes selection
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self,
                  self._delete_selected)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def set_header(self, title, subtitle):
        self.title_label.setText(title)
        self.sub_label.setText(subtitle)

    def set_tasks(self, tasks, empty=None, show_list=False, list_names=None):
        self.show_list = show_list
        list_names = list_names or {}
        previous = self.selected_id
        self._clear_rows()
        self.rows = []
        for task in tasks:
            row = TaskRow(
                task, show_list=show_list,
                list_label=list_names.get(task.get("list_id")))
            row.toggled.connect(self.toggle_requested)
            row.starred.connect(self.star_requested)
            row.clicked.connect(self._row_clicked)
            row.activated.connect(self.activate_requested)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            self.rows.append(row)
            row.show()   # Qt does not auto-show widgets added after show()

        if tasks:
            self.scroll.setVisible(True)
            self.empty_box.setVisible(False)
            if previous is not None:
                self.select_task(previous)
        else:
            icon, big, small = empty or ("✨", "Nothing here", "")
            self.empty_big.setText(icon)
            self.empty_title.setText(big)
            self.empty_sub.setText(small)
            self.scroll.setVisible(False)
            self.empty_box.setVisible(True)
            self.selected_id = None

    def selected_task_id(self):
        return self.selected_id

    def select_task(self, task_id):
        found = False
        for row in self.rows:
            is_sel = row.task["id"] == task_id
            row.set_selected(is_sel)
            if is_sel:
                found = True
        if found:
            self.selected_id = task_id
        else:
            self.selected_id = None
        return found

    def focus_quick_add(self):
        self.entry.setFocus()
        self.entry.selectAll()

    def set_search_visible(self, visible):
        self.search_wrap.setVisible(visible)
        if visible:
            self.search_entry.setFocus()

    def toggle_search(self):
        self.set_search_visible(not self.search_wrap.isVisible())

    def clear_search(self):
        self.search_entry.setText("")

    # ------------------------------------------------------------------ #
    # internal handlers
    # ------------------------------------------------------------------ #
    def _clear_rows(self):
        for row in self.rows:
            self.list_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []

    def _row_clicked(self, task_id):
        if self.selected_id == task_id:
            return
        self.select_task(task_id)
        self.select_requested.emit(task_id)

    def _quick_add(self):
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.setText("")
        self.quick_add_requested.emit(text)

    def _cycle_sort(self):
        self.sort_index = (self.sort_index + 1) % len(SORTS)
        self.sort = SORTS[self.sort_index][0]
        self.sort_button.setText(f"{SORTS[self.sort_index][1]} ▾")
        self.sort_changed.emit(self.sort)

    def _delete_selected(self):
        if self.selected_id is not None:
            self.delete_requested.emit(self.selected_id)

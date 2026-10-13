"""Main application window (Qt)."""
from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout,
                               QMainWindow, QMessageBox, QSplitter, QWidget)

from mintdo import APP_NAME
from mintdo.core import VIEW_META
from mintdo.db import Database
from mintdo.qt import dialogs
from mintdo.qt.detail import DetailPanel
from mintdo.qt.sidebar import Sidebar
from mintdo.qt.stats import StatsDialog
from mintdo.qt.taskview import TaskView
from mintdo.qt.theme import Theme, build_stylesheet
from mintdo.qt.toast import Toast
from mintdo.quickadd import parse as parse_quick_add


class MainWindow(QMainWindow):
    def __init__(self, db: Database, theme: Theme, smoke: bool = False):
        super().__init__()
        self.db = db
        self.theme = theme
        self.smoke = smoke
        self.kind, self.key = "view", "today"
        self.search_term = ""

        self.setWindowTitle(APP_NAME)
        self.resize(1120, 720)
        self.setMinimumSize(880, 560)
        self._set_window_icon()

        self._build_actions()
        self._build_ui()
        self._restore_state()
        self.load_view()

    # ------------------------------------------------------------------ #
    def _build_actions(self):
        def act(text, slot, seq=None):
            action = QAction(text, self)
            if seq:
                action.setShortcut(QKeySequence(seq))
            action.triggered.connect(slot)
            self.addAction(action)
            return action

        act("New task", self.focus_quick_add, "Ctrl+N")
        act("New list", self.new_list, "Ctrl+Shift+N")
        act("Search", self.toggle_search, "Ctrl+F")
        act("Undo", self.undo, "Ctrl+Z")
        act("Toggle dark", self.toggle_dark, "Ctrl+D")
        act("Stats", self.show_stats, "Ctrl+I")
        act("Export backup", self.export_backup, "Ctrl+Shift+S")
        act("Import backup", self.import_backup, "Ctrl+Shift+O")
        act("Sidebar", self.toggle_sidebar, "Ctrl+B")
        act("Shortcuts", self.show_shortcuts, "F1")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = Sidebar(self.db)
        self.sidebar.selected.connect(self.on_sidebar_select)
        self.sidebar.new_list_requested.connect(self.new_list)
        self.sidebar.edit_list_requested.connect(self.edit_list)
        self.sidebar.delete_list_requested.connect(self.delete_list)

        self.taskview = TaskView()
        self.taskview.quick_add_requested.connect(self.quick_add)
        self.taskview.select_requested.connect(self.on_row_selected)
        self.taskview.activate_requested.connect(self.on_row_activated)
        self.taskview.toggle_requested.connect(self.on_toggle_task)
        self.taskview.star_requested.connect(self.on_star_task)
        self.taskview.delete_requested.connect(self.on_delete_task)
        self.taskview.search_changed.connect(self.on_search)
        self.taskview.sort_changed.connect(self.on_sort)

        self.detail = DetailPanel(self.db)
        self.detail.changed.connect(self.refresh)
        self.detail.delete_requested.connect(self.on_delete_task)
        self.detail.done_requested.connect(self.on_toggle_task)
        self.detail.star_requested.connect(self.on_star_task)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.taskview)
        self.splitter.addWidget(self.detail)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([700, 330])

        outer.addWidget(self.sidebar)
        outer.addWidget(self.splitter, 1)

        self.toast = Toast(central)

    def _restore_state(self):
        settings = QSettings("totoman", "MintDo")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        sidebar_hidden = settings.value("sidebarHidden", False, type=bool)
        self.sidebar.setVisible(not sidebar_hidden)

    def _set_window_icon(self):
        # Prefer the multi-resolution .ico (Windows); fall back to the SVG.
        assets = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "assets")
        for name in ("icon.ico", "icon.png", "icon.svg"):
            path = os.path.join(assets, name)
            if os.path.exists(path):
                icon = QIcon(path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    return

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        settings = QSettings("totoman", "MintDo")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("sidebarHidden", self.sidebar.isHidden())
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # action handlers
    # ------------------------------------------------------------------ #
    def focus_quick_add(self):
        self.taskview.focus_quick_add()

    def toggle_search(self):
        self.taskview.toggle_search()

    def toggle_sidebar(self):
        self.sidebar.setVisible(self.sidebar.isHidden())

    def toggle_dark(self):
        mode = "light" if self.theme.prefers_dark() else "dark"
        self.apply_theme(mode)

    def apply_theme(self, mode):
        self.theme.set_mode(mode)
        self.db.set_setting("theme", mode)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(self.theme.prefers_dark()))

    def show_stats(self):
        dialog = StatsDialog(self.db, self)
        dialog.refresh()
        dialog.exec()

    def show_shortcuts(self):
        dialogs.show_shortcuts(self)

    def show_about(self):
        dialogs.show_about(self)

    def undo(self):
        if self.toast.isVisible():
            self.toast.trigger_undo()

    # ------------------------------------------------------------------ #
    # view logic
    # ------------------------------------------------------------------ #
    def refresh(self):
        self.sidebar.refresh()
        self.load_view()

    def load_view(self):
        search, sort = self.search_term, self.taskview.sort
        list_names = {lst["id"]: lst["name"] for lst in self.db.lists()}

        def count_note(n):
            return f"{n} task" + ("s" if n != 1 else "")

        if self.kind == "view":
            title, sub, empty = VIEW_META[self.key]
            tasks = self.db.fetch_tasks(self.key, search=search, sort=sort)
            show_list = self.key not in ("inbox", "completed")
            sub = f"{count_note(len(tasks))} · {sub}"
        else:
            lst = self.db.get_list(self.key)
            if lst is None:  # list deleted underneath us
                self.kind, self.key = "view", "all"
                self.sidebar.select("view", "all")
                self.load_view()
                return
            title = lst["name"]
            sub = f"{count_note(self.db.count_open('list', self.key))} open"
            tasks = self.db.fetch_tasks("list", list_id=self.key,
                                        search=search, sort=sort)
            show_list = False
            empty = ("🗒️", "No tasks here", "Add one with the box above ⬆")
        if search:
            plural = "" if len(tasks) == 1 else "s"
            sub = f"{len(tasks)} result{plural} for “{search}”"
        progress = self.db.subtask_progress()
        for task in tasks:
            step = progress.get(task["id"])
            if step:
                task["_sub_progress"] = step
        self.taskview.set_header(title, sub)
        self.taskview.set_tasks(tasks, empty=empty, show_list=show_list,
                                list_names=list_names)

        selected = self.taskview.selected_task_id()
        if selected is not None:
            if self.detail.task_id != selected:
                self.detail.load(selected)
        elif (self.detail.task_id is not None
              and self.db.get_task(self.detail.task_id) is None):
            self.detail.clear()

    # ------------------------------------------------------------------ #
    # task callbacks
    # ------------------------------------------------------------------ #
    def on_row_selected(self, task_id):
        self.detail.load(task_id)

    def on_row_activated(self, task_id):
        self.detail.load(task_id)
        self.detail.title_entry.setFocus()
        self.detail.title_entry.selectAll()

    def quick_add(self, text):
        parsed = parse_quick_add(text)
        if not parsed["title"]:
            return
        list_id = self.key if self.kind == "list" else None
        tid = self.db.add_task(
            parsed["title"], list_id=list_id, due=parsed["due"],
            priority=parsed["priority"], repeat=parsed["repeat"])
        if parsed["tags"]:
            self.db.set_tags(tid, parsed["tags"])
        self.refresh()
        if self.taskview.select_task(tid):
            self.detail.load(tid)
        self.taskview.focus_quick_add()

    def on_toggle_task(self, task_id, done=None):
        task = self.db.get_task(task_id)
        if task is None:
            return
        if done is None:
            done = task["status"] != "done"
        if done:
            info = self.db.complete_task(task_id)
            message = f"Done: {task['title']}"
            if info["new_id"]:
                message += "  ·  next occurrence scheduled"

            def undo():
                self.db.uncomplete_task(task_id)
                if info["new_id"]:
                    self.db.delete_task(info["new_id"])
                self.refresh()

            self.refresh()
            self.toast.show_toast(message, undo)
        else:
            def undo():
                self.db.complete_task(task_id)
                self.refresh()

            self.db.uncomplete_task(task_id)
            self.refresh()
            self.toast.show_toast(f"Reopened: {task['title']}", undo)

    def on_star_task(self, task_id, value):
        self.db.update_task(task_id, starred=bool(value))
        self.refresh()

    def on_delete_task(self, task_id):
        task = self.db.get_task(task_id)
        if task is None:
            return
        snapshot = self.db.delete_task(task_id)
        if self.detail.task_id == task_id:
            self.detail.clear()

        def undo():
            self.db.restore_task(snapshot)
            self.refresh()
            self.taskview.select_task(task_id)

        self.refresh()
        self.toast.show_toast(f"Deleted: {task['title']}", undo)

    def on_search(self, term):
        self.search_term = term
        self.load_view()

    def on_sort(self, _value):
        self.load_view()

    def on_sidebar_select(self, kind, key):
        self.kind, self.key = kind, key
        self.load_view()

    # ------------------------------------------------------------------ #
    # list management
    # ------------------------------------------------------------------ #
    def new_list(self):
        dialog = dialogs.ListDialog(self, title="New list")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.values
            lid = self.db.add_list(name, color)
            self.sidebar.select("list", lid)
            self.kind, self.key = "list", lid
            self.refresh()

    def edit_list(self, list_id):
        lst = self.db.get_list(list_id)
        if lst is None:
            return
        dialog = dialogs.ListDialog(self, title="Edit list",
                                    initial_name=lst["name"],
                                    initial_color=lst["color"])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.values
            self.db.rename_list(list_id, name)
            self.db.set_list_color(list_id, color)
            self.refresh()

    def delete_list(self, list_id):
        lst = self.db.get_list(list_id)
        if lst is None:
            return
        if not dialogs.confirm_delete_list(self, lst["name"]):
            return
        self.db.delete_list(list_id)
        if self.kind == "list" and self.key == list_id:
            self.kind, self.key = "view", "all"
            self.sidebar.select("view", "all")
        self.refresh()

    # ------------------------------------------------------------------ #
    # backup
    # ------------------------------------------------------------------ #
    def export_backup(self):
        default = f"mintdo-backup-{date.today().isoformat()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export backup", default, "MintDo backup (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.db.export_json())
            self.toast.show_toast(
                f"Backup saved: {os.path.basename(path)}")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def import_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import backup", "", "MintDo backup (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                count = self.db.import_json(handle.read())
            self.refresh()
            self.toast.show_toast(f"Imported {count} tasks")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

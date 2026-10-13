"""Functional tests for the Qt (Windows) front-end.

These drive the *real* PySide6 widgets under the ``offscreen`` platform, so
they catch wiring/rendering bugs the headless unit tests cannot. They are
skipped automatically when PySide6 is not installed.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    import PySide6  # noqa: F401
except Exception:  # pragma: no cover - PySide6 optional on some CI
    QApplication = None
    QDialog = None

from mintdo import db as dbmod
from mintdo.qt import dialogs
from mintdo.qt.mainwindow import MainWindow
from mintdo.qt.theme import Theme, build_stylesheet


class _FakeListDialog:
    """Stands in for dialogs.ListDialog, accepting a parent + kwargs."""

    def __init__(self, *args, **kwargs):
        self._values = ("Fresh", "#4a86c5")

    def exec(self):
        return QDialog.DialogCode.Accepted

    @property
    def values(self):
        return self._values


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class QtUiTestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = dbmod.Database(":memory:")
        dbmod.seed_if_empty(self.db)
        self.theme = Theme()
        self.theme.set_mode("light")
        self.win = MainWindow(self.db, self.theme)
        self.win.show()
        self._pump()

    def tearDown(self):
        self.win.close()
        self.db.close()

    def _pump(self):
        for _ in range(3):
            self.app.processEvents()

    def _titles(self):
        return [r.task["title"] for r in self.win.taskview.rows]

    # ------------------------------------------------------------------ #
    def test_window_builds_and_shows(self):
        self.assertTrue(self.win.isVisible())
        self.assertGreater(len(self.win.taskview.rows), 0)

    def test_quick_add_creates_and_selects(self):
        self.win.quick_add("!1 buy flowers #gift tomorrow")
        self._pump()
        matches = self.db.fetch_tasks("all", search="buy flowers")
        self.assertEqual(len(matches), 1)
        task = matches[0]
        self.assertEqual(task["priority"], 1)
        self.assertIn("gift", task["tags"])
        self.assertEqual(
            task["due"], (date.today() + timedelta(days=1)).isoformat())

    def test_quick_add_empty_is_ignored(self):
        before = len(self.win.taskview.rows)
        self.win.quick_add("   ")
        self._pump()
        self.assertEqual(len(self.win.taskview.rows), before)

    def test_row_selection_loads_detail(self):
        first = self.win.taskview.rows[0]
        first.clicked.emit(first.task["id"])
        self._pump()
        self.assertEqual(self.win.detail.task_id, first.task["id"])
        self.assertEqual(self.win.detail.title_entry.text(),
                         first.task["title"])

    def test_toggle_done_then_undo(self):
        task = self.db.fetch_tasks("today")[0]
        self.win.on_toggle_task(task["id"])
        self._pump()
        self.assertEqual(self.db.get_task(task["id"])["status"], "done")
        self.assertTrue(self.win.toast.isVisible())
        self.win.toast.trigger_undo()
        self._pump()
        self.assertEqual(self.db.get_task(task["id"])["status"], "open")

    def test_recurring_toggle_schedules_next(self):
        tid = self.db.add_task("water plants", repeat="daily",
                               due=date.today().isoformat())
        self.win.on_toggle_task(tid)
        self._pump()
        # original is completed; the next daily occurrence is now open
        self.assertEqual(self.db.get_task(tid)["status"], "done")
        remaining = self.db.fetch_tasks("all", search="water plants")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(
            remaining[0]["due"],
            (date.today() + timedelta(days=1)).isoformat())

    def test_delete_then_undo_restores(self):
        tid = self.db.add_task("temporary")
        before = self.db.count_open("all")
        self.win.on_delete_task(tid)
        self._pump()
        self.assertIsNone(self.db.get_task(tid))
        self.win.toast.trigger_undo()
        self._pump()
        self.assertIsNotNone(self.db.get_task(tid))
        self.assertEqual(self.db.count_open("all"), before)

    def test_star_toggle(self):
        tid = self.db.add_task("star me")
        self.win.on_star_task(tid, True)
        self._pump()
        self.assertTrue(self.db.get_task(tid)["starred"])
        self.win.on_star_task(tid, False)
        self._pump()
        self.assertFalse(self.db.get_task(tid)["starred"])

    def test_search_filters_rows(self):
        self.win.on_sidebar_select("view", "all")
        self._pump()
        self.db.add_task("unique-searchable-item")
        self.win.taskview.search_entry.setText("unique-searchable")
        self._pump()
        self.assertIn("unique-searchable-item", self._titles())

    def test_sidebar_navigation(self):
        self.win.on_sidebar_select("view", "starred")
        self._pump()
        self.assertEqual((self.win.kind, self.win.key), ("view", "starred"))

    def test_sidebar_select_list(self):
        lid = self.db.add_list("QtList")
        self.db.add_task("in list", list_id=lid)
        self.win.on_sidebar_select("list", lid)
        self._pump()
        self.assertEqual(self.win.key, lid)
        self.assertIn("in list", self._titles())

    # ---- detail panel edits ---------------------------------------- #
    def test_detail_priority(self):
        tid = self.db.add_task("prio task")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.prio_buttons[2].setChecked(True)   # P2
        self._pump()
        self.assertEqual(self.db.get_task(tid)["priority"], 2)

    def test_detail_title_edit(self):
        tid = self.db.add_task("old title")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.title_entry.setText("new title")
        self.win.detail._title_committed()
        self._pump()
        self.assertEqual(self.db.get_task(tid)["title"], "new title")

    def test_detail_empty_title_reverts(self):
        tid = self.db.add_task("keep me")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.title_entry.setText("")
        self.win.detail._title_committed()
        self._pump()
        self.assertEqual(self.db.get_task(tid)["title"], "keep me")

    def test_detail_tags(self):
        tid = self.db.add_task("tagged")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.tag_entry.setText("alpha beta")
        self.win.detail._add_tag()
        self._pump()
        self.assertEqual(set(self.db.get_task(tid)["tags"]), {"alpha", "beta"})
        self.win.detail._remove_tag("alpha")
        self._pump()
        self.assertEqual(self.db.get_task(tid)["tags"], ["beta"])

    def test_detail_subtasks(self):
        tid = self.db.add_task("parent")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.sub_entry.setText("step one")
        self.win.detail._add_subtask()
        self.win.detail.sub_entry.setText("step two")
        self.win.detail._add_subtask()
        self._pump()
        self.assertEqual(len(self.db.fetch_subtasks(tid)), 2)

    def test_detail_subtask_toggle(self):
        tid = self.db.add_task("parent2")
        sid = self.db.add_task("child", parent_id=tid)
        self.win.detail.load(tid)
        self._pump()
        self.win.detail._sub_toggled(True, sid)
        self._pump()
        self.assertEqual(self.db.get_task(sid)["status"], "done")

    def test_detail_due_quick(self):
        tid = self.db.add_task("due task")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail._due_quick(1)
        self._pump()
        self.assertEqual(
            self.db.get_task(tid)["due"],
            (date.today() + timedelta(days=1)).isoformat())

    def test_detail_repeat(self):
        tid = self.db.add_task("repeat task")
        self.win.detail.load(tid)
        self._pump()
        for i in range(self.win.detail.repeat_combo.count()):
            if self.win.detail.repeat_combo.itemData(i) == "weekly":
                self.win.detail.repeat_combo.setCurrentIndex(i)
                break
        self._pump()
        self.assertEqual(self.db.get_task(tid)["repeat"], "weekly")

    def test_detail_notes(self):
        tid = self.db.add_task("notes task")
        self.win.detail.load(tid)
        self._pump()
        self.win.detail.notes.setPlainText("some note text")
        self.win.detail._notes_changed()
        self._pump()
        self.assertEqual(self.db.get_task(tid)["notes"], "some note text")

    def test_detail_move_to_list(self):
        lid = self.db.add_list("Movable")
        tid = self.db.add_task("move me")
        self.win.detail.load(tid)
        self._pump()
        for i in range(self.win.detail.list_combo.count()):
            if self.win.detail.list_combo.itemData(i) == str(lid):
                self.win.detail.list_combo.setCurrentIndex(i)
                break
        self._pump()
        self.assertEqual(self.db.get_task(tid)["list_id"], lid)

    # ---- list management ------------------------------------------- #
    def test_new_list(self):
        original = dialogs.ListDialog
        try:
            dialogs.ListDialog = _FakeListDialog
            self.win.new_list()
        finally:
            dialogs.ListDialog = original
        self._pump()
        self.assertIn("Fresh", [l["name"] for l in self.db.lists()])

    def test_delete_list_moves_tasks_to_inbox(self):
        lid = self.db.add_list("Doomed")
        tid = self.db.add_task("orphan", list_id=lid)
        original = dialogs.confirm_delete_list
        try:
            dialogs.confirm_delete_list = lambda *_: True
            self.win.delete_list(lid)
        finally:
            dialogs.confirm_delete_list = original
        self._pump()
        self.assertIsNone(self.db.get_list(lid))
        self.assertIsNone(self.db.get_task(tid)["list_id"])

    # ---- theme ------------------------------------------------------ #
    def test_toggle_theme(self):
        self.win.toggle_dark()
        self._pump()
        self.assertEqual(self.db.get_setting("theme"), "dark")
        self.assertEqual(self.app.styleSheet(), build_stylesheet(True))
        self.win.toggle_dark()
        self._pump()
        self.assertEqual(self.db.get_setting("theme"), "light")
        self.assertEqual(self.app.styleSheet(), build_stylesheet(False))

    # ---- stats ------------------------------------------------------ #
    def test_stats_dialog_refresh(self):
        from mintdo.qt.stats import StatsDialog
        dialog = StatsDialog(self.db)
        dialog.refresh()   # must not raise
        self.assertIsNotNone(dialog)


if __name__ == "__main__":
    unittest.main()

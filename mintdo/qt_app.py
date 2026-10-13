"""Qt (PySide6) front-end: the Windows build of MintDo.

Run with:  python -m mintdo.qt_app [--smoke-test]
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from mintdo import APP_NAME
from mintdo.db import Database, seed_if_empty
from mintdo.paths import data_dir, db_path
from mintdo.qt.mainwindow import MainWindow
from mintdo.qt.theme import Theme, build_stylesheet


def _smoke_check(win, db):
    problems = []
    if not win.isVisible():
        problems.append("window not visible")
    if len(win.taskview.rows) == 0:
        problems.append("task list is empty")
    if win.sidebar.list.count() == 0:
        problems.append("sidebar is empty")
    win.quick_add("!1 smoke test #qa tomorrow")
    if not db.fetch_tasks("all", search="smoke test"):
        problems.append("quick-add did not create a task")
    # rows rebuilt by the refresh must actually be visible
    rows = win.taskview.rows
    if not rows or not all(r.isVisible() for r in rows):
        problems.append("task rows exist but are not visible")
    for hit in db.fetch_tasks("all", search="#qa"):
        db.delete_task(hit["id"])
    win.refresh()
    if problems:
        print("SMOKE FAIL: " + "; ".join(problems), file=sys.stderr)
        win._smoke_failed = True
    else:
        print("SMOKE OK")
    QApplication.quit()


def run(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    smoke = "--smoke-test" in argv
    argv = [a for a in argv if a != "--smoke-test"]

    os.makedirs(data_dir(), exist_ok=True)
    db = Database(db_path())
    seed_if_empty(db)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("totoman")

    theme = Theme()
    theme.set_mode(db.get_setting("theme", "system"))
    app.setStyleSheet(build_stylesheet(theme.prefers_dark()))

    win = MainWindow(db, theme, smoke=smoke)
    win.show()

    if smoke:
        QTimer.singleShot(600, lambda: _smoke_check(win, db))

    code = app.exec()
    db.close()
    return 1 if getattr(win, "_smoke_failed", False) else code


if __name__ == "__main__":
    sys.exit(run(sys.argv))

"""SQLite persistence layer for MintDo.

All data lives in a single database file (default: ~/.local/share/mintdo/mintdo.db).
The layer is pure Python + sqlite3 so it can be unit-tested without GTK.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

# Columns allowed on the tasks table (used for dynamic updates).
TASK_FIELDS = {
    "list_id", "parent_id", "title", "notes", "due", "priority", "starred",
    "repeat", "status", "position", "created_at", "completed_at",
}

VIEWS = ("today", "upcoming", "all", "starred", "inbox", "completed")

REPEATS = ("", "daily", "weekdays", "weekly", "monthly")

SCHEMA = """
CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#87CF3E',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER REFERENCES lists(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    due TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    starred INTEGER NOT NULL DEFAULT 0,
    repeat TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS tags (
    name TEXT NOT NULL PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS task_tags (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag TEXT NOT NULL REFERENCES tags(name) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag)
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due);
"""


def today() -> str:
    return date.today().isoformat()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _add_month(d: date) -> date:
    y, m = (d.year, d.month + 1) if d.month < 12 else (d.year + 1, 1)
    if m == 2:
        leap = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
        last = 29 if leap else 28
    else:
        last = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, last))


def advance_due(due: str | None, repeat: str) -> str:
    """Next occurrence for a recurring task, always in the future."""
    base = date.today()
    if due:
        try:
            base = date.fromisoformat(str(due)[:10])
        except ValueError:
            pass

    def step(d: date) -> date:
        if repeat == "weekly":
            return d + timedelta(days=7)
        if repeat == "monthly":
            return _add_month(d)
        if repeat == "weekdays":
            n = d + timedelta(days=1)
            while n.weekday() >= 5:
                n += timedelta(days=1)
            return n
        return d + timedelta(days=1)  # daily (default)

    nxt = step(base)
    for _ in range(800):
        if nxt > date.today():
            break
        nxt = step(nxt)
    return nxt.isoformat()



def seed_if_empty(db: "Database") -> None:
    """First-run tour so the app never opens completely empty."""
    if db.get_setting("seeded") == "1":
        return
    if db.fetch_tasks("all") or db.lists():
        db.set_setting("seeded", "1")
        return
    lid = db.add_list("Getting Started", "#87cf3e")

    welcome = db.add_task("Welcome to MintDo! 🌱", list_id=lid,
                          starred=True, due=today(), priority=2)
    db.set_tags(welcome, ["welcome"])
    db.update_task(welcome, notes=(
        "Everything is saved offline, all by yourself.\n"
        "• Double-click a task to edit it in the panel on the right\n"
        "• Right-click a list in the sidebar to rename or recolour it\n"
        "• Ctrl+Z undoes your last completion or deletion"))

    quick = db.add_task("Try the quick-add magic", list_id=lid, due=today(),
                        priority=1)
    db.update_task(quick, notes=(
        "Type this in the box at the top and press Enter:\n"
        "   !1 call mum #family friday every week\n"
        "It becomes a priority-1 task, tagged family, due Friday, "
        "repeating weekly."))
    db.add_task("Press Ctrl+N to jump to quick-add", parent_id=quick)
    db.add_task("Press Ctrl+F to search anything", parent_id=quick)
    db.add_task("Press Ctrl+I for your weekly stats", parent_id=quick)

    db.add_task("Water the plants", list_id=lid, due=today(), repeat="daily",
                priority=3)
    done = db.add_task("Open MintDo for the first time", list_id=lid,
                       status="done", completed_at=now_ts())
    db.set_tags(done, ["welcome"])
    db.set_setting("seeded", "1")


class Database:
    """Thin, synchronous wrapper around the MintDo SQLite database."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        # WAL + NORMAL keeps the UI snappy even on spinning disks: commits
        # skip the expensive fsync (only checkpoints do a full sync).
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 3000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ #
    # settings
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)))
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # lists
    # ------------------------------------------------------------------ #
    def lists(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM lists ORDER BY position, id").fetchall()
        return [dict(r) for r in rows]

    def get_list(self, list_id) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()
        return dict(row) if row else None

    def add_list(self, name: str, color: str = "#87CF3E") -> int:
        pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM lists").fetchone()[0]
        cur = self.conn.execute(
            "INSERT INTO lists(name, color, position, created_at) "
            "VALUES(?, ?, ?, ?)",
            (name.strip(), color, pos, now_ts()))
        self.conn.commit()
        return cur.lastrowid

    def rename_list(self, list_id: int, name: str) -> None:
        self.conn.execute("UPDATE lists SET name = ? WHERE id = ?",
                          (name.strip(), list_id))
        self.conn.commit()

    def set_list_color(self, list_id: int, color: str) -> None:
        self.conn.execute("UPDATE lists SET color = ? WHERE id = ?",
                          (color, list_id))
        self.conn.commit()

    def delete_list(self, list_id: int) -> None:
        # Tasks fall back to the Inbox (list_id NULL via FK rule).
        self.conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # tags
    # ------------------------------------------------------------------ #
    def all_tags(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT tag FROM task_tags ORDER BY tag").fetchall()
        return [r["tag"] for r in rows]

    def tags_of(self, task_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT tag FROM task_tags WHERE task_id = ? ORDER BY tag",
            (task_id,)).fetchall()
        return [r["tag"] for r in rows]

    def set_tags(self, task_id: int, tags: list[str]) -> None:
        clean = []
        for t in tags:
            t = str(t).strip().lstrip("#").lower()
            if t and t not in clean:
                clean.append(t)
        self.conn.execute("DELETE FROM task_tags WHERE task_id = ?",
                          (task_id,))
        for t in clean:
            self.conn.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)",
                              (t,))
            self.conn.execute(
                "INSERT OR IGNORE INTO task_tags(task_id, tag) VALUES(?, ?)",
                (task_id, t))
        self.conn.commit()

    def _tags_map(self) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for r in self.conn.execute(
                "SELECT task_id, tag FROM task_tags ORDER BY tag"):
            out.setdefault(r["task_id"], []).append(r["tag"])
        return out

    # ------------------------------------------------------------------ #
    # tasks - CRUD
    # ------------------------------------------------------------------ #
    def add_task(self, title: str, *, task_id=None, list_id=None,
                 parent_id=None, due=None, priority=0, notes="", repeat="",
                 starred=False, position=None, created_at=None, status="open",
                 completed_at=None) -> int:
        if position is None:
            position = self.conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM tasks").fetchone()[0]
        cur = self.conn.execute(
            "INSERT INTO tasks(id, list_id, parent_id, title, notes, due, "
            "priority, starred, repeat, status, position, created_at, "
            "completed_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, list_id, parent_id, (title or "").strip() or "Untitled",
             notes, due, int(priority), 1 if starred else 0, repeat, status,
             position, created_at or now_ts(), completed_at))
        self.conn.commit()
        return cur.lastrowid

    def get_task(self, tid) -> dict | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?",
                                (tid,)).fetchone()
        if not row:
            return None
        task = dict(row)
        task["tags"] = self.tags_of(tid)
        return task

    def update_task(self, tid, **fields) -> None:
        cols, vals = [], []
        for key in TASK_FIELDS & set(fields):
            val = fields[key]
            if key == "starred":
                val = 1 if val else 0
            elif key == "priority":
                val = max(0, min(4, int(val)))
            cols.append(f"{key} = ?")
            vals.append(val)
        if not cols:
            return
        vals.append(tid)
        self.conn.execute(f"UPDATE tasks SET {', '.join(cols)} WHERE id = ?",
                          vals)
        self.conn.commit()

    def delete_task(self, tid) -> dict | None:
        """Delete a task (and its subtasks); returns a snapshot for undo."""
        snap = self.snapshot_task(tid)
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
        self.conn.commit()
        return snap

    def snapshot_task(self, tid) -> dict | None:
        task = self.get_task(tid)
        if not task:
            return None
        subs = []
        for r in self.conn.execute(
                "SELECT * FROM tasks WHERE parent_id = ? ORDER BY id", (tid,)):
            sub = dict(r)
            sub["tags"] = self.tags_of(sub["id"])
            subs.append(sub)
        return {"task": task, "subtasks": subs}

    def restore_task(self, snap) -> int | None:
        """Re-insert a previously deleted task snapshot (undo support)."""
        if not snap or not snap.get("task"):
            return None
        t = snap["task"]
        cols = ("id, list_id, parent_id, title, notes, due, priority, starred,"
                " repeat, status, position, created_at, completed_at")
        ph = ", ".join("?" * 13)
        self.conn.execute(
            f"INSERT OR REPLACE INTO tasks({cols}) VALUES({ph})",
            (t["id"], t["list_id"], t["parent_id"], t["title"], t["notes"],
             t["due"], t["priority"], t["starred"], t["repeat"], t["status"],
             t["position"], t["created_at"], t["completed_at"]))
        for s in snap.get("subtasks", []):
            self.conn.execute(
                f"INSERT OR REPLACE INTO tasks({cols}) VALUES({ph})",
                (s["id"], s["list_id"], s["parent_id"], s["title"], s["notes"],
                 s["due"], s["priority"], s["starred"], s["repeat"],
                 s["status"], s["position"], s["created_at"],
                 s["completed_at"]))
        self.conn.commit()
        self.set_tags(t["id"], t.get("tags", []))
        for s in snap.get("subtasks", []):
            self.set_tags(s["id"], s.get("tags", []))
        return t["id"]

    # ------------------------------------------------------------------ #
    # tasks - queries
    # ------------------------------------------------------------------ #
    def _where(self, view, list_id):
        if view == "list":
            return ("t.parent_id IS NULL AND t.status = 'open' "
                    "AND t.list_id = ?"), [list_id]
        if view == "today":
            return ("t.parent_id IS NULL AND t.status = 'open' "
                    "AND t.due IS NOT NULL AND substr(t.due, 1, 10) <= ?"), [today()]
        if view == "upcoming":
            end = (date.today() + timedelta(days=7)).isoformat()
            return ("t.parent_id IS NULL AND t.status = 'open' "
                    "AND t.due IS NOT NULL AND substr(t.due, 1, 10) > ? "
                    "AND substr(t.due, 1, 10) <= ?"), [today(), end]
        if view == "starred":
            return ("t.parent_id IS NULL AND t.status = 'open' "
                    "AND t.starred = 1"), []
        if view == "inbox":
            return ("t.parent_id IS NULL AND t.status = 'open' "
                    "AND t.list_id IS NULL"), []
        if view == "completed":
            return "t.parent_id IS NULL AND t.status = 'done'", []
        return "t.parent_id IS NULL AND t.status = 'open'", []

    @staticmethod
    def _order(view, sort):
        prio = "CASE WHEN t.priority = 0 THEN 9 ELSE t.priority END"
        if sort == "due":
            return f"(t.due IS NULL), t.due, {prio}, t.title COLLATE NOCASE"
        if sort == "priority":
            return f"{prio}, (t.due IS NULL), t.due, t.title COLLATE NOCASE"
        if sort == "alpha":
            return "t.title COLLATE NOCASE"
        if sort == "manual":
            return "t.position, t.id"
        if sort == "created":
            return "t.created_at DESC"
        if view == "completed":
            return "t.completed_at DESC, t.title COLLATE NOCASE"
        if view in ("today", "upcoming"):
            return f"t.due, {prio}, t.title COLLATE NOCASE"
        if view == "list":
            return "t.position, t.id"
        return f"{prio}, (t.due IS NULL), t.due, t.title COLLATE NOCASE"

    def fetch_tasks(self, view="all", list_id=None, search="", sort="smart"):
        where, params = self._where(view, list_id)
        term = (search or "").strip()
        if term:
            like = f"%{term}%"
            tag_like = f"%{term.lstrip('#')}%"
            where += (" AND (t.title LIKE ? OR t.notes LIKE ? OR EXISTS ("
                      "SELECT 1 FROM task_tags x WHERE x.task_id = t.id "
                      "AND x.tag LIKE ?))")
            params = list(params) + [like, like, tag_like]
        order = self._order(view, sort)
        rows = [dict(r) for r in self.conn.execute(
            f"SELECT t.* FROM tasks t WHERE {where} ORDER BY {order}",
            params)]
        tmap = self._tags_map()
        for r in rows:
            r["tags"] = tmap.get(r["id"], [])
        return rows

    def fetch_subtasks(self, parent_id) -> list[dict]:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY id",
            (parent_id,))]
        tmap = self._tags_map()
        for r in rows:
            r["tags"] = tmap.get(r["id"], [])
        return rows

    def count_open(self, view="all", list_id=None) -> int:
        where, params = self._where(view, list_id)
        row = self.conn.execute(
            f"SELECT COUNT(*) AS c FROM tasks t WHERE {where}",
            params).fetchone()
        return row["c"]

    def subtask_progress(self) -> dict[int, tuple]:
        """{parent_id: (done_count, total)} for every parent task."""
        out: dict[int, tuple] = {}
        for r in self.conn.execute(
                "SELECT parent_id, COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done "
                "FROM tasks WHERE parent_id IS NOT NULL GROUP BY parent_id"):
            out[r["parent_id"]] = (r["done"] or 0, r["total"])
        return out

    # ------------------------------------------------------------------ #
    # completion + recurrence
    # ------------------------------------------------------------------ #
    def complete_task(self, tid) -> dict:
        """Mark done. If the task repeats, spawn the next occurrence.

        Returns {"new_id": <spawned task id or None>}.
        """
        task = self.get_task(tid)
        if not task or task["status"] == "done":
            return {"new_id": None}
        self.conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
            (now_ts(), tid))
        self.conn.commit()
        if not task["repeat"]:
            return {"new_id": None}
        new_id = self.add_task(
            task["title"], list_id=task["list_id"],
            due=advance_due(task["due"], task["repeat"]),
            priority=task["priority"], notes=task["notes"],
            repeat=task["repeat"], starred=bool(task["starred"]),
            position=task["position"])
        self.set_tags(new_id, task.get("tags", []))
        for sub in self.conn.execute(
                "SELECT * FROM tasks WHERE parent_id = ? ORDER BY id", (tid,)):
            sid = self.add_task(
                sub["title"], list_id=task["list_id"], parent_id=new_id,
                due=sub["due"], priority=sub["priority"], notes=sub["notes"])
            self.set_tags(sid, self.tags_of(sub["id"]))
        return {"new_id": new_id}

    def uncomplete_task(self, tid) -> None:
        self.conn.execute(
            "UPDATE tasks SET status = 'open', completed_at = NULL WHERE id = ?",
            (tid,))
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # stats
    # ------------------------------------------------------------------ #
    def stats(self) -> dict:
        t = today()
        week_start = (date.today() - timedelta(days=6)).isoformat()
        cur = self.conn
        done_today = cur.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE status = 'done' "
            "AND substr(completed_at, 1, 10) = ?", (t,)).fetchone()["c"]
        done_week = cur.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE status = 'done' "
            "AND completed_at >= ?", (week_start,)).fetchone()["c"]
        open_count = cur.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE status = 'open' "
            "AND parent_id IS NULL").fetchone()["c"]

        counts = {r["d"]: r["c"] for r in cur.execute(
            "SELECT substr(completed_at, 1, 10) AS d, COUNT(*) AS c "
            "FROM tasks WHERE status = 'done' AND completed_at >= ? "
            "GROUP BY d", (week_start,))}
        series = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            series.append((d, counts.get(d, 0)))

        days = {r["d"] for r in cur.execute(
            "SELECT DISTINCT substr(completed_at, 1, 10) AS d "
            "FROM tasks WHERE status = 'done' AND completed_at IS NOT NULL")}
        streak, cursor = 0, date.today()
        if cursor.isoformat() not in days:
            cursor -= timedelta(days=1)
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)

        return {"done_today": done_today, "done_week": done_week,
                "open": open_count, "streak": streak, "series": series}

    # ------------------------------------------------------------------ #
    # backup
    # ------------------------------------------------------------------ #
    def export_json(self) -> str:
        def rows(q):
            return [dict(r) for r in self.conn.execute(q)]
        data = {
            "app": "mintdo",
            "version": 1,
            "exported_at": now_ts(),
            "lists": rows("SELECT * FROM lists ORDER BY id"),
            "tasks": rows("SELECT * FROM tasks ORDER BY id"),
            "task_tags": rows("SELECT * FROM task_tags ORDER BY task_id, tag"),
            "settings": rows("SELECT * FROM settings ORDER BY key"),
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def import_json(self, text: str) -> int:
        """Replace all data with a backup. Returns number of tasks imported."""
        data = json.loads(text)
        if data.get("app") != "mintdo":
            raise ValueError("This file is not a MintDo backup")
        tasks = data.get("tasks", [])
        cur = self.conn
        cur.execute("DELETE FROM task_tags")
        cur.execute("DELETE FROM tasks")
        cur.execute("DELETE FROM lists")
        cur.execute("DELETE FROM tags")
        cur.execute("DELETE FROM settings")
        # Lists first: tasks reference them.
        for l in data.get("lists", []):
            cur.execute(
                "INSERT INTO lists(id, name, color, position, created_at) "
                "VALUES(?, ?, ?, ?, ?)",
                [l.get(k) for k in ("id", "name", "color", "position",
                                    "created_at")])
        tcols = ("id, list_id, parent_id, title, notes, due, priority, starred,"
                 " repeat, status, position, created_at, completed_at")
        ph = ", ".join("?" * 13)
        for t in tasks:
            cur.execute(
                f"INSERT INTO tasks({tcols}) VALUES({ph})",
                [t.get(k) for k in ("id", "list_id", "parent_id", "title",
                                    "notes", "due", "priority", "starred",
                                    "repeat", "status", "position",
                                    "created_at", "completed_at")])
        for tt in data.get("task_tags", []):
            cur.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)",
                        (tt.get("tag"),))
            cur.execute(
                "INSERT OR REPLACE INTO task_tags(task_id, tag) VALUES(?, ?)",
                (tt.get("task_id"), tt.get("tag")))
        for s in data.get("settings", []):
            cur.execute("INSERT OR REPLACE INTO settings(key, value) "
                        "VALUES(?, ?)", (s.get("key"), s.get("value")))
        cur.commit()
        return len(tasks)




"""Unit tests for the MintDo database layer and quick-add parser."""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mintdo import db as dbmod
from mintdo import quickadd


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.db = dbmod.Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_settings_roundtrip(self):
        self.assertIsNone(self.db.get_setting("theme"))
        self.db.set_setting("theme", "dark")
        self.assertEqual(self.db.get_setting("theme"), "dark")
        self.db.set_setting("theme", "light")
        self.assertEqual(self.db.get_setting("theme"), "light")

    def test_lists_crud_and_inbox_fallback(self):
        lid = self.db.add_list("Groceries", "#5294E2")
        self.assertEqual(self.db.get_list(lid)["name"], "Groceries")
        tid = self.db.add_task("Milk", list_id=lid)
        self.db.rename_list(lid, "Shopping")
        self.assertEqual(self.db.get_list(lid)["name"], "Shopping")
        self.db.delete_list(lid)
        self.assertIsNone(self.db.get_list(lid))
        task = self.db.get_task(tid)
        self.assertIsNone(task["list_id"])  # falls back to Inbox

    def test_smart_views(self):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        in_three = (date.today() + timedelta(days=3)).isoformat()
        in_ten = (date.today() + timedelta(days=10)).isoformat()
        self.db.add_task("overdue", due=yesterday)
        self.db.add_task("due today", due=today)
        self.db.add_task("soon", due=in_three)
        self.db.add_task("later", due=in_ten)
        self.db.add_task("no date")

        titles = [t["title"] for t in self.db.fetch_tasks("today")]
        self.assertEqual(sorted(titles), ["due today", "overdue"])
        titles = [t["title"] for t in self.db.fetch_tasks("upcoming")]
        self.assertEqual(titles, ["soon"])
        self.assertEqual(self.db.count_open("all"), 5)
        self.assertEqual(self.db.count_open("inbox"), 5)

    def test_search_and_tags(self):
        a = self.db.add_task("Buy flowers")
        self.db.set_tags(a, ["Gift", "garden"])
        self.db.add_task("Walk the dog")
        hits = self.db.fetch_tasks("all", search="flowers")
        self.assertEqual([t["title"] for t in hits], ["Buy flowers"])
        hits = self.db.fetch_tasks("all", search="#gift")
        self.assertEqual([t["id"] for t in hits], [a])
        self.assertEqual(self.db.tags_of(a), ["garden", "gift"])
        self.assertEqual(self.db.all_tags(), ["garden", "gift"])
        self.db.set_tags(a, ["gift"])
        self.assertEqual(self.db.tags_of(a), ["gift"])

    def test_update_and_starred_view(self):
        tid = self.db.add_task("Draft plan", priority=2)
        self.db.update_task(tid, priority=1, starred=True, notes="details")
        task = self.db.get_task(tid)
        self.assertEqual(task["priority"], 1)
        self.assertEqual(task["starred"], 1)
        self.assertEqual(task["notes"], "details")
        self.assertEqual([t["id"] for t in self.db.fetch_tasks("starred")], [tid])
        self.db.update_task(tid, priority=99)  # clamped
        self.assertEqual(self.db.get_task(tid)["priority"], 4)

    def test_subtasks(self):
        tid = self.db.add_task("Plan party")
        s1 = self.db.add_task("Book cake", parent_id=tid)
        s2 = self.db.add_task("Send invites", parent_id=tid)
        subs = self.db.fetch_subtasks(tid)
        self.assertEqual([s["id"] for s in subs], [s1, s2])
        # Subtasks never show up as top-level rows.
        self.assertEqual([t["id"] for t in self.db.fetch_tasks("all")], [tid])
        self.db.update_task(s1, status="done")
        self.assertEqual(self.db.fetch_subtasks(tid)[0]["status"], "done")
        # Deleting the parent cascades.
        self.db.delete_task(tid)
        self.assertIsNone(self.db.get_task(s1))
        self.assertIsNone(self.db.get_task(s2))

    def test_completion_and_undo(self):
        tid = self.db.add_task("Water plants")
        info = self.db.complete_task(tid)
        self.assertIsNone(info["new_id"])
        self.assertEqual(self.db.get_task(tid)["status"], "done")
        self.assertEqual(self.db.count_open("all"), 0)
        self.assertEqual(len(self.db.fetch_tasks("completed")), 1)
        self.db.uncomplete_task(tid)
        self.assertEqual(self.db.get_task(tid)["status"], "open")
        # completing twice returns no new task
        self.db.complete_task(tid)
        self.assertIsNone(self.db.complete_task(tid)["new_id"])

    def test_recurring_task_respawns(self):
        today = date.today().isoformat()
        tid = self.db.add_task("Take vitamins", due=today, repeat="daily",
                               priority=3)
        info = self.db.complete_task(tid)
        self.assertIsNotNone(info["new_id"])
        old = self.db.get_task(tid)
        new = self.db.get_task(info["new_id"])
        self.assertEqual(old["status"], "done")
        self.assertEqual(new["status"], "open")
        self.assertEqual(new["repeat"], "daily")
        self.assertGreater(new["due"], today)
        self.assertEqual(new["priority"], 3)
        # weekly advance
        nxt = dbmod.advance_due(today, "weekly")
        self.assertEqual(nxt, (date.today() + timedelta(days=7)).isoformat())
        # weekdays skip the weekend
        sat = date(2026, 10, 17)  # a Saturday
        self.assertEqual(dbmod.advance_due(sat.isoformat(), "weekdays"),
                         "2026-10-19")
        # monthly clamps to the shortest month, and always lands in the future
        self.assertEqual(dbmod.advance_due("2027-01-31", "monthly"),
                         "2027-02-28")
        self.assertGreater(dbmod.advance_due("2026-01-31", "monthly"),
                           date.today().isoformat())

    def test_delete_and_restore(self):
        tid = self.db.add_task("Important", priority=1, due="2026-12-01")
        self.db.set_tags(tid, ["urgent"])
        self.db.add_task("Step one", parent_id=tid)
        snap = self.db.delete_task(tid)
        self.assertIsNone(self.db.get_task(tid))
        self.assertEqual(self.db.count_open("all"), 0)
        restored = self.db.restore_task(snap)
        self.assertEqual(restored, tid)
        task = self.db.get_task(tid)
        self.assertEqual(task["title"], "Important")
        self.assertEqual(task["priority"], 1)
        self.assertEqual(task["tags"], ["urgent"])
        self.assertEqual(len(self.db.fetch_subtasks(tid)), 1)
        self.assertEqual(self.db.fetch_subtasks(tid)[0]["title"], "Step one")

    def test_stats(self):
        for i in range(3):
            tid = self.db.add_task(f"done {i}")
            self.db.complete_task(tid)
        self.db.add_task("still open")
        s = self.db.stats()
        self.assertEqual(s["done_today"], 3)
        self.assertEqual(s["done_week"], 3)
        self.assertEqual(s["open"], 1)
        self.assertGreaterEqual(s["streak"], 1)
        self.assertEqual(len(s["series"]), 7)
        self.assertEqual(s["series"][-1][1], 3)  # today's bar

    def test_export_import_roundtrip(self):
        lid = self.db.add_list("Trips", "#E8A33D")
        tid = self.db.add_task("Book hotel", list_id=lid, due="2026-11-20",
                               priority=2)
        self.db.set_tags(tid, ["travel"])
        blob = self.db.export_json()
        self.db.add_task("temporary")
        count = self.db.import_json(blob)
        self.assertEqual(count, 1)
        self.assertEqual(self.db.count_open("all"), 1)
        task = self.db.fetch_tasks("list", list_id=lid)[0]
        self.assertEqual(task["title"], "Book hotel")
        self.assertEqual(task["tags"], ["travel"])
        self.assertEqual(self.db.get_list(lid)["color"], "#E8A33D")
        with self.assertRaises(ValueError):
            self.db.import_json('{"app": "other"}')


class QuickAddTestCase(unittest.TestCase):
    def test_plain_title(self):
        r = quickadd.parse("Buy groceries")
        self.assertEqual(r["title"], "Buy groceries")
        self.assertEqual(r["priority"], 0)
        self.assertEqual(r["tags"], [])
        self.assertIsNone(r["due"])
        self.assertEqual(r["repeat"], "")

    def test_full_line(self):
        r = quickadd.parse("!1 buy flowers #gift tomorrow every week")
        self.assertEqual(r["title"], "buy flowers")
        self.assertEqual(r["priority"], 1)
        self.assertEqual(r["tags"], ["gift"])
        self.assertEqual(r["due"], (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(r["repeat"], "weekly")

    def test_tags_and_weekday(self):
        r = quickadd.parse("Movie night #fun friday")
        self.assertEqual(r["title"], "Movie night")
        self.assertEqual(r["tags"], ["fun"])
        due = date.fromisoformat(r["due"])
        self.assertEqual(due.weekday(), 4)  # Friday
        self.assertGreater(due, date.today())

    def test_today_and_iso_date(self):
        self.assertEqual(quickadd.parse("Stretch today")["due"],
                         date.today().isoformat())
        self.assertEqual(quickadd.parse("Tax stuff 2026-12-15")["due"],
                         "2026-12-15")
        # Past ISO dates are kept as the title, not parsed as due dates.
        self.assertIsNone(quickadd.parse("Old thing 2020-01-01")["due"])

    def test_priority_and_repeat(self):
        r = quickadd.parse("Water flowers every day !3 #home")
        self.assertEqual(r["priority"], 3)
        self.assertEqual(r["repeat"], "daily")
        self.assertEqual(r["title"], "Water flowers")
        self.assertEqual(r["tags"], ["home"])


if __name__ == "__main__":
    unittest.main()



"""A single task row: checkbox, title, metadata chips and star."""

from __future__ import annotations

from datetime import date, timedelta

import gi
gi.require_version("Pango", "1.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _set_class(context, name, enabled):
    """GTK3 has no toggle_class(); add/remove manually."""
    if enabled:
        context.add_class(name)
    else:
        context.remove_class(name)


def format_due(due: str, status_class: list) -> str:
    """Human due label; appends CSS classes to *status_class*."""
    d = date.fromisoformat(due[:10])
    today = date.today()
    if d < today:
        status_class.append("overdue")
        return f"⚠ {d.day} {MONTHS[d.month - 1]}"
    if d == today:
        status_class.append("due-today")
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    if (d - today).days < 7:
        return d.strftime("%A")
    return f"{d.day} {MONTHS[d.month - 1]}"


class TaskRow(Gtk.ListBoxRow):
    def __init__(self, task, *, show_list=False, list_label=None,
                 on_toggle=None, on_star=None):
        super().__init__()
        self.task = task
        self.show_list = show_list
        self.list_label = list_label
        self.on_toggle = on_toggle
        self.on_star = on_star
        self._loading = False
        self.get_style_context().add_class("task")

        self.check = Gtk.CheckButton()
        self.check.set_valign(Gtk.Align.CENTER)
        self.check.connect("toggled", self._toggled)

        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                               hexpand=True, selectable=False)
        self.title.get_style_context().add_class("task-title")

        self.meta = Gtk.FlowBox()
        self.meta.set_selection_mode(Gtk.SelectionMode.NONE)
        self.meta.set_max_children_per_line(8)
        self.meta.set_homogeneous(False)
        self.meta.set_row_spacing(3)
        self.meta.set_column_spacing(4)
        self.meta.set_valign(Gtk.Align.CENTER)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text_box.pack_start(self.title, False, False, 0)
        text_box.pack_start(self.meta, False, False, 0)

        self.star = Gtk.Button()
        self.star.get_style_context().add_class("flat")
        self.star.get_style_context().add_class("star")
        self.star.set_relief(Gtk.ReliefStyle.NONE)
        self.star.set_valign(Gtk.Align.CENTER)
        self.star.connect("clicked", self._starred)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.pack_start(self.check, False, False, 0)
        box.pack_start(text_box, True, True, 0)
        box.pack_start(self.star, False, False, 0)
        self.add(box)
        self.update(task)

    # ------------------------------------------------------------------ #
    def _chip(self, text, classes):
        label = Gtk.Label(label=text)
        ctx = label.get_style_context()
        ctx.add_class("meta-chip")
        for cls in classes:
            ctx.add_class(cls)
        return label

    def update(self, task):
        """Re-render row contents from a task dict."""
        self._loading = True
        try:
            done = task["status"] == "done"
            self.check.set_active(done)
            self.check.set_tooltip_text(
                "Mark as not done" if done else "Mark as done")

            escaped = GLib.markup_escape_text(task["title"])
            self.title.set_markup(f"<s>{escaped}</s>" if done else escaped)
            ctx = self.title.get_style_context()
            ctx.add_class("task-title")
            _set_class(ctx, "done", done)

            for child in self.meta.get_children():
                self.meta.remove(child)

            if task.get("due"):
                classes = []
                self.meta.add(self._chip(format_due(task["due"], classes),
                                         classes))

            if task.get("priority"):
                prio = task["priority"]
                self.meta.add(self._chip(f"P{prio}", [f"p{prio}"]))

            if task.get("repeat"):
                unit = {"daily": "day", "weekly": "week",
                        "monthly": "month", "weekdays": "weekday"}[
                            task["repeat"]]
                self.meta.add(self._chip(f"↻ every {unit}", []))

            if self.show_list and self.list_label:
                self.meta.add(self._chip(self.list_label, []))

            tags = task.get("tags", [])
            for tag in tags[:3]:
                self.meta.add(self._chip(f"#{tag}", ["tag"]))
            if len(tags) > 3:
                self.meta.add(self._chip(f"+{len(tags) - 3}", ["tag"]))

            if task.get("notes"):
                self.meta.add(self._chip("✎", []))

            if task.get("_sub_progress"):
                done_n, total = task["_sub_progress"]
                self.meta.add(self._chip(f"☑ {done_n}/{total}", []))

            starred = bool(task.get("starred"))
            self.star.set_label("★" if starred else "☆")
            _set_class(self.star.get_style_context(), "on", starred)
            self.star.set_tooltip_text("Star this task")
        finally:
            self._loading = False
        self.task = task

    # ------------------------------------------------------------------ #
    def _toggled(self, _btn):
        if self._loading:
            return
        if self.on_toggle:
            self.on_toggle(self.task["id"], self.check.get_active())

    def _starred(self, _btn):
        if self._loading:
            return
        if self.on_star:
            self.on_star(self.task["id"], not self.task.get("starred"))


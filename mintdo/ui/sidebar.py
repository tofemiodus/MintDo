"""Left navigation pane: smart views, custom lists and live counts."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mintdo.db import Database

# (key, icon, human title)
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


class Sidebar(Gtk.Box):
    """Navigation sidebar. Emits selection through the given callback."""

    def __init__(self, db: Database, on_select, on_new_list, on_edit_list,
                 on_delete_list):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.on_select = on_select
        self.on_new_list = on_new_list
        self.on_edit_list = on_edit_list
        self.on_delete_list = on_delete_list
        self.get_style_context().add_class("sidebar")
        self.set_size_request(205, -1)
        self._rows = {}
        self._selection = ("view", "today")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.NONE)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(False)
        self.listbox.connect("row-selected", self._row_selected)
        self.listbox.connect("button-press-event", self._button_press)
        scrolled.add(self.listbox)
        self.pack_start(scrolled, True, True, 0)

        footer = Gtk.Label(xalign=0)
        footer.get_style_context().add_class("count")
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_top(8)
        footer.set_margin_bottom(8)
        self.footer = footer
        self.pack_start(footer, False, False, 0)
        self.refresh()

    # ------------------------------------------------------------------ #
    def _make_row(self, kind, key, icon, title, count=None, color=None):
        row = Gtk.ListBoxRow()
        row.kind, row.key = kind, key
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if color:
            dot = Gtk.Label(label="●")
            rgba = Gdk.RGBA()
            rgba.parse(color)
            dot.override_color(Gtk.StateFlags.NORMAL, rgba)
            box.pack_start(dot, False, False, 0)
        elif icon:
            box.pack_start(Gtk.Label(label=icon), False, False, 0)
        label = Gtk.Label(label=title, xalign=0, hexpand=True,
                          ellipsize=3)  # Pango.EllipsizeMode.END
        box.pack_start(label, True, True, 0)
        if count is not None:
            count_label = Gtk.Label(label=str(count) if count else "")
            count_label.get_style_context().add_class("count")
            box.pack_start(count_label, False, False, 0)
        row.add(box)
        return row

    @staticmethod
    def _header_row(text):
        row = Gtk.ListBoxRow()
        row.kind, row.key = "header", text
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_sensitive(False)
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("section-title")
        row.add(label)
        return row

    def refresh(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        self._rows.clear()

        self.listbox.add(self._header_row("VIEWS"))
        for key, icon, title in SMART_VIEWS:
            count = self.db.count_open(key)
            row = self._make_row("view", key, icon, title, count)
            self._rows[("view", key)] = row
            self.listbox.add(row)

        self.listbox.add(self._header_row("LISTS"))

        for lst in self.db.lists():
            count = self.db.count_open("list", list_id=lst["id"])
            row = self._make_row("list", lst["id"], None, lst["name"],
                                 count, lst["color"])
            self._rows[("list", lst["id"])] = row
            self.listbox.add(row)

        add_row = Gtk.ListBoxRow()
        add_row.kind, add_row.key = "new-list", None
        add_row.set_selectable(False)
        box = Gtk.Box(spacing=8)
        box.pack_start(Gtk.Label(label="＋", xalign=0), False, False, 0)
        box.pack_start(Gtk.Label(label="New list", xalign=0), False, False, 0)
        add_row.add(box)
        self._rows[("new-list", None)] = add_row
        self.listbox.add(add_row)

        # GTK3 does not auto-show children added to a visible container.
        self.listbox.show_all()

        stats = self.db.stats()
        streak = f" · 🔥 {stats['streak']} day streak" if stats["streak"] else ""
        self.footer.set_text(f"✓ {stats['done_today']} done today{streak}")

        kind, key = self._selection
        row = self._rows.get((kind, key))
        if row is not None and row.get_selectable():
            self.listbox.select_row(row)

    def select(self, kind, key):
        self._selection = (kind, key)
        row = self._rows.get((kind, key))
        if row is not None and row.get_selectable():
            self.listbox.select_row(row)

    # ------------------------------------------------------------------ #
    def _row_selected(self, _box, row):
        if row is None or row.kind == "header":
            return
        if row.kind == "new-list":
            self.on_new_list()
            GLib.idle_add(self._restore_selection)
            return
        if (row.kind, row.key) == self._selection:
            return  # programmatic re-select during refresh
        self._selection = (row.kind, row.key)
        self.on_select(row.kind, row.key)

    def _restore_selection(self):
        kind, key = self._selection
        row = self._rows.get((kind, key))
        if row is not None and row.get_selectable():
            self.listbox.select_row(row)
        return False

    def _button_press(self, _box, event):
        if event.button != 3:
            return False
        row = self.listbox.get_row_at_y(int(event.y))
        if row is None or row.kind != "list":
            return False
        menu = Gtk.Menu()
        edit = Gtk.MenuItem(label="Rename / recolor…")
        edit.connect("activate", lambda *_: self.on_edit_list(row.key))
        delete = Gtk.MenuItem(label="Delete list")
        delete.connect("activate", lambda *_: self.on_delete_list(row.key))
        menu.append(edit)
        menu.append(delete)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True


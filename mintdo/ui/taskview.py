"""Central pane: view header, quick-add entry, search and the task list."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from mintdo.ui.taskrow import TaskRow

SORTS = (
    ("smart", "Recommended"),
    ("due", "Due date"),
    ("priority", "Priority"),
    ("alpha", "Name (A–Z)"),
    ("created", "Newest first"),
    ("manual", "Manual order"),
)


class TaskView(Gtk.Box):
    def __init__(self, callbacks: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.cb = callbacks
        self.sort = "smart"
        self.show_list = False

        # --- header: view title + sort menu --- #
        self.title_label = Gtk.Label(xalign=0)
        self.title_label.get_style_context().add_class("view-title")
        self.sub_label = Gtk.Label(xalign=0)
        self.sub_label.get_style_context().add_class("view-sub")

        self.sort_button = Gtk.MenuButton(label="Sort ▾")
        self.sort_button.set_relief(Gtk.ReliefStyle.NONE)
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        self._sort_group = []
        for value, label in SORTS:
            btn = Gtk.RadioButton.new_with_label_from_widget(
                self._sort_group[0] if self._sort_group else None, label)
            btn.connect("toggled", self._sort_toggled, value)
            self._sort_group.append(btn)
            box.pack_start(btn, False, False, 0)
        pop.add(box)
        box.show_all()          # show content only — never the popover
        self.sort_button.set_popover(pop)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        titles.pack_start(self.title_label, False, False, 0)
        titles.pack_start(self.sub_label, False, False, 0)
        head.pack_start(titles, True, True, 0)
        head.pack_start(self.sort_button, False, False, 0)
        head.set_margin_start(12)
        head.set_margin_end(8)
        self.pack_start(head, False, False, 0)

        # --- quick add --- #
        self.entry = Gtk.Entry()
        self.entry.get_style_context().add_class("quick-add")
        self.entry.set_placeholder_text(
            "Add a task…  e.g.  !1 buy flowers #gift tomorrow")
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                           "list-add-symbolic")
        self.entry.connect("activate", self._quick_add)
        self.pack_start(self.entry, False, False, 0)

        hint = Gtk.Label(xalign=0, label=(
            "!1–!4 priority · #tag · today/tomorrow/weekday · every day/week"))
        hint.get_style_context().add_class("quick-hint")
        self.pack_start(hint, False, False, 0)

        # --- search bar --- #
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search tasks…")
        self.search_entry.connect("search-changed",
                                  lambda e: self.cb["search"](e.get_text()))
        self.search_bar = Gtk.SearchBar()
        self.search_bar.add(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.pack_start(self.search_bar, False, False, 0)

        # --- list / empty stack --- #
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._row_selected)
        self.listbox.connect("row-activated", self._row_activated)
        self.listbox.connect("key-press-event", self._key_press)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.NONE)
        scrolled.add(self.listbox)

        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_halign(Gtk.Align.CENTER)
        self.empty_big = Gtk.Label(label="🎉")
        self.empty_big.set_name("")  # keep default font
        self.empty_title = Gtk.Label()
        self.empty_title.get_style_context().add_class("empty-title")
        self.empty_sub = Gtk.Label()
        self.empty_sub.get_style_context().add_class("empty-sub")
        self.empty_sub.set_line_wrap(True)
        self.empty_sub.set_max_width_chars(40)
        self.empty_sub.set_justify(Gtk.Justification.CENTER)
        empty_box.pack_start(self.empty_big, False, False, 0)
        empty_box.pack_start(self.empty_title, False, False, 0)
        empty_box.pack_start(self.empty_sub, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.add_named(scrolled, "list")
        self.stack.add_named(empty_box, "empty")
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pack_start(self.stack, True, True, 0)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def set_header(self, title, subtitle):
        self.title_label.set_text(title)
        self.sub_label.set_text(subtitle)

    def set_tasks(self, tasks, empty=None, show_list=False, list_names=None):
        """(Re)render *tasks*; *empty* is (icon, title, subtitle)."""
        self.show_list = show_list
        list_names = list_names or {}
        previous = self.selected_task_id()
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for task in tasks:
            row = TaskRow(
                task, show_list=show_list,
                list_label=list_names.get(task.get("list_id")),
                on_toggle=self.cb["toggle"], on_star=self.cb["star"])
            self.listbox.add(row)
            row.show_all()   # GTK3 does not auto-show added children

        if tasks:
            self.stack.set_visible_child_name("list")
            if previous is not None:
                self.select_task(previous)
        else:
            icon, big, small = empty or ("✨", "Nothing here", "")
            self.empty_big.set_text(icon)
            self.empty_title.set_text(big)
            self.empty_sub.set_text(small)
            self.stack.set_visible_child_name("empty")

    def selected_task_id(self):
        row = self.listbox.get_selected_row()
        if isinstance(row, TaskRow):
            return row.task["id"]
        return None

    def select_task(self, task_id):
        for row in self.listbox.get_children():
            if isinstance(row, TaskRow) and row.task["id"] == task_id:
                self.listbox.select_row(row)
                return True
        return False

    def focus_quick_add(self):
        self.entry.grab_focus()

    def set_search_visible(self, visible):
        self.search_bar.set_search_mode(visible)
        if visible:
            self.search_entry.grab_focus()

    def toggle_search(self):
        self.set_search_visible(not self.search_bar.get_search_mode())

    def clear_search(self):
        self.search_entry.set_text("")

    # ------------------------------------------------------------------ #
    # internal handlers
    # ------------------------------------------------------------------ #
    def _quick_add(self, entry):
        text = entry.get_text().strip()
        if not text:
            return
        entry.set_text("")
        self.cb["quick_add"](text)

    def _sort_toggled(self, button, value):
        if button.get_active():
            self.sort = value
            self.cb["sort"](value)

    def _row_selected(self, _box, row):
        if isinstance(row, TaskRow):
            self.cb["select"](row.task["id"])

    def _row_activated(self, _box, row):
        if isinstance(row, TaskRow):
            self.cb["activate"](row.task["id"])

    def _key_press(self, _box, event):
        if event.keyval == Gdk.KEY_Delete:
            task_id = self.selected_task_id()
            if task_id is not None:
                self.cb["delete"](task_id)
                return True
        if event.keyval in (Gdk.KEY_space, Gdk.KEY_KP_Space):
            # Space toggles the checkbox when the row itself has focus.
            row = self.listbox.get_selected_row()
            top = self.get_toplevel()
            focused = top.get_focus() if isinstance(top, Gtk.Window) else None
            if isinstance(row, TaskRow) and not isinstance(
                    focused, (Gtk.Entry, Gtk.TextView)):
                row.check.set_active(not row.check.get_active())
                return True
        return False


"""Right-hand editor panel for the selected task."""

from __future__ import annotations

from datetime import date, timedelta

import gi
gi.require_version("Pango", "1.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from mintdo.db import Database, now_ts as db_now

REPEAT_LABELS = (
    ("", "Never"),
    ("daily", "Every day"),
    ("weekdays", "Every weekday"),
    ("weekly", "Every week"),
    ("monthly", "Every month"),
)


class DetailPanel(Gtk.Box):
    """Shows and edits every field of the currently selected task."""

    def __init__(self, db: Database, callbacks: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.cb = callbacks
        self.task_id = None
        self._loading = False
        self.get_style_context().add_class("detail")
        self.set_size_request(310, -1)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack.add_named(self._build_placeholder(), "placeholder")
        self.stack.add_named(self._build_editor(), "editor")
        self.stack.set_visible_child_name("placeholder")
        self.pack_start(self.stack, True, True, 0)

    # ------------------------------------------------------------------ #
    def _build_placeholder(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Label(label="👈")
        title = Gtk.Label(label="Select a task")
        title.get_style_context().add_class("empty-title")
        sub = Gtk.Label(label="Click a task on the left to edit\n"
                              "its details here.")
        sub.get_style_context().add_class("empty-sub")
        sub.set_justify(Gtk.Justification.CENTER)
        box.pack_start(icon, False, False, 0)
        box.pack_start(title, False, False, 0)
        box.pack_start(sub, False, False, 0)
        return box

    def _heading(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("heading")
        return label

    def _build_editor(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_margin_start(14)
        inner.set_margin_end(14)
        inner.set_margin_top(8)
        inner.set_margin_bottom(8)

        # top buttons ------------------------------------------------ #
        self.done_btn = Gtk.Button(label="✓ Done")
        self.done_btn.connect("clicked", lambda *_: self._toggle_done())
        self.star_btn = Gtk.Button(label="☆")
        self.star_btn.connect("clicked", lambda *_: self._toggle_star())
        self.del_btn = Gtk.Button(label="Delete")
        self.del_btn.get_style_context().add_class("destructive-action")
        self.del_btn.connect("clicked", lambda *_: self._delete())
        top = Gtk.Box(spacing=6)
        top.pack_start(self.done_btn, False, False, 0)
        top.pack_start(self.star_btn, False, False, 0)
        top.pack_end(self.del_btn, False, False, 0)
        inner.pack_start(top, False, False, 0)

        # title ------------------------------------------------------ #
        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Task title")
        self.title_entry.connect("activate", self._title_committed)
        self.title_entry.connect("focus-out-event", self._title_focus_out)
        inner.pack_start(self.title_entry, False, False, 0)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.get_style_context().add_class("muted")
        inner.pack_start(self.status_label, False, False, 0)

        # due -------------------------------------------------------- #
        inner.pack_start(self._heading("DUE DATE"), False, False, 0)
        self.due_btn = Gtk.MenuButton(label="📅  No date")
        self.due_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.due_btn.set_halign(Gtk.Align.START)
        due_pop = Gtk.Popover()
        self.due_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.due_box.set_margin_top(8)
        self.due_box.set_margin_bottom(8)
        self.due_box.set_margin_start(8)
        self.due_box.set_margin_end(8)
        quick = Gtk.Box(spacing=4)
        for label, days in (("Today", 0), ("Tomorrow", 1), ("Next week", 7)):
            b = Gtk.Button(label=label)
            b.connect("clicked", self._due_quick, days)
            quick.pack_start(b, True, True, 0)
        clear = Gtk.Button(label="Clear")
        clear.connect("clicked", lambda *_: self._set_due(None))
        quick.pack_start(clear, True, True, 0)
        self.calendar = Gtk.Calendar()
        self.calendar.connect("day-selected", self._cal_selected)
        self.due_box.pack_start(quick, False, False, 0)
        self.due_box.pack_start(self.calendar, False, False, 0)
        due_pop.add(self.due_box)
        self.due_box.show_all()  # show content only — never the popover
        self.due_btn.set_popover(due_pop)
        inner.pack_start(self.due_btn, False, False, 0)

        # priority --------------------------------------------------- #
        inner.pack_start(self._heading("PRIORITY"), False, False, 0)
        self.prio_buttons = []
        prio_box = Gtk.Box(spacing=0)
        prio_box.get_style_context().add_class("linked")
        prio_box.get_style_context().add_class("prio-group")
        group = None
        for label in ("None", "P1", "P2", "P3", "P4"):
            b = Gtk.RadioButton.new_with_label_from_widget(group, label)
            group = b
            b.connect("toggled", self._prio_toggled, label)
            self.prio_buttons.append(b)
            prio_box.pack_start(b, True, True, 0)
        inner.pack_start(prio_box, False, False, 0)

        # repeat + list ---------------------------------------------- #
        inner.pack_start(self._heading("REPEAT"), False, False, 0)
        self.repeat_combo = Gtk.ComboBoxText()
        for value, label in REPEAT_LABELS:
            self.repeat_combo.append(value, label)
        self.repeat_combo.connect("changed", self._repeat_changed)
        inner.pack_start(self.repeat_combo, False, False, 0)

        inner.pack_start(self._heading("LIST"), False, False, 0)
        self.list_combo = Gtk.ComboBoxText()
        self.list_combo.connect("changed", self._list_changed)
        inner.pack_start(self.list_combo, False, False, 0)

        # tags ------------------------------------------------------- #
        inner.pack_start(self._heading("TAGS"), False, False, 0)
        self.tag_flow = Gtk.FlowBox()
        self.tag_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.tag_flow.set_row_spacing(4)
        self.tag_flow.set_column_spacing(4)
        inner.pack_start(self.tag_flow, False, False, 0)
        self.tag_entry = Gtk.Entry()
        self.tag_entry.set_placeholder_text("Add tag + Enter")
        self.tag_entry.connect("activate", self._add_tag)
        inner.pack_start(self.tag_entry, False, False, 0)

        # notes ------------------------------------------------------ #
        inner.pack_start(self._heading("NOTES"), False, False, 0)
        self.notes_view = Gtk.TextView()
        self.notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_view.set_size_request(-1, 90)
        self.notes_view.get_style_context().add_class("textview-frame")
        self.notes_view.connect("focus-out-event", self._notes_focus_out)
        notes_scroll = Gtk.ScrolledWindow()
        notes_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        notes_scroll.add(self.notes_view)
        notes_scroll.set_shadow_type(Gtk.ShadowType.NONE)
        inner.pack_start(notes_scroll, False, False, 0)

        # subtasks --------------------------------------------------- #
        inner.pack_start(self._heading("SUBTASKS"), False, False, 0)
        self.sub_progress = Gtk.Label(xalign=0)
        self.sub_progress.get_style_context().add_class("muted")
        inner.pack_start(self.sub_progress, False, False, 0)
        self.sub_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        inner.pack_start(self.sub_box, False, False, 0)
        self.sub_entry = Gtk.Entry()
        self.sub_entry.set_placeholder_text("Add a step + Enter")
        self.sub_entry.connect("activate", self._add_subtask)
        inner.pack_start(self.sub_entry, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.NONE)
        scrolled.add(inner)
        outer.pack_start(scrolled, True, True, 0)
        return outer

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
            self.title_entry.set_text(task["title"])
            self.notes_view.get_buffer().set_text(task["notes"] or "")
            self._show_due(task["due"])

            self.prio_buttons[int(task["priority"] or 0)].set_active(True)
            self.repeat_combo.set_active_id(task["repeat"] or "")

            self.list_combo.remove_all()
            self.list_combo.append("", "📥 Inbox")
            for lst in self.db.lists():
                self.list_combo.append(str(lst["id"]), lst["name"])
            self.list_combo.set_active_id(
                str(task["list_id"]) if task["list_id"] else "")

            self._render_tags(task["tags"])

            done = task["status"] == "done"
            self.done_btn.set_label("↩ Reopen" if done else "✓ Done")
            self.star_btn.set_label("★" if task["starred"] else "☆")
            stamp = f"Created {task['created_at']}"
            if done and task["completed_at"]:
                stamp += f"  ·  Done {task['completed_at']}"
            self.status_label.set_text(stamp)
            self._render_subtasks(task_id)
        finally:
            self._loading = False
        self.stack.set_visible_child_name("editor")

    def clear(self):
        self.task_id = None
        self.stack.set_visible_child_name("placeholder")

    def reload(self):
        if self.task_id is not None:
            self.load(self.task_id)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _show_due(self, due):
        if not due:
            self.due_btn.set_label("📅  No date")
            self._style_due(())
            return
        d = date.fromisoformat(due[:10])
        today = date.today()
        if d < today:
            text, cls = f"📅  Overdue · {d.day} {d.strftime('%b')}", ("overdue",)
        elif d == today:
            text, cls = "📅  Today", ("due-today",)
        elif d == today + timedelta(days=1):
            text, cls = "📅  Tomorrow", ()
        elif (d - today).days < 7:
            text, cls = f"📅  {d.strftime('%A')}", ()
        else:
            text, cls = f"📅  {d.day} {d.strftime('%b %Y')}", ()
        self.due_btn.set_label(text)
        self._style_due(cls)
        try:
            self.calendar.props.year = d.year
            self.calendar.props.month = d.month - 1
            self.calendar.select_day(d.day)
        except Exception:
            pass

    def _style_due(self, classes):
        child = self.due_btn.get_child()
        if isinstance(child, Gtk.Label):
            ctx = child.get_style_context()
            ctx.remove_class("overdue")
            ctx.remove_class("due-today")
            for cls in classes:
                ctx.add_class(cls)

    def _render_tags(self, tags):
        for child in self.tag_flow.get_children():
            self.tag_flow.remove(child)
        for tag in tags:
            chip = Gtk.Button(label=f"{tag}  ×")
            chip.get_style_context().add_class("flat")
            chip.get_style_context().add_class("meta-chip")
            chip.connect("clicked", self._remove_tag, tag)
            holder = Gtk.FlowBoxChild()
            holder.add(chip)
            self.tag_flow.add(holder)
        self.tag_flow.show_all()

    def _render_subtasks(self, task_id):
        for child in self.sub_box.get_children():
            self.sub_box.remove(child)
        subs = self.db.fetch_subtasks(task_id)
        done = sum(1 for s in subs if s["status"] == "done")
        self.sub_progress.set_text(
            f"{done} of {len(subs)} steps done" if subs else "No steps yet")
        for sub in subs:
            row = Gtk.Box(spacing=4)
            check = Gtk.CheckButton(label=sub["title"])
            check.set_active(sub["status"] == "done")
            if sub["status"] == "done":
                lbl = check.get_child()
                if isinstance(lbl, Gtk.Label):
                    lbl.set_markup(
                        f"<s>{GLib.markup_escape_text(sub['title'])}</s>")
            check.connect("toggled", self._sub_toggled, sub["id"])
            kill = Gtk.Button(label="×")
            kill.get_style_context().add_class("flat")
            kill.set_tooltip_text("Remove step")
            kill.connect("clicked", self._sub_delete, sub["id"])
            row.pack_start(check, True, True, 0)
            row.pack_start(kill, False, False, 0)
            self.sub_box.pack_start(row, False, False, 0)
        self.sub_box.show_all()

    # ------------------------------------------------------------------ #
    # event handlers
    # ------------------------------------------------------------------ #
    def _save(self, **fields):
        if self._loading or self.task_id is None:
            return
        self.db.update_task(self.task_id, **fields)
        self.cb["changed"]()

    def _title_committed(self, entry):
        if self.task_id is None:
            return
        text = entry.get_text().strip()
        if not text:
            task = self.db.get_task(self.task_id)
            entry.set_text(task["title"] if task else "")
            return
        self._save(title=text)

    def _title_focus_out(self, entry, _event):
        self._title_committed(entry)
        return False

    def _due_quick(self, _btn, days):
        self._set_due((date.today() + timedelta(days=days)).isoformat())

    def _cal_selected(self, _cal):
        if self._loading:
            return
        try:
            d = date(self.calendar.props.year,
                     self.calendar.props.month + 1,
                     self.calendar.props.day)
        except ValueError:
            return
        self._set_due(d.isoformat())

    def _set_due(self, due):
        self._show_due(due)
        self._save(due=due)
        pop = self.due_btn.get_popover()
        if pop is not None:
            pop.popdown()

    def _prio_toggled(self, btn, label):
        if self._loading or not btn.get_active():
            return
        self._save(priority={"None": 0, "P1": 1, "P2": 2,
                             "P3": 3, "P4": 4}[label])

    def _repeat_changed(self, combo):
        if self._loading:
            return
        self._save(repeat=combo.get_active_id() or "")

    def _list_changed(self, combo):
        if self._loading:
            return
        active = combo.get_active_id()
        self._save(list_id=int(active) if active else None)

    def _add_tag(self, entry):
        text = entry.get_text().strip().lower().replace(",", " ")
        entry.set_text("")
        if not text or self.task_id is None:
            return
        tags = self.db.tags_of(self.task_id)
        for token in text.split():
            token = token.lstrip("#")
            if token and token not in tags:
                tags.append(token)
        self.db.set_tags(self.task_id, tags)
        self._render_tags(self.db.tags_of(self.task_id))
        self.cb["changed"]()

    def _remove_tag(self, _btn, tag):
        if self.task_id is None:
            return
        tags = [t for t in self.db.tags_of(self.task_id) if t != tag]
        self.db.set_tags(self.task_id, tags)
        self._render_tags(tags)
        self.cb["changed"]()

    def _notes_text(self):
        buf = self.notes_view.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, True).rstrip("\n")

    def _notes_focus_out(self, *_args):
        if self._loading or self.task_id is None:
            return False
        task = self.db.get_task(self.task_id)
        text = self._notes_text()
        if task is not None and (task["notes"] or "") != text:
            self._save(notes=text)
        return False

    def _toggle_done(self):
        if self.task_id is not None:
            self.cb["done"](self.task_id)

    def _toggle_star(self):
        if self.task_id is None:
            return
        task = self.db.get_task(self.task_id)
        value = not task.get("starred")
        self.star_btn.set_label("★" if value else "☆")
        self.cb["star"](self.task_id, value)

    def _delete(self):
        if self.task_id is not None:
            self.cb["delete"](self.task_id)

    def _add_subtask(self, entry):
        text = entry.get_text().strip()
        entry.set_text("")
        if not text or self.task_id is None:
            return
        parent = self.db.get_task(self.task_id)
        self.db.add_task(text, list_id=parent.get("list_id"),
                         parent_id=self.task_id)
        self._render_subtasks(self.task_id)
        self.cb["changed"]()

    def _sub_toggled(self, btn, sub_id):
        if self._loading:
            return
        if btn.get_active():
            self.db.update_task(sub_id, status="done",
                                completed_at=db_now())
        else:
            self.db.update_task(sub_id, status="open", completed_at=None)
        self._render_subtasks(self.task_id)
        self.cb["changed"]()

    def _sub_delete(self, _btn, sub_id):
        self.db.delete_task(sub_id)
        self._render_subtasks(self.task_id)
        self.cb["changed"]()



"""MintDo application window and wiring."""

from __future__ import annotations

import os
import sys
from datetime import date

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from mintdo import APP_ID, APP_NAME, __version__  # noqa: E402
from mintdo import quickadd  # noqa: E402
from mintdo.db import (Database, now_ts, seed_if_empty,  # noqa: E402
                       today)
from mintdo.theme import Theme  # noqa: E402
from mintdo.ui import dialogs  # noqa: E402
from mintdo.ui.detail import DetailPanel  # noqa: E402
from mintdo.ui.sidebar import Sidebar  # noqa: E402
from mintdo.ui.stats import StatsPopover  # noqa: E402
from mintdo.ui.taskview import TaskView  # noqa: E402
from mintdo.ui.toast import Toast  # noqa: E402

DATA_DIR = os.path.join(GLib.get_user_data_dir(), "mintdo")
DB_PATH = os.path.join(DATA_DIR, "mintdo.db")

# view key -> (title, subtitle, empty-state (icon, headline, hint))
VIEW_META = {
    "today": ("Today", "Due today or overdue",
              ("🌤️", "You're all caught up",
               "Nothing is due today — enjoy the calm.")),
    "upcoming": ("Upcoming", "The next seven days",
                 ("📅", "Nothing on the horizon",
                  "New due dates show up here.")),
    "all": ("All Tasks", "Every open task",
            ("📝", "No tasks yet", "Add one with the box above ⬆")),
    "starred": ("Starred", "Tasks you pinned",
                ("⭐", "No stars yet", "Tap ☆ on a task to pin it here.")),
    "inbox": ("Inbox", "Tasks that aren't in a list",
              ("📥", "Inbox zero", "Tasks without a list land here.")),
    "completed": ("Completed", "What you've finished",
                  ("🏁", "Nothing completed yet",
                   "Tick off a task and it appears here.")),
}


class MintDoApp(Gtk.Application):
    def __init__(self, smoke: bool = False):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.smoke = smoke
        self.db: Database | None = None
        self.theme: Theme | None = None
        self.window = None
        self.kind, self.key = "view", "today"
        self.search_term = ""
        self._size_id = 0

    # ------------------------------------------------------------------ #
    def do_startup(self):
        Gtk.Application.do_startup(self)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db = Database(DB_PATH)
        seed_if_empty(self.db)
        self.theme = Theme()
        self.theme.set_mode(self.db.get_setting("theme", "system"))
        self._install_actions()

    def _install_actions(self):
        simple = (
            ("new-task", self._act_new_task, ["<Control>n"]),
            ("new-list", self._act_new_list, ["<Control><Shift>n"]),
            ("search", self._act_search, ["<Control>f"]),
            ("undo", self._act_undo, ["<Control>z"]),
            ("toggle-dark", self._act_toggle_dark, ["<Control>d"]),
            ("stats", self._act_stats, ["<Control>i"]),
            ("export", self._act_export, ["<Control><Shift>s"]),
            ("import", self._act_import, ["<Control><Shift>o"]),
            ("shortcuts", self._act_shortcuts, ["F1"]),
            ("about", self._act_about, None),
        )
        for name, handler, accels in simple:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

        sidebar = Gio.SimpleAction.new_stateful(
            "sidebar-visible", None, GLib.Variant.new_boolean(True))
        sidebar.connect("activate", self._act_sidebar_visible)
        self.add_action(sidebar)

        stored = self.db.get_setting("theme", "system")
        theme = Gio.SimpleAction.new_stateful(
            "theme", GLib.VariantType.new("s"),
            GLib.Variant.new_string(stored))
        theme.connect("activate", self._act_theme)
        self.add_action(theme)

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def _act_new_task(self, *_):
        if getattr(self, "taskview", None):
            self.taskview.focus_quick_add()

    def _act_new_list(self, *_):
        self._new_list()

    def _act_search(self, *_):
        if getattr(self, "taskview", None):
            self.taskview.toggle_search()

    def _act_undo(self, *_):
        if getattr(self, "toast", None):
            self.toast.trigger_undo()

    def _act_toggle_dark(self, *_):
        mode = "light" if self.theme.prefers_dark() else "dark"
        self._apply_theme(mode)

    def _act_theme(self, action, param):
        self._apply_theme(param.get_string())

    def _apply_theme(self, mode):
        action = self.lookup_action("theme")
        if action:
            action.set_state(GLib.Variant.new_string(mode))
        self.theme.set_mode(mode)
        if self.db:
            self.db.set_setting("theme", mode)

    def _act_sidebar_visible(self, action, *_):
        visible = not action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(visible))
        if getattr(self, "sidebar", None):
            self.sidebar.set_visible(visible)
        if self.db:
            self.db.set_setting("sidebar", "1" if visible else "0")

    def _act_stats(self, *_):
        if getattr(self, "stats_btn", None):
            self.stats_btn.clicked()

    def _act_export(self, *_):
        self._export_backup()

    def _act_import(self, *_):
        self._import_backup()

    def _act_shortcuts(self, *_):
        dialogs.show_shortcuts(self.window)

    def _act_about(self, *_):
        dialogs.show_about(self.window)

    # ------------------------------------------------------------------ #
    # window
    # ------------------------------------------------------------------ #
    def do_activate(self):
        if self.window is None:
            self._build_window()
            if self.smoke:
                GLib.timeout_add(1500, self._smoke_check)
        self.window.present()

    def _build_window(self):
        win = Gtk.ApplicationWindow(application=self, title=APP_NAME)
        win.set_icon_name("mintdo")
        width = int(self.db.get_setting("win-w", "1120"))
        height = int(self.db.get_setting("win-h", "720"))
        win.set_default_size(width, height)
        win.set_size_request(880, 560)
        win.connect("configure-event", self._on_configure)
        win.connect("key-press-event", self._on_key)
        self.window = win

        # --- header bar --- #
        header = Gtk.HeaderBar(show_close_button=True)
        header.props.title = APP_NAME

        new_btn = Gtk.Button(label="＋ New Task")
        new_btn.get_style_context().add_class("suggested-action")
        new_btn.set_tooltip_text("New task  (Ctrl+N)")
        new_btn.connect("clicked", lambda *_: self.taskview.focus_quick_add())
        header.pack_start(new_btn)

        self.search_btn = Gtk.ToggleButton(label="Search")
        self.search_btn.set_tooltip_text("Search  (Ctrl+F)")
        self.search_btn.connect("toggled", self._on_search_toggle)
        header.pack_end(self.search_btn)

        self.stats_pop = StatsPopover(self.db)
        self.stats_btn = Gtk.MenuButton(label="Stats")
        self.stats_btn.set_tooltip_text("Your week  (Ctrl+I)")
        self.stats_btn.set_popover(self.stats_pop)
        self.stats_btn.connect("clicked", lambda *_: self.stats_pop.refresh())
        header.pack_end(self.stats_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name(
            "open-menu-symbolic", Gtk.IconSize.BUTTON))
        model = Gio.Menu()
        appearance = Gio.Menu()
        appearance.append("Follow system", "app.theme::system")
        appearance.append("Light", "app.theme::light")
        appearance.append("Dark", "app.theme::dark")
        model.append_submenu("Appearance", appearance)
        edit = Gio.Menu()
        edit.append("New list…", "app.new-list")
        edit.append("Undo last action", "app.undo")
        edit.append_item(self._sidebar_menu_item())
        model.append_submenu("Edit", edit)
        backup = Gio.Menu()
        backup.append("Export backup…", "app.export")
        backup.append("Import backup…", "app.import")
        model.append_section(None, backup)
        help_menu = Gio.Menu()
        help_menu.append("Keyboard shortcuts", "app.shortcuts")
        help_menu.append("About MintDo", "app.about")
        model.append_section(None, help_menu)
        menu_btn.set_menu_model(model)
        header.pack_end(menu_btn)
        win.set_titlebar(header)

        # --- main content --- #
        self.taskview = TaskView({
            "quick_add": self.quick_add,
            "select": self._on_row_selected,
            "activate": self._on_row_activated,
            "toggle": self._on_toggle_task,
            "star": self._on_star_task,
            "delete": self._on_delete_task,
            "search": self._on_search,
            "sort": self._on_sort,
        })
        self.detail = DetailPanel(self.db, {
            "changed": self.refresh,
            "delete": self._on_delete_task,
            "done": self._on_toggle_task,
            "star": self._on_star_task,
        })
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.pack1(self.taskview, True, False)
        self.paned.pack2(self.detail, False, False)
        self.paned.set_position(max(360, width - 330))

        self.sidebar = Sidebar(
            self.db,
            on_select=self._on_sidebar_select,
            on_new_list=self._new_list,
            on_edit_list=self._edit_list,
            on_delete_list=self._delete_list)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.pack_start(self.sidebar, False, False, 0)
        body.pack_start(self.paned, True, True, 0)

        overlay = Gtk.Overlay()
        overlay.add(body)
        self.toast = Toast()
        overlay.add_overlay(self.toast)

        win.add(overlay)
        self.load_view()
        win.show_all()
        self.sidebar.set_visible(
            self.lookup_action("sidebar-visible").get_state().get_boolean())
        if self.db.get_setting("welcome-notify") != "1":
            GLib.timeout_add_seconds(4, self._maybe_notify)
            self.db.set_setting("welcome-notify", "1")

    def _sidebar_menu_item(self):
        return Gio.MenuItem.new("Show sidebar", "app.sidebar-visible")

    # ------------------------------------------------------------------ #
    def _on_configure(self, _win, event):
        if self._size_id:
            GLib.source_remove(self._size_id)
        self._size_id = GLib.timeout_add(
            800, self._save_size, event.width, event.height)
        return False

    def _save_size(self, width, height):
        self.db.set_setting("win-w", width)
        self.db.set_setting("win-h", height)
        self._size_id = 0
        return False

    def _on_key(self, _win, event):
        if event.keyval == Gdk.KEY_F2 and self.detail.task_id:
            self.detail.title_entry.grab_focus()
            self.detail.title_entry.select_region(0, -1)
            return True
        if event.keyval == Gdk.KEY_Escape:
            if self.taskview.search_bar.get_search_mode():
                self.search_btn.set_active(False)
                return True
        return False

    def _on_search_toggle(self, button, *_):
        visible = button.get_active()
        self.taskview.set_search_visible(visible)
        if not visible:
            self.taskview.clear_search()

    # ------------------------------------------------------------------ #
    # view logic
    # ------------------------------------------------------------------ #
    def refresh(self):
        if getattr(self, "sidebar", None):
            self.sidebar.refresh()
        self.load_view()

    def load_view(self):
        if not getattr(self, "taskview", None):
            return
        search, sort = self.search_term, self.taskview.sort
        list_names = {lst["id"]: lst["name"] for lst in self.db.lists()}
        count_note = lambda n: f"{n} task" + ("s" if n != 1 else "")  # noqa: E731

        if self.kind == "view":
            title, sub, empty = VIEW_META[self.key]
            tasks = self.db.fetch_tasks(self.key, search=search, sort=sort)
            show_list = self.key not in ("inbox", "completed")
            sub = f"{count_note(len(tasks))} · {sub}"
        else:
            lst = self.db.get_list(self.key)
            if lst is None:  # list deleted underneath us
                self.kind, self.key = "view", "all"
                self.load_view()
                return
            title = lst["name"]
            sub = f"{count_note(self.db.count_open('list', self.key))} open"
            tasks = self.db.fetch_tasks("list", list_id=self.key,
                                        search=search, sort=sort)
            show_list = False
            empty = ("🗒️", "No tasks here", "Add one with the box above ⬆")
        if search:
            sub = f'{len(tasks)} result' + ("s" if len(tasks) != 1 else "") \
                  + f' for “{search}”'
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
    def _on_row_selected(self, task_id):
        self.detail.load(task_id)

    def _on_row_activated(self, task_id):
        self.detail.load(task_id)
        self.detail.title_entry.grab_focus()
        self.detail.title_entry.select_region(0, -1)

    def quick_add(self, text):
        parsed = quickadd.parse(text)
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

    def _on_toggle_task(self, task_id, done=None):
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

    def _on_star_task(self, task_id, value):
        self.db.update_task(task_id, starred=bool(value))
        self.refresh()

    def _on_delete_task(self, task_id):
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

    def _on_search(self, term):
        self.search_term = term
        self.load_view()

    def _on_sort(self, _value):
        self.load_view()

    def _on_sidebar_select(self, kind, key):
        self.kind, self.key = kind, key
        self.load_view()

    # ------------------------------------------------------------------ #
    # list management
    # ------------------------------------------------------------------ #
    def _new_list(self):
        dialog = dialogs.ListDialog(self.window, title="New list")
        if dialog.run() == Gtk.ResponseType.OK:
            name, color = dialog.values
            lid = self.db.add_list(name, color)
            self.sidebar.select("list", lid)
            self.kind, self.key = "list", lid
            self.refresh()

    def _edit_list(self, list_id):
        lst = self.db.get_list(list_id)
        if lst is None:
            return
        dialog = dialogs.ListDialog(
            self.window, title="Edit list", initial_name=lst["name"],
            initial_color=lst["color"])
        if dialog.run() == Gtk.ResponseType.OK:
            name, color = dialog.values
            self.db.rename_list(list_id, name)
            self.db.set_list_color(list_id, color)
            self.refresh()

    def _delete_list(self, list_id):
        lst = self.db.get_list(list_id)
        if lst is None:
            return
        if not dialogs.confirm_delete_list(self.window, lst["name"]):
            return
        self.db.delete_list(list_id)
        if self.kind == "list" and self.key == list_id:
            self.kind, self.key = "view", "all"
            self.sidebar.select("view", "all")
        self.refresh()

    # ------------------------------------------------------------------ #
    # backup
    # ------------------------------------------------------------------ #
    def _file_dialog(self, title, action, accept):
        dialog = Gtk.FileChooserDialog(
            title=title, transient_for=self.window, action=action)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           accept, Gtk.ResponseType.OK)
        json_filter = Gtk.FileFilter()
        json_filter.set_name("MintDo backup (*.json)")
        json_filter.add_pattern("*.json")
        dialog.add_filter(json_filter)
        return dialog

    def _export_backup(self):
        dialog = self._file_dialog("Export backup",
                                   Gtk.FileChooserAction.SAVE,
                                   Gtk.STOCK_SAVE)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name(
            f"mintdo-backup-{date.today().isoformat()}.json")
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(self.db.export_json())
                self.toast.show_toast(
                    f"Backup saved: {os.path.basename(path)}")
            except OSError as exc:
                self._error("Export failed", str(exc))
        dialog.destroy()

    def _import_backup(self):
        dialog = self._file_dialog("Import backup",
                                   Gtk.FileChooserAction.OPEN,
                                   Gtk.STOCK_OPEN)
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    count = self.db.import_json(handle.read())
            except Exception as exc:  # bad file, bad JSON, wrong app
                self._error("Import failed", str(exc))
            else:
                self.db.set_setting("seeded", "1")
                if self.kind == "list" and self.db.get_list(self.key) is None:
                    self.kind, self.key = "view", "all"
                    self.sidebar.select("view", "all")
                self.refresh()
                self.toast.show_toast(f"Restored {count} task(s)")
        dialog.destroy()

    def _error(self, title, secondary):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE,
                                   text=title)
        dialog.format_secondary_text(secondary)
        dialog.run()
        dialog.destroy()


    # ------------------------------------------------------------------ #
    # misc
    # ------------------------------------------------------------------ #
    def _maybe_notify(self):
        try:
            import gi
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify
            Notify.init(APP_NAME)
            count = self.db.count_open("today")
            if count:
                Notify.Notification.new(
                    f"MintDo · {count} task"
                    + ("s" if count != 1 else "") + " today",
                    "You have overdue or due-today tasks waiting.",
                    "mintdo").show()
        except Exception:
            pass
        return False

    def do_shutdown(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        Gtk.Application.do_shutdown(self)

    # ------------------------------------------------------------------ #
    def _smoke_check(self):
        problems = []
        if self.window is None or not self.window.get_realized():
            problems.append("window not realized")
        if not self.taskview.listbox.get_children():
            problems.append("task list is empty")
        if not self.sidebar.listbox.get_children():
            problems.append("sidebar is empty")
        # exercise quick-add end-to-end, then clean up after ourselves
        self.quick_add("!1 smoke test #qa tomorrow")
        if not self.db.fetch_tasks("all", search="smoke test"):
            problems.append("quick-add did not create a task")
        # rows rebuilt by the refresh above must actually be shown
        rows = self.taskview.listbox.get_children()
        if rows and not all(r.is_visible() for r in rows):
            problems.append("task rows exist but are not visible")
        for hit in self.db.fetch_tasks("all", search="#qa"):
            self.db.delete_task(hit["id"])
        self.refresh()
        if problems:
            print("SMOKE FAIL: " + "; ".join(problems), file=sys.stderr)
            self._smoke_failed = True
        else:
            print("SMOKE OK")
        self.quit()
        return False


def run(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    smoke = "--smoke-test" in argv
    argv = [a for a in argv if a != "--smoke-test"]
    app = MintDoApp(smoke=smoke)
    code = app.run(argv)
    if getattr(app, "_smoke_failed", False):
        return 1
    return code






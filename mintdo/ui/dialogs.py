"""Dialogs: list editor, list deletion confirmation, shortcuts, about."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from mintdo import APP_NAME, __version__
from mintdo.ui.sidebar import LIST_COLORS


class ListDialog(Gtk.Dialog):
    """Create or rename a list and pick its colour."""

    def __init__(self, parent, title="New list", initial_name="",
                 initial_color=None):
        super().__init__(title=title, transient_for=parent, modal=True,
                         flags=Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.name_entry = Gtk.Entry(text=initial_name)
        self.name_entry.set_placeholder_text("List name, e.g. “Groceries”")
        self.name_entry.set_activates_default(True)
        box.pack_start(self.name_entry, False, False, 0)

        label = Gtk.Label(label="Colour", xalign=0)
        box.pack_start(label, False, False, 0)

        self.color_buttons = []
        chosen = initial_color or LIST_COLORS[0]
        group = None
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(8)
        for color in LIST_COLORS:
            btn = Gtk.RadioButton.new_with_label_from_widget(group, "   ")
            group = btn
            btn._mintdo_color = color
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_size_request(34, 26)
            rgba = Gdk.RGBA()
            rgba.parse(color)
            btn.override_background_color(Gtk.StateFlags.NORMAL, rgba)
            btn.override_background_color(Gtk.StateFlags.PRELIGHT, rgba)
            if color == chosen:
                btn.set_active(True)
            self.color_buttons.append(btn)
            holder = Gtk.FlowBoxChild()
            holder.add(btn)
            flow.add(holder)
        box.pack_start(flow, False, False, 0)
        self.show_all()

    def run(self):
        response = super().run()
        if response == Gtk.ResponseType.OK:
            name = self.name_entry.get_text().strip()
            if not name:
                response = Gtk.ResponseType.NONE
        self.destroy()
        return response

    @property
    def values(self):
        color = LIST_COLORS[0]
        for btn in self.color_buttons:
            if btn.get_active():
                color = btn._mintdo_color
        return self.name_entry.get_text().strip(), color


def confirm_delete_list(parent, name) -> bool:
    dialog = Gtk.MessageDialog(
        transient_for=parent, modal=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text=f"Delete “{name}”?")
    dialog.format_secondary_text(
        "Tasks in this list move to the Inbox.")
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.YES


def show_about(parent):
    import os
    about = Gtk.AboutDialog(transient_for=parent, modal=True)
    about.set_program_name(APP_NAME)
    about.set_version(__version__)
    about.set_comments(
        "A friendly to-do list for Linux Mint.\n"
        "Lists, tags, subtasks, recurring tasks and daily streaks — "
        "completely offline.")
    about.set_license_type(Gtk.License.MIT_X11)
    logo_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "assets", "icon.svg")
    if os.path.exists(logo_path):
        try:
            from gi.repository import GdkPixbuf
            about.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale(
                logo_path, 96, 96, True))
        except Exception:
            pass
    about.run()
    about.destroy()


SHORTCUTS = (
    ("<Control>n", "New task", "Jump to the quick-add box"),
    ("<Control><Shift>n", "New list", "Create a new list"),
    ("<Control>f", "Search", "Find tasks by title, note or #tag"),
    ("<Control>z", "Undo", "Undo the last completion or deletion"),
    ("<Control>d", "Dark mode", "Switch between light and dark theme"),
    ("<Control>b", "Sidebar", "Show or hide the sidebar"),
    ("<Control>i", "Stats", "Open the weekly progress popover"),
    ("Delete", "Delete task", "Remove the selected task (undoable)"),
    ("space", "Complete", "Tick the selected task on or off"),
    ("F2", "Edit task", "Focus the title in the detail panel"),
)


def show_shortcuts(parent):
    win = Gtk.ShortcutsWindow(transient_for=parent, modal=True)
    section = Gtk.ShortcutsSection(title="MintDo")
    group = Gtk.ShortcutsGroup(title="Keyboard")
    for accel, title, desc in SHORTCUTS:
        shortcut = Gtk.ShortcutsShortcut(title=title, accel=accel,
                                         subtitle=desc)
        group.add(shortcut)
    section.add(group)
    win.add(section)
    win.show_all()
    win.run()
    win.destroy()


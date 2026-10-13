"""A small undo banner shown at the bottom of the window."""

from __future__ import annotations

from gi.repository import GLib, Gtk


class Toast(Gtk.Revealer):
    def __init__(self):
        super().__init__(valign=Gtk.Align.END, halign=Gtk.Align.CENTER,
                         transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                         transition_duration=220, reveal_child=False)
        self._hide_id = 0
        self._on_undo = None

        self.label = Gtk.Label(xalign=0)
        self.button = Gtk.Button(label="Undo")
        self.button.get_style_context().add_class("flat")
        self.button.connect("clicked", self._undo_clicked)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("toast")
        box.pack_start(self.label, True, True, 0)
        box.pack_start(self.button, False, False, 0)
        self.add(box)

    def show_toast(self, message: str, on_undo=None, timeout_ms: int = 5000):
        """Display *message*; pressing Undo invokes *on_undo* once."""
        if self._hide_id:
            GLib.source_remove(self._hide_id)
            self._hide_id = 0
        self.label.set_text(message)
        self._on_undo = on_undo
        self.button.set_visible(on_undo is not None)
        self.set_reveal_child(True)
        self._hide_id = GLib.timeout_add(timeout_ms, self._hide)

    def _undo_clicked(self, *_args):
        callback, self._on_undo = self._on_undo, None
        self._hide()
        if callback:
            callback()

    def trigger_undo(self) -> bool:
        """Run the pending undo callback (Ctrl+Z). Returns True if one ran."""
        if self._on_undo is None or not self.get_reveal_child():
            return False
        self._undo_clicked()
        return True

    def cancel(self):
        if self._hide_id:
            GLib.source_remove(self._hide_id)
            self._hide_id = 0
        self._on_undo = None
        self.set_reveal_child(False)

    def _hide(self):
        self.set_reveal_child(False)
        self._hide_id = 0
        return False

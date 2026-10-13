"""Theme handling: light / dark / follow-system for the whole GTK app."""

from __future__ import annotations

import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

MODES = ("system", "light", "dark")


class Theme:
    """Owns the CSS providers for the default screen."""

    def __init__(self):
        self.screen = Gdk.Screen.get_default()
        self.settings = Gtk.Settings.get_default()
        self.light = Gtk.CssProvider()
        self.light.load_from_path(os.path.join(ASSETS_DIR, "light.css"))
        self.dark = Gtk.CssProvider()
        self.dark.load_from_path(os.path.join(ASSETS_DIR, "dark.css"))
        self._dark_installed = False
        self.mode = "system"
        Gtk.StyleContext.add_provider_for_screen(
            self.screen, self.light,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            mode = "system"
        self.mode = mode
        prefer_dark = self.prefers_dark()
        if prefer_dark and not self._dark_installed:
            Gtk.StyleContext.add_provider_for_screen(
                self.screen, self.dark,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            self._dark_installed = True
        elif not prefer_dark and self._dark_installed:
            Gtk.StyleContext.remove_provider_for_screen(self.screen, self.dark)
            self._dark_installed = False
        if self.settings:
            self.settings.set_property("gtk-application-prefer-dark-theme",
                                       prefer_dark)

    def prefers_dark(self) -> bool:
        if self.mode == "dark":
            return True
        if self.mode == "light":
            return False
        return self._system_prefers_dark()

    @staticmethod
    def _system_prefers_dark() -> bool:
        # Linux Mint exposes the GTK theme through Cinnamon/GNOME settings.
        for schema, key in (("org.cinnamon.desktop.interface", "gtk-theme"),
                            ("org.gnome.desktop.interface", "gtk-theme")):
            try:
                settings = Gio.Settings.new(schema)
                theme = settings.get_string(key) or ""
                if theme:
                    return "dark" in theme.lower()
            except Exception:
                continue
        try:
            name = Gtk.Settings.get_default().get_property("gtk-theme-name")
            return "dark" in (name or "").lower()
        except Exception:
            return False

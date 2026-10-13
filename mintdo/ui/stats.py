"""Statistics popover: streaks and a 7-day completion bar chart."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from mintdo.db import Database

DAY_LETTERS = ("M", "T", "W", "T", "F", "S", "S")


def _stat_box(number_label):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    box.set_halign(Gtk.Align.CENTER)
    number = Gtk.Label(label="0")
    number.get_style_context().add_class("stat-number")
    caption = Gtk.Label(label=number_label)
    caption.get_style_context().add_class("stat-label")
    box.pack_start(number, False, False, 0)
    box.pack_start(caption, False, False, 0)
    return box, number


class StatsPopover(Gtk.Popover):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.get_style_context().add_class("stats-pop")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        heading = Gtk.Label(label="Your week", xalign=0)
        heading.get_style_context().add_class("heading")
        box.pack_start(heading, False, False, 0)

        numbers = Gtk.Box(spacing=18)
        self.today_box, self.today_n = _stat_box("done today")
        self.week_box, self.week_n = _stat_box("this week")
        self.streak_box, self.streak_n = _stat_box("day streak")
        for b in (self.today_box, self.week_box, self.streak_box):
            numbers.pack_start(b, True, True, 0)
        box.pack_start(numbers, False, False, 0)

        self.chart = Gtk.DrawingArea()
        self.chart.set_size_request(240, 110)
        self.chart.connect("draw", self._draw_chart)
        box.pack_start(self.chart, False, False, 0)

        self.footer = Gtk.Label(xalign=0)
        self.footer.get_style_context().add_class("muted")
        box.pack_start(self.footer, False, False, 0)

        box.show_all()
        self.add(box)   # NB: box only; showing the popover itself would pop it up

    def refresh(self):
        s = self.db.stats()
        self.today_n.set_text(str(s["done_today"]))
        self.week_n.set_text(str(s["done_week"]))
        self.streak_n.set_text(str(s["streak"]))
        open_word = "task" if s["open"] == 1 else "tasks"
        self.footer.set_text(f"{s['open']} open {open_word} waiting for you")
        self._series = s["series"]
        self.chart.queue_draw()

    # ------------------------------------------------------------------ #
    def _draw_chart(self, _widget, cr):
        series = getattr(self, "_series", [])
        if not series:
            return
        width = self.chart.get_allocated_width()
        height = self.chart.get_allocated_height()
        top, bottom = 14, 16
        plot_h = max(10, height - top - bottom)
        slot = width / 7.0
        peak = max(v for _, v in series) or 1

        try:
            ok, accent = self.chart.get_style_context().lookup_color("accent")
        except Exception:
            ok, accent = False, None
        if not ok:
            from gi.repository import Gdk
            accent = Gdk.RGBA()
            accent.parse("#87cf3e")

        for i, (day, value) in enumerate(series):
            cx = i * slot + slot / 2
            bar_w = slot * 0.55
            # bar
            if value > 0:
                h = max(4, plot_h * value / peak)
                cr.set_source_rgba(accent.red, accent.green, accent.blue,
                                   1.0 if i == 6 else 0.75)
                cr.rectangle(cx - bar_w / 2, top + plot_h - h, bar_w, h)
                cr.fill()
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
                cr.select_font_face("Sans")
                cr.set_font_size(9)
                text = str(value)
                ext = cr.text_extents(text)
                cr.move_to(cx - ext.width / 2, top + plot_h - h - 4)
                cr.show_text(text)
            # day letter
            cr.set_source_rgba(0.5, 0.5, 0.5, 1.0)
            cr.select_font_face("Sans")
            cr.set_font_size(9)
            letter = DAY_LETTERS[i]
            ext = cr.text_extents(letter)
            cr.move_to(cx - ext.width / 2, height - 4)
            cr.show_text(letter)

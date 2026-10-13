"""Statistics dialog: streaks and a 7-day completion bar chart (Qt)."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from mintdo.db import Database

DAY_LETTERS = ("M", "T", "W", "T", "F", "S", "S")


class BarChart(QWidget):
    """Seven vertical bars showing completions per day of the last week."""

    def __init__(self, accent: str):
        super().__init__()
        self.accent = QColor(accent)
        self.series = []
        self.setMinimumHeight(150)

    def set_series(self, series, accent: str):
        self.series = series
        self.accent = QColor(accent)
        self.update()

    def paintEvent(self, _event):
        if not self.series:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top, bottom = 16, 18
        plot_h = max(10, h - top - bottom)
        slot = w / 7.0
        peak = max(v for _, v in self.series) or 1

        for i, (_day, value) in enumerate(self.series):
            cx = i * slot + slot / 2
            bar_w = slot * 0.55
            if value > 0:
                bar_h = max(4, plot_h * value / peak)
                color = QColor(self.accent)
                color.setAlpha(255 if i == 6 else 191)
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(
                    QRect(int(cx - bar_w / 2),
                          int(top + plot_h - bar_h),
                          int(bar_w), int(bar_h)), 3, 3)
                painter.setPen(QColor(self.accent))
                font = QFont()
                font.setPointSize(9)
                painter.setFont(font)
                text = str(value)
                tw = painter.fontMetrics().horizontalAdvance(text)
                painter.drawText(int(cx - tw / 2),
                                 int(top + plot_h - bar_h - 4), text)
            painter.setPen(QColor("#8a908a"))
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            letter = DAY_LETTERS[i]
            lw = painter.fontMetrics().horizontalAdvance(letter)
            painter.drawText(int(cx - lw / 2), h - 4, letter)
        painter.end()


def _stat_block(number_label: str):
    block = QWidget()
    lay = QVBoxLayout(block)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    number = QLabel("0")
    number.setObjectName("statNumber")
    number.setAlignment(Qt.AlignmentFlag.AlignCenter)
    caption = QLabel(number_label)
    caption.setObjectName("statLabel")
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(number)
    lay.addWidget(caption)
    return block, number


class StatsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Your week")
        self.setMinimumWidth(340)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        heading = QLabel("Your week")
        heading.setObjectName("viewTitle")
        root.addWidget(heading)

        numbers = QHBoxLayout()
        numbers.setSpacing(18)
        self.today_block, self.today_n = _stat_block("done today")
        self.week_block, self.week_n = _stat_block("this week")
        self.streak_block, self.streak_n = _stat_block("day streak")
        for block in (self.today_block, self.week_block, self.streak_block):
            numbers.addWidget(block, 1)
        root.addLayout(numbers)

        self.chart = BarChart("#4f9426")
        root.addWidget(self.chart, 1)

        self.footer = QLabel()
        self.footer.setObjectName("viewSub")
        root.addWidget(self.footer)

    def refresh(self):
        s = self.db.stats()
        self.today_n.setText(str(s["done_today"]))
        self.week_n.setText(str(s["done_week"]))
        self.streak_n.setText(str(s["streak"]))
        open_word = "task" if s["open"] == 1 else "tasks"
        self.footer.setText(f"{s['open']} open {open_word} waiting for you")
        self.chart.set_series(s["series"], self._accent())

    def _accent(self) -> str:
        from mintdo.qt.theme import colors
        try:
            parent = self.parentWidget()
            dark = getattr(parent, "theme", None)
            if dark is not None:
                return colors(dark.prefers_dark())["accent"]
        except Exception:
            pass
        return "#4f9426"

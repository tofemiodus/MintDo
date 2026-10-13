"""Qt theming for MintDo (Windows + fallback on Linux).

Uses the same palette as the GTK stylesheets so both versions look alike.
"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# name -> (light, dark) — mirrors mintdo/assets/light.css and dark.css
PALETTE = {
    "bg": ("#f2f4ee", "#1f231f"),
    "surface": ("#ffffff", "#272c27"),
    "surface_alt": ("#e8ece1", "#222623"),
    "border": ("#dbdfd3", "#383e38"),
    "text": ("#2b302a", "#e7ebe4"),
    "text_dim": ("#757c72", "#98a096"),
    "accent": ("#4f9426", "#87cf3e"),
    "accent_bright": ("#87cf3e", "#9cdd52"),
    "danger": ("#d64f52", "#ef6a6d"),
    "warn": ("#d8952a", "#eab04b"),
    "info": ("#4a86c5", "#6fa8e0"),
}


def colors(dark: bool) -> dict:
    idx = 1 if dark else 0
    return {k: v[idx] for k, v in PALETTE.items()}


def system_prefers_dark() -> bool:
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except Exception:
            return False
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=2).stdout.strip().lower()
        return "dark" in out
    except Exception:
        return False



def btn_dark() -> str:
    return "#1f231f"


def _sheet_frame(c: dict, accent_soft: str) -> str:
    return f"""
    QWidget {{ background: {c['bg']}; color: {c['text']}; font-size: 13px; }}
    QFrame#header {{
        background: {c['surface']};
        border-bottom: 1px solid {c['border']};
    }}
    QLabel#viewTitle {{ font-size: 19px; font-weight: 700; background:
        transparent; }}
    QLabel#viewSub {{ color: {c['text_dim']}; background: transparent; }}
    QFrame#sidebar {{
        background: {c['surface']};
        border-right: 1px solid {c['border']};
    }}
    QListWidget#navList {{
        background: transparent; border: none; outline: none;
    }}
    QListWidget#navList::item {{ border-radius: 8px; margin: 1px 8px;
        padding: 7px 10px; }}
    QListWidget#navList::item:hover {{ background: {c['surface_alt']}; }}
    QListWidget#navList::item:selected {{ background: {c['surface_alt']};
        color: {c['text']}; }}
    QLabel#sectionTitle {{ color: {c['text_dim']}; font-size: 11px;
        font-weight: 700; }}
    QLabel#count {{ color: {c['text_dim']}; }}
    QFrame#taskRow {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 8px 12px;
    }}
    QFrame#taskRow:hover {{ border-color: {accent_soft}; }}
    QFrame#taskRow[selected="true"] {{ border: 2px solid {accent_soft}; }}
    QLabel#title {{ font-size: 14px; background: transparent; }}
    QLabel#title[done="true"] {{ color: {c['text_dim']}; }}
    QLabel[chip="plain"] {{
        background: {c['surface_alt']}; color: {c['text_dim']};
        border-radius: 9px; padding: 2px 8px; font-size: 11px; }}
    QLabel[chip="tag"] {{
        background: {c['surface_alt']}; color: {c['accent']};
        border-radius: 9px; padding: 2px 8px; font-size: 11px; }}
    QLabel[chip="p1"] {{ background: transparent; color: {c['danger']};
        font-weight: 700; font-size: 11px; }}
    QLabel[chip="p2"] {{ background: transparent; color: {c['warn']};
        font-weight: 700; font-size: 11px; }}
    QLabel[chip="p3"] {{ background: transparent; color: {c['info']};
        font-weight: 700; font-size: 11px; }}
    QLabel[chip="p4"] {{ background: transparent; color: {c['text_dim']};
        font-weight: 700; font-size: 11px; }}
    QLabel[chip="overdue"] {{ background: transparent; color: {c['danger']};
        font-weight: 700; font-size: 11px; }}
    QLabel[chip="duetoday"] {{ background: transparent; color: {accent_soft};
        font-weight: 700; font-size: 11px; }}
    QToolButton#star {{ background: transparent; border: none;
        font-size: 16px; color: {c['text_dim']}; }}
    QToolButton#star[on="true"] {{ color: {accent_soft}; }}
    """


def _sheet_input(c: dict, accent_soft: str) -> str:
    return f"""
    QLineEdit, QTextEdit, QComboBox {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 10px;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border-color: {accent_soft}; }}
    QLineEdit#quickAdd {{ padding: 9px 12px; font-size: 14px; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']}; border: 1px solid {c['border']};
        selection-background-color: {c['surface_alt']};
        selection-color: {c['text']}; }}
    QPushButton {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ border-color: {accent_soft}; }}
    QPushButton#primary {{
        background: {accent_soft}; color: {btn_dark()};
        border: none; font-weight: 700; }}
    QPushButton#primary:hover {{ background: {c['accent_bright']}; }}
    QPushButton#danger {{ color: {c['danger']}; }}
    QPushButton#flat {{ background: transparent; border: none;
        padding: 4px 8px; }}
    QPushButton#prio {{ border-radius: 0px; padding: 5px 0px; }}
    QPushButton#prio:checked {{ background: {accent_soft};
        color: {btn_dark()}; font-weight: 700; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {c['border']};
        border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QLabel#statNumber {{ font-size: 20px; font-weight: 700;
        color: {accent_soft}; background: transparent; }}
    QLabel#statLabel {{ color: {c['text_dim']}; font-size: 11px;
        background: transparent; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['border']};
        border-radius: 8px; padding: 6px; }}
    QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {c['surface_alt']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']};
        margin: 4px 8px; }}
    QFrame#toast {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
    }}
    QFrame#detail {{
        background: {c['surface']};
        border-left: 1px solid {c['border']};
    }}
    QFrame#detail QLabel {{ background: transparent; }}
    QLabel#heading {{ color: {c['text_dim']}; font-size: 11px;
        font-weight: 700; }}
    QLabel#mutedLabel {{ color: {c['text_dim']}; }}
    QCheckBox {{ background: transparent; spacing: 8px; }}
    QCalendarWidget {{ background: {c['surface']}; }}
    QCalendarWidget QToolButton {{ background: transparent;
        color: {c['text']}; }}
    QMenuBar {{ background: {c['surface']}; border-bottom: 1px solid
        {c['border']}; }}
    QMenuBar::item:selected {{ background: {c['surface_alt']}; }}
    """


def build_stylesheet(dark: bool) -> str:
    c = colors(dark)
    accent_soft = c["accent_bright"] if dark else c["accent"]
    return _sheet_frame(c, accent_soft) + _sheet_input(c, accent_soft)


class Theme:
    """Keeps the application-wide palette in sync with the chosen mode."""

    MODES = ("system", "light", "dark")

    def __init__(self):
        self.mode = "system"
        self._dark = False

    def prefers_dark(self) -> bool:
        return self._dark

    def stylesheet(self) -> str:
        return build_stylesheet(self._dark)


    def set_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            mode = "system"
        self.mode = mode
        dark = (mode == "dark" or
                (mode == "system" and system_prefers_dark()))
        self._dark = dark
        app = QApplication.instance()
        if app is None:
            return
        c = colors(dark)
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(c["surface"]))
        pal.setColor(QPalette.ColorRole.AlternateBase,
                     QColor(c["surface_alt"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(c["surface"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(c["accent_bright"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(btn_dark()))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["surface"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
        pal.setColor(QPalette.ColorRole.PlaceholderText,
                     QColor(c["text_dim"]))
        app.setPalette(pal)
        app.setStyleSheet(build_stylesheet(dark))


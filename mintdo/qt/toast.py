"""A small undo banner shown at the bottom of the window (Qt)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class Toast(QFrame):
    """Undo banner anchored bottom-centre over *parent*."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self._on_undo = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.label = QLabel()
        self.label.setObjectName("mutedLabel")
        self.button = QPushButton("Undo")
        self.button.setObjectName("flat")
        self.button.clicked.connect(self._undo_clicked)

        box = QHBoxLayout(self)
        box.setContentsMargins(14, 10, 10, 10)
        box.setSpacing(10)
        box.addWidget(self.label, 1)
        box.addWidget(self.button)

        self.hide()

    def show_toast(self, message: str, on_undo=None, timeout_ms: int = 5000):
        self.label.setText(message)
        self._on_undo = on_undo
        self.button.setVisible(on_undo is not None)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(timeout_ms)

    def _place(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        w = self.width()
        x = (parent.width() - w) // 2
        y = parent.height() - self.height() - 28
        self.move(max(12, x), max(12, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self._place()

    def _undo_clicked(self):
        callback, self._on_undo = self._on_undo, None
        self._timer.stop()
        self.hide()
        if callback:
            callback()

    def trigger_undo(self):
        """Run the pending undo callback (Ctrl+Z)."""
        if self._on_undo is None:
            return
        self._undo_clicked()

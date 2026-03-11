from __future__ import annotations
"""
ui/player_bar.py
Top transport bar: artwork, track info, seek slider, control buttons.
Thread-safe: uses a pyqtSignal to update artwork from a background thread.
"""

import logging
import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSlider, QVBoxLayout, QWidget,
)

from ui import styles

if TYPE_CHECKING:
    from roon_manager import RoonManager

logger = logging.getLogger(__name__)

_PLACEHOLDER_PIXMAP: QPixmap | None = None


def _placeholder(size: int) -> QPixmap:
    global _PLACEHOLDER_PIXMAP
    if _PLACEHOLDER_PIXMAP is None:
        px = QPixmap(size, size)
        px.fill()
        from PyQt6.QtGui import QColor
        px.fill(QColor(styles.ARTWORK_PLACEHOLDER))
        _PLACEHOLDER_PIXMAP = px
    return _PLACEHOLDER_PIXMAP


def _fmt(secs: float | None) -> str:
    if secs is None or secs < 0:
        return "—:——"
    s = int(secs)
    return f"{s // 60}:{s % 60:02d}"


class PlayerBar(QWidget):
    """Fixed-height bar at the top of the main window."""

    # Signal emitted from background thread when artwork bytes are ready.
    _artwork_signal = pyqtSignal(str, bytes)

    def __init__(self, roon: "RoonManager", parent: QWidget | None = None):
        super().__init__(parent)
        self._roon = roon
        self._seeking = False
        self._track_length = 0.0
        self._current_image_key: str | None = None

        self.setObjectName("playerBar")
        self.setFixedHeight(80)

        self._artwork_signal.connect(self._on_artwork_ready)
        self._build()

        # 1-second tick to advance position display between server pushes
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._seek_tick)
        self._tick.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # Artwork thumbnail
        self._artwork_lbl = QLabel()
        self._artwork_lbl.setFixedSize(56, 56)
        self._artwork_lbl.setObjectName("playerLabel")
        self._artwork_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._artwork_lbl.setStyleSheet(
            f"background-color: {styles.ARTWORK_PLACEHOLDER}; border-radius: 3px;"
        )
        root.addWidget(self._artwork_lbl)

        # Right side: controls + info + seek
        right = QWidget()
        right.setObjectName("playerBar")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(2)

        # ── Row 1: transport buttons + track info ─────────────────────────────
        top = QWidget()
        top.setObjectName("playerBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(1)

        btn_defs = [
            ("←15", "−15s",   self._on_back15,         styles.FONT_FAMILY if False else None),
            ("⏮",  "Previous", self._roon.prev_track,   None),
            ("⏯",  "Play/Pause", self._roon.play_pause, None),
            ("⏹",  "Stop",    self._roon.stop,          None),
            ("⏭",  "Next",    self._roon.next_track,    None),
            ("15→", "+15s",   self._on_fwd15,           None),
        ]
        self._play_btn: QPushButton | None = None
        for icon, tip, fn, _ in btn_defs:
            btn = self._make_transport_btn(icon, tip, fn)
            th.addWidget(btn)
            if tip == "Play/Pause":
                self._play_btn = btn

        th.addSpacing(10)

        # Track info labels
        info = QWidget()
        info.setObjectName("playerBar")
        iv = QVBoxLayout(info)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(0)

        self._title_lbl = QLabel("Not Playing")
        self._title_lbl.setObjectName("playerLabel")
        self._title_lbl.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {styles.TEXT}; background: transparent;"
        )
        iv.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setObjectName("playerLabel")
        self._sub_lbl.setStyleSheet(
            f"font-size: 11px; color: {styles.TEXT_SECONDARY}; background: transparent;"
        )
        iv.addWidget(self._sub_lbl)
        th.addWidget(info, stretch=1)

        # Status label (right edge)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        th.addWidget(self._status_lbl)

        rv.addWidget(top)

        # ── Row 2: elapsed + seek slider + remaining ──────────────────────────
        seek_row = QWidget()
        seek_row.setObjectName("playerBar")
        sh = QHBoxLayout(seek_row)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(4)

        self._elapsed_lbl = QLabel("—:——")
        self._elapsed_lbl.setObjectName("statusLabel")
        self._elapsed_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._elapsed_lbl.setFixedWidth(38)
        sh.addWidget(self._elapsed_lbl)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("seekSlider")
        self._slider.setRange(0, 10000)
        self._slider.sliderPressed.connect(self._on_seek_press)
        self._slider.sliderReleased.connect(self._on_seek_release)
        sh.addWidget(self._slider, stretch=1)

        self._remain_lbl = QLabel("—:——")
        self._remain_lbl.setObjectName("statusLabel")
        self._remain_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._remain_lbl.setFixedWidth(44)
        sh.addWidget(self._remain_lbl)

        rv.addWidget(seek_row)
        root.addWidget(right, stretch=1)

    def _make_transport_btn(self, icon: str, tip: str, fn) -> QPushButton:
        btn = QPushButton(icon)
        btn.setObjectName("transportBtn")
        btn.setToolTip(tip)
        btn.setFixedSize(34, 28)
        btn.setStyleSheet("font-size: 15px;")
        btn.clicked.connect(fn)
        return btn

    # ── Artwork ───────────────────────────────────────────────────────────────

    def _load_artwork(self, image_key: str) -> None:
        def _fetch():
            data = self._roon.get_image(image_key, width=112, height=112)
            if data:
                self._artwork_signal.emit(image_key, data)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_artwork_ready(self, key: str, data: bytes) -> None:
        """Slot – always called on the main thread via signal."""
        if key != self._current_image_key:
            return
        img = QImage.fromData(data)
        if img.isNull():
            return
        px = QPixmap.fromImage(img).scaled(
            56, 56,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._artwork_lbl.setPixmap(px)
        self._artwork_lbl.setStyleSheet("")   # remove placeholder colour

    def _clear_artwork(self) -> None:
        self._artwork_lbl.clear()
        self._artwork_lbl.setStyleSheet(
            f"background-color: {styles.ARTWORK_PLACEHOLDER}; border-radius: 3px;"
        )

    # ── Seek ──────────────────────────────────────────────────────────────────

    def _on_seek_press(self) -> None:
        self._seeking = True

    def _on_seek_release(self) -> None:
        self._seeking = False
        if self._track_length > 0:
            pos = self._slider.value() / 10000.0 * self._track_length
            self._roon.seek(pos)

    def _on_back15(self) -> None:
        self._roon.seek_relative(-15)

    def _on_fwd15(self) -> None:
        self._roon.seek_relative(15)

    def _update_seek_display(self, position: float) -> None:
        if self._seeking:
            return
        pct = int(position / self._track_length * 10000) if self._track_length > 0 else 0
        self._slider.setValue(pct)
        self._elapsed_lbl.setText(_fmt(position))
        self._remain_lbl.setText(f"−{_fmt(self._track_length - position)}")

    def _seek_tick(self) -> None:
        """Advance position label by 1 s locally between server pushes."""
        zone = self._roon.active_zone
        if zone and zone.get("state") == "playing":
            pos = float(zone.get("seek_position") or 0)
            self._update_seek_display(pos + 1)

    # ── Public update API ─────────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        self._status_lbl.setText(text)

    def update_from_zone(self) -> None:
        """Refresh all controls from the current active zone state."""
        zone = self._roon.active_zone
        if not zone:
            self._title_lbl.setText("Not Playing")
            self._sub_lbl.setText("")
            self._elapsed_lbl.setText("—:——")
            self._remain_lbl.setText("—:——")
            self._slider.setValue(0)
            self._clear_artwork()
            return

        state = zone.get("state", "stopped")
        if self._play_btn:
            self._play_btn.setText("⏸" if state == "playing" else "⏯")

        np = zone.get("now_playing")
        if np:
            three = np.get("three_line", {})
            two   = np.get("two_line",   {})
            title  = (three.get("line1") or two.get("line1") or "Unknown Track")
            artist = (three.get("line2") or two.get("line2") or "")
            album  = (three.get("line3") or "")

            self._title_lbl.setText(title)
            self._sub_lbl.setText(" — ".join(filter(None, [artist, album])))

            self._track_length = float(np.get("length") or 0)
            self._update_seek_display(float(zone.get("seek_position") or 0))

            image_key = np.get("image_key")
            if image_key and image_key != self._current_image_key:
                self._current_image_key = image_key
                self._load_artwork(image_key)
        else:
            self._title_lbl.setText("No track info")
            self._sub_lbl.setText("")
            self._clear_artwork()

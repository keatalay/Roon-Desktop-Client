from __future__ import annotations
"""
ui/sidebar.py
iTunes-style source-list sidebar using QListWidget.
Section headers are non-selectable items styled differently.
"""

import logging
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QSizePolicy

from ui import styles

logger = logging.getLogger(__name__)

_SECTION = "section"
_ITEM    = "item"
_ZONE    = "zone"


class Sidebar(QListWidget):
    def __init__(self, on_select, parent=None):
        super().__init__(parent)
        self._on_select = on_select
        self._keys = []       # parallel list of (kind, key) per row

        self.setObjectName("sidebar")
        self.setFixedWidth(styles.SIDEBAR_WIDTH if hasattr(styles, "SIDEBAR_WIDTH") else 170)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.currentRowChanged.connect(self._on_row_changed)

        self._build_static()

    def _add_section(self, text):
        item = QListWidgetItem(text.upper())
        item.setFlags(Qt.ItemFlag.NoItemFlags)          # not selectable
        f = item.font()
        f.setPointSize(9)
        f.setBold(True)
        item.setFont(f)
        item.setForeground(QColor(styles.TEXT_SECONDARY))
        self.addItem(item)
        self._keys.append((_SECTION, ""))

    def _add_item(self, label, key, kind=_ITEM):
        item = QListWidgetItem(f"  {label}")
        self.addItem(item)
        self._keys.append((kind, key))
        return item

    def _build_static(self):
        self._add_section("Library")
        for label, key in [
            ("Genres",  "genres"),
            ("Artists", "artists"),
            ("Albums",  "albums"),
            ("Songs",   "songs"),
        ]:
            self._add_item(label, key)

        self._playlists_section_row = None   # populated later
        self._zones_section_row = None

    def set_zones(self, zones: dict):
        if self._zones_section_row is None:
            self._add_section("Zones")
            self._zones_section_row = self.count() - 1
        for zone_id, zone in zones.items():
            name = zone.get("display_name", zone_id)
            self._add_item(name, zone_id, kind=_ZONE)

    def select_key(self, key: str):
        for row, (kind, k) in enumerate(self._keys):
            if k == key:
                self.blockSignals(True)
                self.setCurrentRow(row)
                self.blockSignals(False)
                break

    def _on_row_changed(self, row):
        if row < 0 or row >= len(self._keys):
            return
        kind, key = self._keys[row]
        if kind == _SECTION or not key:
            return
        if kind == _ZONE:
            self._on_select(f"zone:{key}")
        else:
            self._on_select(key)

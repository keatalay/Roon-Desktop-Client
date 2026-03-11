from __future__ import annotations
"""
ui/library.py
iTunes-style three-column library browser (Genres | Artists | Albums)
with a resizable track list pane below.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QListWidget, QListWidgetItem,
    QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from browse_manager import BrowseItem
from ui import styles

if TYPE_CHECKING:
    from browse_manager import BrowseManager
    from roon_manager import RoonManager

logger = logging.getLogger(__name__)


class ColumnList(QWidget):
    """One column of the three-column browser."""

    def __init__(self, header: str, parent=None):
        super().__init__(parent)
        self._items = []
        self._on_select = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel(header)
        hdr.setStyleSheet(
            f"background-color: {styles.HEADER_BG}; color: {styles.TEXT}; "
            "font-size: 11px; "
            f"border-bottom: 1px solid {styles.SEPARATOR}; padding: 3px 8px;"
        )
        layout.addWidget(hdr)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, stretch=1)

    def set_on_select(self, fn):
        self._on_select = fn

    def populate(self, items, label=""):
        self._list.blockSignals(True)
        self._list.clear()
        self._items = [None] + list(items)
        all_text = f"All ({len(items)} {label})" if label else f"All ({len(items)})"
        all_wi = QListWidgetItem(all_text)
        f = all_wi.font(); f.setItalic(True); all_wi.setFont(f)
        self._list.addItem(all_wi)
        for bi in items:
            self._list.addItem(bi.title)
        self._list.setCurrentRow(0)
        self._list.blockSignals(False)

    def select_all(self):
        self._list.blockSignals(True)
        self._list.setCurrentRow(0)
        self._list.blockSignals(False)

    def selected_item(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _on_row_changed(self, row):
        if self._on_select and row >= 0:
            item = self._items[row] if row < len(self._items) else None
            self._on_select(item)


class TrackList(QWidget):
    HEADERS = ("#", "Name", "Artist", "Album", "Time")
    WIDTHS  = (30,  280,    160,      160,      50)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks = []
        self._on_activate = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {styles.SEPARATOR};")
        layout.addWidget(line)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(self.HEADERS))
        self._tree.setHeaderLabels(self.HEADERS)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemActivated.connect(self._on_item_activated)

        hdr = self._tree.header()
        hdr.setStretchLastSection(False)
        for i, w in enumerate(self.WIDTHS):
            hdr.resizeSection(i, w)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._tree, stretch=1)

    def set_on_activate(self, fn):
        self._on_activate = fn

    def populate(self, tracks):
        self._tracks = tracks
        self._tree.clear()
        for i, t in enumerate(tracks):
            parts = t.subtitle.split(" \u2022 ") if t.subtitle else []
            artist = parts[0].strip() if parts else ""
            album  = parts[1].strip() if len(parts) > 1 else ""
            item = QTreeWidgetItem([str(i + 1), t.title, artist, album, ""])
            item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
            self._tree.addTopLevelItem(item)

    def _on_item_activated(self, item, _col):
        row = self._tree.indexOfTopLevelItem(item)
        if 0 <= row < len(self._tracks) and self._on_activate:
            self._on_activate(self._tracks[row])


class LibraryBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._browse = None
        self._roon = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._vsplit = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(self._vsplit)

        browser_widget = QWidget()
        bh = QHBoxLayout(browser_widget)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        # Narrowed to Artists / Albums only
        self._artist_col = ColumnList("Artists")
        self._album_col  = ColumnList("Albums")

        self._artist_col.set_on_select(self._on_artist_select)
        self._album_col.set_on_select(self._on_album_select)

        for col, is_last in [
            (self._artist_col, False), (self._album_col, True)
        ]:
            bh.addWidget(col, stretch=1)
            if not is_last:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet(f"color: {styles.SEPARATOR};")
                bh.addWidget(sep)

        self._vsplit.addWidget(browser_widget)

        self._track_list = TrackList()
        self._track_list.set_on_activate(self._on_track_activate)
        self._vsplit.addWidget(self._track_list)
        self._vsplit.setSizes([200, 300])

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setParent(self)
        self._status_lbl.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._status_lbl.setGeometry(0, 0, self.width(), self.height())

    def set_browse_manager(self, browse, roon):
        self._browse = browse
        self._roon = roon

    def set_status(self, text):
        self._status_lbl.setText(text)
        if text:
            self._status_lbl.show()
            self._status_lbl.raise_()
        else:
            self._status_lbl.hide()

    def refresh_all(self):
        if not self._browse:
            return
        self._artist_col.populate(self._browse.all_artists, "Artists")
        self._album_col.populate(self._browse.all_albums, "Albums")
        self._track_list.populate([])

    def refresh_artists(self):
        if not self._browse:
            return
        self._artist_col.populate(self._browse.visible_artists, "Artists")
        self._artist_col.select_all()
        self._album_col.populate(self._browse.visible_albums, "Albums")
        self._album_col.select_all()
        self._track_list.populate([])

    def refresh_albums(self):
        if not self._browse:
            return
        self._album_col.populate(self._browse.visible_albums, "Albums")
        self._album_col.select_all()
        self._track_list.populate([])

    def refresh_tracks(self):
        if not self._browse:
            return
        self._track_list.populate(self._browse.visible_tracks)

    def _on_genre_select(self, item):
        if not self._browse or self._busy:
            return
        self._busy = True
        self.set_status("Loading\u2026")
        self._browse.select_genre(item, on_complete=lambda: QTimer.singleShot(0, self._after_genre))

    def _after_genre(self):
        self._busy = False
        self.set_status("")
        self.refresh_artists()

    def _on_artist_select(self, item):
        if not self._browse or self._busy:
            return
        self._busy = True
        self.set_status("Loading\u2026")
        self._browse.select_artist(item, on_complete=lambda: QTimer.singleShot(0, self._after_artist))

    def _after_artist(self):
        self._busy = False
        self.set_status("")
        self.refresh_albums()

    def _on_album_select(self, item):
        if not self._browse or self._busy:
            return
        if item is None:
            self._track_list.populate([])
            return
        self._busy = True
        self.set_status("Loading tracks\u2026")
        self._browse.select_album(item, on_complete=lambda: QTimer.singleShot(0, self._after_album))

    def _after_album(self):
        self._busy = False
        self.set_status("")
        self.refresh_tracks()

    def _on_track_activate(self, track):
        if self._roon and track.item_key:
            self._roon.play_browse_item(track.item_key)

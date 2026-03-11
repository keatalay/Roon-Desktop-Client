from __future__ import annotations
"""
ui/main_window.py
Composes the full application window: player bar, sidebar, library browser.
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QMainWindow,
    QMessageBox, QSplitter, QWidget,
)

from roonapi import RoonDiscovery
from browse_manager import BrowseManager
from roon_manager import RoonManager
from ui import styles
from ui.connection_dialog import ConnectionDialog
from ui.library import LibraryBrowser
from ui.player_bar import PlayerBar
from ui.sidebar import Sidebar
from ui.signals import bus

logger = logging.getLogger(__name__)

_WAITING_MSG = (
    "Waiting for extension approval in Roon…\n\n"
    "Open Roon → Settings → Extensions\n"
    "and click Enable next to 'Roon Desktop Client'.\n\n"
    "This only needs to be done once."
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._roon = RoonManager()
        self._browse = None

        self.setWindowTitle("Roon")
        self.resize(1100, 720)
        self.setMinimumSize(900, 580)

        self._build_ui()

        # Wire the shared signal bus
        bus.zone_changed.connect(self._on_zone_changed)
        bus.library_loaded.connect(self._on_library_loaded)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {styles.WINDOW_BG};")

        from PyQt6.QtWidgets import QVBoxLayout
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Player bar
        self._player = PlayerBar(self._roon)
        vbox.addWidget(self._player)

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {styles.SEPARATOR}; background: {styles.SEPARATOR};")
        sep.setFixedHeight(1)
        vbox.addWidget(sep)

        # Content: sidebar + library in a horizontal splitter
        self._hsplit = QSplitter(Qt.Orientation.Horizontal)
        vbox.addWidget(self._hsplit, stretch=1)

        self._sidebar = Sidebar(on_select=self._on_sidebar_select)
        self._hsplit.addWidget(self._sidebar)

        self._library = LibraryBrowser()
        self._hsplit.addWidget(self._library)

        self._hsplit.setStretchFactor(0, 0)
        self._hsplit.setStretchFactor(1, 1)
        self._hsplit.setSizes([170, 930])

    # ── Application start ─────────────────────────────────────────────────────

    def start(self):
        """
        Start the app by:
          1. Reconnecting to a previously known Core, or
          2. Auto-discovering a Core on the LAN, or
          3. Falling back to the manual connection dialog.
        """
        # 1) Reuse previously approved Core if we have one
        if self._roon.saved_host and self._roon.saved_port:
            logger.info(
                "Reconnecting to saved Roon Core at %s:%s",
                self._roon.saved_host,
                self._roon.saved_port,
            )
            self._connect_to_core(self._roon.saved_host, self._roon.saved_port)
            return

        # 2) Try automatic discovery (no UI needed if this succeeds)
        host = None
        port = None
        try:
            disc = RoonDiscovery(None)
            host, port = disc.first()  # blocks ≤ 5 s
            disc.stop()
        except OSError:
            # Multicast not available (VPN, firewall, etc.) — fall back to dialog.
            host = port = None

        if host and port:
            logger.info("Auto-discovered Roon Core at %s:%s", host, port)
            self._connect_to_core(host, int(port))
            return

        # 3) Fallback: show connection dialog (which itself will try discovery)
        dlg = ConnectionDialog(
            saved_host=None,
            saved_port=None,
            parent=self,
        )
        if dlg.exec() != ConnectionDialog.DialogCode.Accepted:
            import sys
            sys.exit(0)  # user cancelled

        self._connect_to_core(dlg.host, dlg.port)

    def _connect_to_core(self, host: str, port: int) -> None:
        """Kick off an async connection to the given Core."""
        self._player.set_status("Waiting for Roon approval…")
        self._library.set_status(_WAITING_MSG)
        self._roon.connect_async(
            host=host,
            port=port,
            on_success=self._on_connected_bg,
            on_failure=self._on_failed_bg,
        )

    # Called from background thread — emit signal to reach main thread
    def _on_connected_bg(self):
        bus.zone_changed.emit("connected", [])

    def _on_failed_bg(self, error):
        bus.zone_changed.emit(f"__failed__{error}", [])

    # ── Roon event handlers (main thread via signal bus) ──────────────────────

    def _on_zone_changed(self, event: str, zone_ids: list):
        if event == "connected":
            self._handle_connected()
        elif event.startswith("__failed__"):
            self._handle_failed(event[len("__failed__"):])
        else:
            self._player.update_from_zone()

    def _handle_connected(self):
        logger.info("Connected to Roon Core.")
        self._player.set_status("Connected")
        self._library.set_status("Loading library…")

        self._sidebar.set_zones(self._roon.zones)
        self._roon.add_state_callback(
            lambda ev, ids: bus.zone_changed.emit(ev, ids)
        )
        self._player.update_from_zone()

        self._browse = BrowseManager(self._roon)
        zone_id = self._roon.active_zone_id
        if zone_id:
            self._browse.set_zone_id(zone_id)

        self._browse.load_library(
            on_complete=lambda success=True: bus.library_loaded.emit(success)
        )

    def _handle_failed(self, error: str):
        self._player.set_status("Not connected")
        self._library.set_status("")
        QMessageBox.critical(
            self,
            "Roon Connection Failed",
            f"Could not connect to Roon Core:\n\n{error}\n\n"
            "Make sure Roon is running on your network, then restart this app.\n"
            "On first launch, enable 'Roon Desktop Client' in\n"
            "Roon → Settings → Extensions.",
        )

    def _on_library_loaded(self, success: bool):
        if not success:
            self._library.set_status("Library load failed — check Roon connection.")
            return
        self._library.set_status("")
        self._library.set_browse_manager(self._browse, self._roon)
        self._library.refresh_all()
        self._sidebar.select_key("genres")

    # ── Sidebar navigation ────────────────────────────────────────────────────

    def _on_sidebar_select(self, key: str):
        if key.startswith("zone:"):
            zone_id = key[5:]
            self._roon.set_zone(zone_id)
            if self._browse:
                self._browse.set_zone_id(zone_id)
            self._player.update_from_zone()

from __future__ import annotations
"""
ui/connection_dialog.py
Shown on startup: auto-discovers Roon Core via SOOD multicast, with a
manual-entry fallback for networks where multicast is blocked.
"""

import threading
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QVBoxLayout,
)

from roonapi import RoonDiscovery
from ui import styles


class ConnectionDialog(QDialog):
    """
    Modal dialog that:
      1. Runs RoonDiscovery in a background thread.
      2. Pre-fills host/port if discovery succeeds.
      3. Lets the user enter the address manually if not.
      4. Returns .host / .port after the user clicks Connect.
    """

    _sig_discovered = pyqtSignal(str, int)   # host, port
    _sig_not_found  = pyqtSignal()

    def __init__(self, saved_host: str | None = None,
                 saved_port: int | None = None,
                 parent=None):
        super().__init__(parent)
        self._result_host: str | None = None
        self._result_port: int | None = None

        self.setWindowTitle("Connect to Roon Core")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._sig_discovered.connect(self._on_discovered)
        self._sig_not_found.connect(self._on_not_found)

        self._build()

        if saved_host and saved_port:
            # Reconnect to a previously known Core immediately
            self._host_edit.setText(saved_host)
            self._port_edit.setText(str(saved_port))
            self._set_status(f"Using saved address: {saved_host}:{saved_port}", ok=True)
            self._connect_btn.setEnabled(True)
            self._progress.hide()
        else:
            self._start_discovery()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("<b>Connect to Roon Core</b>")
        title.setStyleSheet("font-size: 14px;")
        root.addWidget(title)

        self._status_lbl = QLabel("Searching for Roon Core on your local network…")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color: {styles.TEXT_SECONDARY}; font-size: 11px;")
        root.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)          # indeterminate spinner
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        # Manual entry row
        manual_lbl = QLabel("Roon Core address (fill in if not found automatically):")
        manual_lbl.setStyleSheet("margin-top: 6px;")
        root.addWidget(manual_lbl)

        addr_row = QHBoxLayout()
        addr_row.setSpacing(6)

        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("IP address  e.g. 192.168.1.50")
        self._host_edit.textChanged.connect(self._update_connect_btn)
        addr_row.addWidget(self._host_edit, stretch=4)

        addr_row.addWidget(QLabel("Port:"))

        self._port_edit = QLineEdit("9100")
        self._port_edit.setFixedWidth(64)
        self._port_edit.textChanged.connect(self._update_connect_btn)
        addr_row.addWidget(self._port_edit)

        root.addLayout(addr_row)

        # Help text
        note = QLabel(
            "<small>After connecting, switch to <b>Roon → Settings → Extensions</b>"
            " and click <b>Enable</b> next to <i>Roon Desktop Client</i>.<br>"
            "You only need to do this once.</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {styles.TEXT_SECONDARY};")
        root.addWidget(note)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setEnabled(False)
        self._connect_btn.setDefault(True)
        self._connect_btn.setStyleSheet(
            f"background-color: {styles.SELECTION_BG}; color: white; "
            "padding: 4px 16px; border-radius: 4px;"
        )
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        btn_row.addWidget(self._connect_btn)

        root.addLayout(btn_row)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _start_discovery(self) -> None:
        def _worker():
            try:
                disc = RoonDiscovery(None)
                host, port = disc.first()     # blocks ≤ 5 s
                disc.stop()
                if host:
                    self._sig_discovered.emit(host, int(port))
                else:
                    self._sig_not_found.emit()
            except OSError:
                # Multicast not available on this network (VPN, firewall, etc.)
                self._sig_not_found.emit()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_discovered(self, host: str, port: int) -> None:
        self._host_edit.setText(host)
        self._port_edit.setText(str(port))
        self._set_status(f"Found Roon Core at {host}:{port}", ok=True)
        self._progress.hide()
        self._connect_btn.setEnabled(True)

    def _on_not_found(self) -> None:
        self._set_status(
            "Auto-discovery unavailable on this network (multicast may be blocked).\n"
            "Enter the IP address of the machine running Roon Core below.\n"
            "You can find it in Roon → About → Version.",
            ok=False,
        )
        self._progress.hide()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, ok: bool) -> None:
        colour = styles.TEXT if ok else "#C0392B"
        self._status_lbl.setStyleSheet(f"color: {colour}; font-size: 11px;")
        self._status_lbl.setText(text)

    def _update_connect_btn(self) -> None:
        host = self._host_edit.text().strip()
        port = self._port_edit.text().strip()
        self._connect_btn.setEnabled(bool(host) and port.isdigit() and int(port) > 0)

    def _on_connect_clicked(self) -> None:
        self._result_host = self._host_edit.text().strip()
        try:
            self._result_port = int(self._port_edit.text().strip())
        except ValueError:
            self._result_port = 9100
        self.accept()

    # ── Result ────────────────────────────────────────────────────────────────

    @property
    def host(self) -> str | None:
        return self._result_host

    @property
    def port(self) -> int | None:
        return self._result_port

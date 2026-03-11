from __future__ import annotations
"""
ui/signals.py
Module-level signal bus for safe cross-thread → main-thread communication.

Because PyQt6 uses Qt's AutoConnection, any signal emitted from a background
thread is automatically queued and delivered on the receiver's thread (main).
"""

from PyQt6.QtCore import QObject, pyqtSignal


class _SignalBus(QObject):
    zone_changed   = pyqtSignal(str, list)   # (event, changed_zone_ids)
    library_loaded = pyqtSignal(bool)         # success flag


# Single instance created on import (always on the main thread).
bus = _SignalBus()

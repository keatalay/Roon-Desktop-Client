from __future__ import annotations
"""
roon_manager.py
Handles the Roon Core connection, transport controls, and raw browse API.
"""

import json
import logging
import threading
from pathlib import Path

from roonapi import RoonApi, RoonDiscovery

logger = logging.getLogger(__name__)

APPINFO = {
    "extension_id": "com.roon_desktop_client.v1",
    "display_name": "Roon Desktop Client",
    "display_version": "1.0.0",
    "publisher": "Roon Desktop Client",
    "email": "roon@localhost",
    "website": "https://localhost",
}

TOKEN_PATH = Path.home() / ".roon_desktop_client.json"


class RoonManager:
    """Wraps the roonapi library with a clean interface."""

    def __init__(self):
        self._api: RoonApi | None = None
        self._token: str | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._active_zone_id: str | None = None
        self._state_callbacks: list = []
        self._connected = False
        self._browse_lock = threading.Lock()
        self._load_saved_config()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_saved_config(self) -> None:
        if TOKEN_PATH.exists():
            try:
                data = json.loads(TOKEN_PATH.read_text())
                self._token = data.get("token")
                self._host = data.get("host")
                self._port = data.get("port")
                logger.info("Loaded saved Roon config.")
            except Exception as e:
                logger.warning("Could not load saved config: %s", e)

    def _save_config(self) -> None:
        if self._api and self._api.token:
            data = {
                "token": self._api.token,
                "host": self._host,
                "port": self._port,
            }
            try:
                TOKEN_PATH.write_text(json.dumps(data))
            except Exception as e:
                logger.warning("Could not save config: %s", e)

    # ── Connection ───────────────────────────────────────────────────────────

    def add_state_callback(self, callback) -> None:
        """Register fn(event: str, changed_zone_ids: list) called on zone changes."""
        self._state_callbacks.append(callback)

    def connect_async(self, host: str, port: int,
                      on_success=None, on_failure=None) -> None:
        """Connect to a known Roon Core address in a background thread."""
        self._host = host
        self._port = port
        t = threading.Thread(
            target=self._connect_thread,
            args=(on_success, on_failure),
            daemon=True,
        )
        t.start()

    def _connect_thread(self, on_success, on_failure) -> None:
        try:
            # Connect and wait for extension approval in Roon → Settings → Extensions.
            # blocking_init=True blocks until the user enables the extension.
            logger.info(
                "Connecting to Roon Core at %s:%s — "
                "enable 'Roon Desktop Client' in Roon → Settings → Extensions if prompted",
                self._host, self._port,
            )
            self._api = RoonApi(
                APPINFO,
                self._token,
                self._host,
                self._port,
                blocking_init=True,
            )
            self._connected = True
            self._save_config()
            self._api.register_state_callback(self._on_roon_state)
            # Pick first available zone as default
            if self._api.zones:
                self._active_zone_id = list(self._api.zones.keys())[0]
            if on_success:
                on_success()
        except Exception as e:
            logger.error("Connection failed: %s", e)
            if on_failure:
                on_failure(str(e))

    def _on_roon_state(self, event: str, changed_zone_ids: list) -> None:
        if not self._active_zone_id and self._api and self._api.zones:
            self._active_zone_id = list(self._api.zones.keys())[0]
        for cb in self._state_callbacks:
            try:
                cb(event, changed_zone_ids)
            except Exception as e:
                logger.error("State callback error: %s", e)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected and self._api is not None

    @property
    def zones(self) -> dict:
        return self._api.zones if self._api else {}

    @property
    def active_zone(self) -> dict | None:
        if self._api and self._active_zone_id:
            return self._api.zones.get(self._active_zone_id)
        return None

    @property
    def active_zone_id(self) -> str | None:
        return self._active_zone_id

    @property
    def saved_host(self) -> str | None:
        return self._host

    @property
    def saved_port(self) -> int | None:
        return self._port

    def set_zone(self, zone_id: str) -> None:
        self._active_zone_id = zone_id

    # ── Transport ─────────────────────────────────────────────────────────────

    def play_pause(self) -> None:
        if self._api and self._active_zone_id:
            self._api.playback_control(self._active_zone_id, "playpause")

    def stop(self) -> None:
        if self._api and self._active_zone_id:
            self._api.playback_control(self._active_zone_id, "stop")

    def next_track(self) -> None:
        if self._api and self._active_zone_id:
            self._api.playback_control(self._active_zone_id, "next")

    def prev_track(self) -> None:
        if self._api and self._active_zone_id:
            self._api.playback_control(self._active_zone_id, "previous")

    def seek(self, position_seconds: float) -> None:
        """Seek to an absolute position (seconds)."""
        if self._api and self._active_zone_id:
            self._api.seek(self._active_zone_id, "absolute", int(position_seconds))

    def seek_relative(self, delta_seconds: int) -> None:
        """Seek forward (+) or backward (-) by delta_seconds."""
        if self._api and self._active_zone_id:
            self._api.seek(self._active_zone_id, "relative", delta_seconds)

    # ── Images ────────────────────────────────────────────────────────────────

    def get_image(self, image_key: str, width: int = 200, height: int = 200) -> bytes | None:
        """Return raw image bytes for a given image_key, or None on failure."""
        if not self._api or not image_key:
            return None
        try:
            return self._api.get_image(image_key, scale="fit", width=width, height=height)
        except Exception as e:
            logger.warning("Could not fetch image %s: %s", image_key, e)
            return None

    # ── Browse primitives ─────────────────────────────────────────────────────

    def browse_navigate(self, opts: dict) -> dict | None:
        """Thread-safe browse_browse call."""
        if not self._api:
            return None
        with self._browse_lock:
            try:
                return self._api.browse_browse(opts)
            except Exception as e:
                logger.error("browse_browse error: %s", e)
                return None

    def browse_load(self, opts: dict) -> dict | None:
        """Thread-safe browse_load call."""
        if not self._api:
            return None
        with self._browse_lock:
            try:
                return self._api.browse_load(opts)
            except Exception as e:
                logger.error("browse_load error: %s", e)
                return None

    def play_browse_item(self, item_key: str) -> None:
        """
        Attempt to play a browse item. If the item is an action_list (e.g. an
        album), Roon will queue the default action (usually Play Now).
        """
        if not self._api or not self._active_zone_id:
            return
        t = threading.Thread(
            target=self._play_item_thread,
            args=(item_key,),
            daemon=True,
        )
        t.start()

    def _play_item_thread(self, item_key: str) -> None:
        base = {"hierarchy": "browse", "zone_or_output_id": self._active_zone_id}
        with self._browse_lock:
            try:
                result = self._api.browse_browse({**base, "item_key": item_key})
                if not result:
                    return
                if result.get("action") == "list":
                    # Look for a Play action in the list
                    level = result["list"]["level"]
                    load_result = self._api.browse_load({
                        **base, "level": level, "offset": 0, "count": 5
                    })
                    if load_result:
                        for item in load_result.get("items", []):
                            title = item.get("title", "").lower()
                            if item.get("hint") == "action" and (
                                "play" in title or "queue" in title
                            ):
                                self._api.browse_browse(
                                    {**base, "item_key": item["item_key"]}
                                )
                                break
            except Exception as e:
                logger.error("play_item_thread error: %s", e)

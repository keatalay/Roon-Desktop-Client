from __future__ import annotations
"""
browse_manager.py
iTunes-style three-column library navigation using Roon's browse API.

Column mapping:
  Genre column  →  Artist column  →  Album column  →  Track list
All selections default to "All" which means no filter.
"""

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class BrowseItem:
    """Lightweight container for a browse list entry."""
    __slots__ = ("title", "subtitle", "item_key", "hint", "image_key")

    def __init__(self, raw):
        """
        Wrap a single Roon browse item.

        Newer Roon builds sometimes return plain strings or other primitives in
        places where we previously always saw dicts.  Be defensive here so that
        odd items do not crash the browser.
        """
        if isinstance(raw, dict):
            self.title: str = raw.get("title", "") or ""
            self.subtitle: str = raw.get("subtitle", "") or ""
            self.item_key: str = raw.get("item_key", "") or ""
            self.hint: str = raw.get("hint", "") or ""
            self.image_key: str = raw.get("image_key", "") or ""
        else:
            # Fallback for unexpected item shapes (e.g. plain strings)
            self.title = str(raw)
            self.subtitle = ""
            self.item_key = ""
            self.hint = ""
            self.image_key = ""

    def __repr__(self):
        return f"<BrowseItem '{self.title}'>"


class BrowseManager:
    """
    Navigates Roon's hierarchical browse API to expose a flat
    Genre / Artist / Album / Track view (iTunes column browser style).
    """

    def __init__(self, roon_manager):
        self._roon = roon_manager
        self._zone_id: str | None = None

        # Full library data (loaded once)
        self.all_genres: list[BrowseItem] = []
        self.all_artists: list[BrowseItem] = []
        self.all_albums: list[BrowseItem] = []
        self.all_tracks: list[BrowseItem] = []

        # Current filtered view
        self.visible_artists: list[BrowseItem] = []
        self.visible_albums: list[BrowseItem] = []
        self.visible_tracks: list[BrowseItem] = []

        # Current selections (None = All)
        self.selected_genre: BrowseItem | None = None
        self.selected_artist: BrowseItem | None = None
        self.selected_album: BrowseItem | None = None

    def set_zone_id(self, zone_id: str) -> None:
        self._zone_id = zone_id

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _base_opts(self, **extra) -> dict:
        opts = {"hierarchy": "browse"}
        if self._zone_id:
            opts["zone_or_output_id"] = self._zone_id
        opts.update(extra)
        return opts

    def _nav(self, **kwargs) -> dict | None:
        return self._roon.browse_navigate(self._base_opts(**kwargs))

    def _load_all(self, level: int, page_size: int = 500) -> list[BrowseItem]:
        """Load every item at *level*, paginating as needed."""
        items: list[BrowseItem] = []
        offset = 0
        while True:
            result = self._roon.browse_load(
                self._base_opts(level=level, offset=offset, count=page_size)
            )
            if not result:
                break
            batch = result.get("items", []) or []
            for raw in batch:
                if not isinstance(raw, dict):
                    # Ignore unsupported shapes (e.g. plain strings)
                    continue
                if not raw.get("item_key"):
                    continue
                items.append(BrowseItem(raw))
            total = result.get("list", {}).get("count", 0)
            offset += len(batch)
            if offset >= total or not batch:
                break
        return items

    def _find_item(self, items: list[BrowseItem], keyword: str) -> BrowseItem | None:
        kw = keyword.lower()
        for item in items:
            if kw in item.title.lower():
                return item
        return None

    # ── Top-level navigation helpers ─────────────────────────────────────────

    def _go_root(self) -> int | None:
        """Pop all and return the root browse level number."""
        result = self._nav(pop_all=True)
        if result and result.get("action") == "list":
            return result["list"]["level"]
        return None

    def _go_library(self) -> int | None:
        """Navigate to My Library, return level number."""
        root_level = self._go_root()
        if root_level is None:
            return None
        root_items = self._load_all(root_level, page_size=20)
        lib = self._find_item(root_items, "library")
        if not lib:
            # Fallback: pick the first list-hint item
            lib = next((i for i in root_items if i.hint == "list"), None)
        if not lib:
            logger.warning("Cannot find Library node. Available: %s", root_items)
            return None
        result = self._nav(item_key=lib.item_key)
        if isinstance(result, dict) and result.get("action") == "list":
            return result["list"]["level"]
        return None

    def _go_library_section(self, section_name: str) -> tuple[list[BrowseItem], int] | tuple[list, None]:
        """
        From Library root, navigate into *section_name* (e.g. 'Genres',
        'Artists', 'Albums') and return (items, level).
        """
        lib_level = self._go_library()
        if lib_level is None:
            return [], None
        lib_items = self._load_all(lib_level, page_size=30)
        section = self._find_item(lib_items, section_name)
        if not section:
            logger.warning("Cannot find '%s'. Available: %s", section_name, lib_items)
            return [], None
        result = self._nav(item_key=section.item_key)
        if isinstance(result, dict) and result.get("action") == "list":
            level = result["list"]["level"]
            return self._load_all(level), level
        return [], None

    # ── Public API: initial library load ─────────────────────────────────────

    def load_library(self, on_complete: Callable | None = None) -> None:
        """
        Asynchronously load all genres, artists, and albums.
        Calls on_complete(success=True/False) on the caller's side when done
        (caller must marshal to the main thread if needed).
        """
        threading.Thread(
            target=self._load_library_thread,
            args=(on_complete,),
            daemon=True,
        ).start()

    def _load_library_thread(self, on_complete) -> None:
        try:
            # Not all cores expose Genres in the library root; focus on Artists/Albums/Tracks.
            self.all_genres = []

            artists, _ = self._go_library_section("Artists")
            self.all_artists = artists

            albums, _ = self._go_library_section("Albums")
            self.all_albums = albums

            tracks, _ = self._go_library_section("Tracks")
            self.all_tracks = tracks

            self.visible_artists = list(self.all_artists)
            self.visible_albums = list(self.all_albums)
            self.visible_tracks = []

            logger.info(
                "Library loaded: %d genres, %d artists, %d albums, %d tracks",
                len(self.all_genres), len(self.all_artists),
                len(self.all_albums), len(self.all_tracks),
            )
            if on_complete:
                on_complete(success=True)
        except Exception as e:
            logger.error("load_library error: %s", e)
            if on_complete:
                on_complete(success=False)

    # ── Public API: column selections ────────────────────────────────────────

    def select_genre(self, genre: BrowseItem | None, on_complete: Callable | None = None) -> None:
        """
        Filter the Artist column by *genre*.  Pass None to reset to 'All'.
        """
        self.selected_genre = genre
        self.selected_artist = None
        self.selected_album = None
        self.visible_tracks = []

        if genre is None:
            self.visible_artists = list(self.all_artists)
            self.visible_albums = list(self.all_albums)
            if on_complete:
                on_complete()
            return

        threading.Thread(
            target=self._filter_artists_by_genre,
            args=(genre, on_complete),
            daemon=True,
        ).start()

    def _filter_artists_by_genre(self, genre: BrowseItem, on_complete) -> None:
        try:
            # Navigate: root → library → Genres → <genre>
            lib_level = self._go_library()
            if lib_level is None:
                self.visible_artists = list(self.all_artists)
                if on_complete:
                    on_complete()
                return

            lib_items = self._load_all(lib_level, page_size=30)
            genres_item = self._find_item(lib_items, "Genre")
            if not genres_item:
                self.visible_artists = list(self.all_artists)
                if on_complete:
                    on_complete()
                return

            # Enter Genres
            result = self._nav(item_key=genres_item.item_key)
            if not isinstance(result, dict) or result.get("action") != "list":
                self.visible_artists = list(self.all_artists)
                if on_complete:
                    on_complete()
                return

            # Enter the specific genre
            result = self._nav(item_key=genre.item_key)
            if not isinstance(result, dict) or result.get("action") != "list":
                self.visible_artists = list(self.all_artists)
                if on_complete:
                    on_complete()
                return

            level = result["list"]["level"]
            genre_contents = self._load_all(level, page_size=20)

            # Genre may expose Artists as a sub-section, or directly artists
            artists_node = self._find_item(genre_contents, "Artist")
            if artists_node:
                result = self._nav(item_key=artists_node.item_key)
                if isinstance(result, dict) and result.get("action") == "list":
                    level = result["list"]["level"]
                    self.visible_artists = self._load_all(level)
                else:
                    self.visible_artists = [
                        i for i in genre_contents
                        if i.hint in ("list", "action_list") and i.item_key
                    ]
            else:
                # Contents are directly artists
                self.visible_artists = [
                    i for i in genre_contents if i.hint in ("list", "action_list")
                ]

            self.visible_albums = list(self.all_albums)

        except Exception as e:
            logger.error("_filter_artists_by_genre error: %s", e)
            self.visible_artists = list(self.all_artists)
            self.visible_albums = list(self.all_albums)
        finally:
            if on_complete:
                on_complete()

    def select_artist(self, artist: BrowseItem | None, on_complete: Callable | None = None) -> None:
        """
        Filter the Album column by *artist*.  Pass None to reset to 'All'.

        Instead of relying on deep browse navigation (which can vary between
        cores), we filter the already-loaded Albums section by matching the
        artist's name in each album's subtitle/title.
        """
        self.selected_artist = artist
        self.selected_album = None
        self.visible_tracks = []

        if artist is None:
            self.visible_albums = list(self.all_albums)
            if on_complete:
                on_complete()
            return

        name = (artist.title or "").lower()
        visible: list[BrowseItem] = []
        for alb in self.all_albums:
            haystack = f"{alb.title} {alb.subtitle}".lower()
            if name and name in haystack:
                visible.append(alb)

        # Fallback: if we didn't match anything, keep all albums so the UI
        # doesn't look empty; this is better than a blank column.
        self.visible_albums = visible or list(self.all_albums)

        if on_complete:
            on_complete()

    def select_album(self, album: BrowseItem | None, on_complete: Callable | None = None) -> None:
        """
        Load tracks for *album* using the pre-loaded Tracks library section.
        Pass None to clear the track list.
        """
        self.selected_album = album
        self.visible_tracks = []

        if album is None:
            if on_complete:
                on_complete()
            return

        if not self.all_tracks:
            logger.warning(
                "select_album: all_tracks is empty when selecting album '%s'",
                album.title,
            )
            if on_complete:
                on_complete()
            return

        album_name = (album.title or "").lower()

        candidates: list[BrowseItem] = []
        for t in self.all_tracks:
            haystack = f"{t.title} {t.subtitle}".lower()
            if album_name and album_name in haystack:
                candidates.append(t)

        self.visible_tracks = candidates

        logger.info(
            "select_album: filtered %d tracks for album '%s'",
            len(self.visible_tracks), album.title,
        )

        if on_complete:
            on_complete()

from __future__ import annotations
"""
ui/styles.py
Qt stylesheet and palette constants matching an iTunes-like aesthetic.
"""

# ── Raw colour tokens ──────────────────────────────────────────────────────────
WINDOW_BG       = "#FFFFFF"
PLAYER_BG       = "#F5F5F5"
SIDEBAR_BG      = "#F2F2F2"
BROWSER_BG      = "#FFFFFF"
HEADER_BG       = "#EBEBEB"

TEXT            = "#1D1D1F"
TEXT_SECONDARY  = "#6E6E73"
TEXT_DISABLED   = "#AEAEB2"

SELECTION_BG    = "#3478F6"
SELECTION_FG    = "#FFFFFF"

BORDER          = "#D1D1D6"
SEPARATOR       = "#C7C7CC"

TRACK_ROW_ALT   = "#F7F7F7"
TRACK_PLAYING   = "#EBF3FF"
ARTWORK_PLACEHOLDER = "#C7C7CC"

# ── Global Qt stylesheet ───────────────────────────────────────────────────────
MAIN_STYLESHEET = f"""
/* ── Base ─────────────────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {WINDOW_BG};
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 12px;
    color: {TEXT};
}}

/* ── Splitter handles ─────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {SEPARATOR};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── List widgets (column browser) ───────────────────────────────────────── */
QListWidget {{
    background-color: {BROWSER_BG};
    border: none;
    outline: 0;
}}
QListWidget::item {{
    padding: 1px 6px;
    height: 20px;
}}
QListWidget::item:selected {{
    background-color: {SELECTION_BG};
    color: {SELECTION_FG};
    border-radius: 0px;
}}
QListWidget::item:hover:!selected {{
    background-color: #E5E5EA;
}}

/* ── Tree widget (track list) ─────────────────────────────────────────────── */
QTreeWidget {{
    background-color: {BROWSER_BG};
    alternate-background-color: {TRACK_ROW_ALT};
    border: none;
    outline: 0;
}}
QTreeWidget::item {{
    padding: 1px 4px;
    height: 18px;
}}
QTreeWidget::item:selected {{
    background-color: {SELECTION_BG};
    color: {SELECTION_FG};
}}
QTreeWidget::item:hover:!selected {{
    background-color: #E5E5EA;
}}

/* ── Header views ─────────────────────────────────────────────────────────── */
QHeaderView {{
    background-color: {HEADER_BG};
}}
QHeaderView::section {{
    background-color: {HEADER_BG};
    color: {TEXT};
    border: none;
    border-right: 1px solid {SEPARATOR};
    border-bottom: 1px solid {SEPARATOR};
    padding: 2px 6px;
    font-size: 11px;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ── Scroll bars ──────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #AEAEB2;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #8E8E93;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 8px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: #AEAEB2;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Seek / progress slider ───────────────────────────────────────────────── */
QSlider#seekSlider::groove:horizontal {{
    height: 3px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider#seekSlider::sub-page:horizontal {{
    background: {SELECTION_BG};
    border-radius: 2px;
}}
QSlider#seekSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 1px solid #AEAEB2;
    width: 11px;
    height: 11px;
    margin: -4px 0;
    border-radius: 6px;
}}
QSlider#seekSlider::handle:horizontal:hover {{
    border-color: {SELECTION_BG};
}}

/* ── Transport buttons ────────────────────────────────────────────────────── */
QPushButton#transportBtn {{
    background: transparent;
    border: none;
    color: {TEXT};
    padding: 2px 5px;
    border-radius: 4px;
}}
QPushButton#transportBtn:hover {{
    background: #E0E0E5;
}}
QPushButton#transportBtn:pressed {{
    background: {BORDER};
}}

/* ── Player bar ───────────────────────────────────────────────────────────── */
QWidget#playerBar {{
    background-color: {PLAYER_BG};
    border-bottom: 1px solid {SEPARATOR};
}}
QLabel#playerLabel {{
    background: transparent;
}}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
QListWidget#sidebar {{
    background-color: {SIDEBAR_BG};
    border: none;
    outline: 0;
    font-size: 12px;
}}
QListWidget#sidebar::item {{
    padding: 3px 12px;
    height: 22px;
    color: {TEXT};
}}
QListWidget#sidebar::item:selected {{
    background-color: {SELECTION_BG};
    color: {SELECTION_FG};
}}
QListWidget#sidebar::item[section="true"] {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: bold;
    padding-top: 10px;
}}

/* ── Status / misc labels ─────────────────────────────────────────────────── */
QLabel#statusLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    background: transparent;
}}
"""

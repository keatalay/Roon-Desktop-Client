#!/usr/bin/env python3
"""
main.py – Roon Desktop Client entry point.

Usage:
    bash run.sh        (recommended – sets up venv automatically)
    python main.py     (if dependencies already installed)

Requirements:
    pip install roonapi PyQt6
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("roonapi").setLevel(logging.WARNING)


def _check_deps() -> bool:
    missing = []
    try:
        import roonapi  # noqa: F401
    except ImportError:
        missing.append("roonapi")
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        missing.append("PyQt6")
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Run:  pip install {' '.join(missing)}")
        return False
    return True


def main() -> None:
    if not _check_deps():
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from ui.styles import MAIN_STYLESHEET
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Roon")
    app.setOrganizationName("RoonDesktopClient")
    app.setStyleSheet(MAIN_STYLESHEET)

    # Crisp rendering on Retina / HiDPI
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = MainWindow()
    window.show()
    window.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

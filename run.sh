#!/bin/bash
# run.sh – set up (once) and launch the Roon Desktop Client
#
# Uses Homebrew Python (or the first python3 on PATH).
# PyQt6 bundles its own Qt libraries so no system Tk/X11 is needed.

set -e
cd "$(dirname "$0")"

VENV=".venv"
# Prefer Homebrew Python; fall back to whatever python3 is on PATH
if [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON="/usr/local/bin/python3"
else
    PYTHON="python3"
fi

# Recreate the venv if it was built with a different Python (e.g. old system Python)
if [ -d "$VENV" ] && [ -f "$VENV/bin/python" ]; then
    VENV_PYTHON=$("$VENV/bin/python" -c "import sys; print(sys.executable)" 2>/dev/null || true)
    if [ "$VENV_PYTHON" != "$("$PYTHON" -c "import sys; print(sys.executable)" 2>/dev/null)" ]; then
        echo "Python changed – recreating virtual environment …"
        rm -rf "$VENV"
    fi
fi

# Create virtualenv on first run
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment with $PYTHON …"
    "$PYTHON" -m venv "$VENV"
fi

# Install / upgrade dependencies
echo "Installing dependencies …"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

echo "Starting Roon Desktop Client …"
exec "$VENV/bin/python" main.py "$@"

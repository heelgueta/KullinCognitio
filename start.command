#!/bin/bash
# KullinCognitio launcher — macOS / Linux
# Double-click this file (after `chmod +x start.command` once) to bootstrap
# (.venv + deps) and start the suite.

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo
    echo "  Python no encontrado."
    echo "  Instala Python 3.10+ desde https://www.python.org/downloads/"
    echo "  o ejecuta:  brew install python"
    echo
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar…"
    exit 1
fi

"$PYTHON" run.py "$@"

# Keep the window open if run.py exited with an error
if [ $? -ne 0 ]; then
    read -n 1 -s -r -p "Presiona cualquier tecla para cerrar…"
fi

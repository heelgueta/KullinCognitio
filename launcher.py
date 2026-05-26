"""
MolfunCognitio — suite launcher.

Starts CulpemCorpus, YeneConservatio, and LlallinRelatio as subprocesses,
then serves a dashboard at http://localhost:5000 that monitors them all.

App lookup order per sub-app:
  1. ./<AppName>/              (git submodule — preferred for end users)
  2. ../<AppName>/             (sibling directory — dev workflow)

Ctrl+C cleanly shuts down everything.
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from threading import Thread

import requests
from flask import Flask, jsonify, render_template

HERE           = Path(__file__).parent.resolve()
DASHBOARD_PORT = 5000

APPS = [
    {
        "id":     "culpem",
        "name":   "CulpemCorpus",
        "dir":    "CulpemCorpus",
        "port":   5001,
        "emoji":  "🦊",
        "accent": "#e8733a",
        "desc":   "Scraper de medios para construir corpus académicos",
    },
    {
        "id":     "yene",
        "name":   "YeneConservatio",
        "dir":    "YeneConservatio",
        "port":   5002,
        "emoji":  "🐋",
        "accent": "#2e7fd8",
        "desc":   "Archivo local persistente de medios",
    },
    {
        "id":     "llallin",
        "name":   "LlallinRelatio",
        "dir":    "LlallinRelatio",
        "port":   5003,
        "emoji":  "🕷️",
        "accent": "#3aab8f",
        "desc":   "Red de conceptos desde corpus (Gephi)",
    },
]

processes = []   # (app_id, Popen) tuples


# ── App lookup & launching ────────────────────────────────────────────────────

def find_app_dir(app_dirname: str) -> Path | None:
    """Find an app: submodule path first, then sibling directory."""
    candidates = [HERE / app_dirname, HERE.parent / app_dirname]
    for c in candidates:
        if c.exists() and (c / "app.py").exists():
            return c
    return None


def start_app(app: dict) -> subprocess.Popen | None:
    app_dir = find_app_dir(app["dir"])
    if not app_dir:
        print(f"  ⚠ {app['name']}: no encontrado (ni submodule ni hermano)")
        return None

    log_path = HERE / "logs" / f"{app['id']}.log"
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=str(app_dir),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=open(log_path, "ab"),
        stderr=subprocess.STDOUT,
    )
    location = "submodule" if app_dir.parent == HERE else "hermano"
    print(f"  → {app['emoji']} {app['name']} ({location}, PID {proc.pid}) :{app['port']}")
    return proc


def cleanup():
    if not processes:
        return
    print("\nApagando suite…")
    for _, p in processes:
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                p.kill()
    print("Bye! 🐾")


# ── Dashboard Flask app ───────────────────────────────────────────────────────

flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return render_template("index.html", apps=APPS)


@flask_app.route("/status")
def status():
    result = {}
    for app in APPS:
        app_dir   = find_app_dir(app["dir"])
        installed = app_dir is not None

        running = False
        if installed:
            try:
                r = requests.get(f"http://localhost:{app['port']}/", timeout=0.4)
                running = r.status_code < 500
            except Exception:
                running = False

        result[app["id"]] = {
            "installed": installed,
            "running":   running,
            "location":  str(app_dir.relative_to(HERE.parent)) if app_dir else None,
        }
    return jsonify(result)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    (HERE / "logs").mkdir(exist_ok=True)

    print("🐾 MolfunCognitio — iniciando suite")
    print("=" * 50)

    for app in APPS:
        p = start_app(app)
        if p:
            processes.append((app["id"], p))

    print(f"\n  → 🏠 Dashboard:  http://localhost:{DASHBOARD_PORT}")
    print(f"     Logs en:     {HERE / 'logs'}")
    print("\n  Ctrl+C para detener todo.\n")

    # Open browser after a short delay so apps have time to bind ports
    def _open():
        time.sleep(2.5)
        try: webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
        except Exception: pass
    Thread(target=_open, daemon=True).start()

    try:
        # use_reloader=False to avoid double-spawning child processes
        flask_app.run(host="127.0.0.1", port=DASHBOARD_PORT,
                      debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()

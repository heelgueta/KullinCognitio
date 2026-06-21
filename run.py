"""
KullinCognitio bootstrapper.

Creates a local .venv if missing, installs dependencies, then runs launcher.py.
Cross-platform (Mac / Linux / Windows). Designed to be invoked by the
double-click wrappers (start.bat on Windows, start.command on macOS) so
non-technical users never have to touch a terminal.

Usage:
  python run.py             # bootstrap + launch
  python run.py --reinstall # force re-install of all requirements
"""
import os
import subprocess
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on emojis; reconfigure stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).parent.resolve()
VENV = HERE / ".venv"
MARK = VENV / ".installed"
REQ  = HERE / "requirements.txt"
SUBAPPS = (
    "YeneConservatio", "CulpemCorpus", "LlallinRelatio",
    "ÑarkiMundatio", "MañkeAnalytica", "FiluSententia",
)


def venv_python() -> Path:
    return VENV / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.check_call(cmd, **kw)


def ensure_venv():
    if VENV.exists() and venv_python().exists():
        return
    print(f"Creating virtualenv at {VENV} …")
    run([sys.executable, "-m", "venv", str(VENV)])


def ensure_deps(force: bool = False):
    py = venv_python()
    fresh = force or not MARK.exists()
    if not fresh and REQ.exists() and REQ.stat().st_mtime > MARK.stat().st_mtime:
        fresh = True

    if not fresh:
        return

    print("Installing dependencies (first run takes a minute)…")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    if REQ.exists():
        run([str(py), "-m", "pip", "install", "-r", str(REQ), "--quiet"])
    for sub in SUBAPPS:
        req = HERE / sub / "requirements.txt"
        if req.exists():
            print(f"  … {sub}/requirements.txt")
            run([str(py), "-m", "pip", "install", "-r", str(req), "--quiet"])
    MARK.touch()


def launch():
    py = venv_python()
    print()
    print("=" * 50)
    print("Iniciando KullinCognitio…")
    print("=" * 50)
    # Don't use os.execv on Windows — the wrapper window vanishes.
    # subprocess keeps the parent alive so Ctrl+C stops both cleanly.
    try:
        subprocess.call([str(py), str(HERE / "launcher.py")])
    except KeyboardInterrupt:
        pass


def main():
    force = "--reinstall" in sys.argv
    print("🐾 KullinCognitio")
    print(f"  cwd: {HERE}")
    try:
        ensure_venv()
        ensure_deps(force=force)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR durante setup: {e}")
        try: input("\nPresiona Enter para cerrar… ")
        except EOFError: pass
        sys.exit(1)
    launch()


if __name__ == "__main__":
    main()

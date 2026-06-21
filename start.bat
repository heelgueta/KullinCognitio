@echo off
REM KullinCognitio launcher — Windows
REM Double-click this file to bootstrap (.venv + deps) and start the suite.

cd /d "%~dp0"

REM Prefer the py launcher (handles multiple Python versions); fall back to python.
where py >nul 2>nul
if %errorlevel%==0 (
    py run.py %*
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python run.py %*
    ) else (
        echo.
        echo  Python no encontrado.
        echo  Instala Python 3.10+ desde https://www.python.org/downloads/
        echo  (marca "Add Python to PATH" durante la instalacion)
        echo.
        pause
        exit /b 1
    )
)

REM Keep the window open if run.py exited with an error
if errorlevel 1 pause

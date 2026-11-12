@echo off
rem Windows launcher for the local LAST LIGHT API (counterpart of start.command).
rem Keep this file ASCII-only: cmd misparses UTF-8 batch files.
rem Uses .venv-win, separate from the macOS .venv, because a synced folder cannot share one venv.
setlocal
set "SERVER_DIR=%~dp0"
cd /d "%SERVER_DIR%"

set "PYTHON=%SERVER_DIR%.venv-win\Scripts\python.exe"
"%PYTHON%" -c "import django" >nul 2>&1
if not errorlevel 1 goto run

echo server\.venv-win is missing or broken, running setup_local.py...
where py >nul 2>&1
if errorlevel 1 (
    python "%SERVER_DIR%setup_local.py"
) else (
    py -3 "%SERVER_DIR%setup_local.py"
)
if errorlevel 1 (
    echo Setup failed. Install Python 3.10+ from python.org, check Internet access and try again.
    pause
    exit /b 1
)

:run
"%PYTHON%" -u "%SERVER_DIR%run_local.py" --open %*
set "RC=%errorlevel%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%

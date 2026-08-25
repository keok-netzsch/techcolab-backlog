@echo off
:: TechColab Backlog — Weekly English Coach report
:: Triggered by Windows Task Scheduler every Monday at 08:30.

cd /d "%~dp0"

:: Output is redirected to a log file by the scheduled task, so Python would
:: fall back to the ANSI code page (cp1252). Keep the log UTF-8 and make a
:: non-ASCII print unable to kill the run. See agent/agent_io.py.
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

:: Activate venv if it exists; fall back to system Python otherwise
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [english-coach] .venv not found, using system Python
)

python agent\english_coach.py --days 7

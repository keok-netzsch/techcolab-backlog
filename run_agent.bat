@echo off
:: TechColab Backlog ? Phase 1: Daily analysis + report
:: Triggered by Windows Task Scheduler every morning.

cd /d "%~dp0"

:: stdout is redirected to the log file below, so Python would fall
:: back to the ANSI code page (cp1252) and raise UnicodeEncodeError on any
:: non-ASCII print. Force UTF-8 for this process and every child it spawns.
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

:: Activate venv if it exists; otherwise use system Python (the expected default here)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [agent] Using system Python ^(no .venv; this is the normal setup^)
)

if not exist logs mkdir logs
python -u agent\daily_report.py > "%~dp0logs\agent-last.log" 2>&1

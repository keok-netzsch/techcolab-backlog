@echo off
:: TechColab Backlog ? Phase 1: Daily analysis + report
:: Triggered by Windows Task Scheduler every morning.

cd /d "%~dp0"

:: Activate venv if it exists; fall back to system Python otherwise
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [agent] .venv not found, using system Python
)

if not exist logs mkdir logs
python -u agent\daily_report.py > "%~dp0logs\agent-last.log" 2>&1

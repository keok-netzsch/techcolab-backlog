@echo off
:: TechColab Backlog — Weekly English Coach report
:: Triggered by Windows Task Scheduler every Monday at 08:30.

cd /d "%~dp0"

:: Activate venv if it exists; fall back to system Python otherwise
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [english-coach] .venv not found, using system Python
)

python agent\english_coach.py --days 7

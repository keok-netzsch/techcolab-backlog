@echo off
cd /d "%USERPROFILE%\techcolab-backlog"

:: Output is redirected to a log file by the scheduled task, so Python would
:: fall back to the ANSI code page (cp1252). Keep the log UTF-8 and make a
:: non-ASCII print unable to kill the run. See agent/agent_io.py.
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
call .venv\Scripts\activate.bat
python scripts\recalc_opus_price.py

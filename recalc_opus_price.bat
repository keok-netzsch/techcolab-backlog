@echo off
cd /d "%USERPROFILE%\techcolab-backlog"
call .venv\Scripts\activate.bat
python scripts\recalc_opus_price.py

@echo off
:: TechColab Backlog — Phase 1: Daily analysis + report
:: Triggered by Windows Task Scheduler every morning.

cd /d "%~dp0"
call .venv\Scripts\activate.bat
python agent\daily_report.py

@echo off
:: Entry point kept for the desktop shortcuts, Raycast and install.bat that
:: already point here. The logic lives in scripts\start-app.ps1 — one place that
:: decides, instead of every launcher blindly running `streamlit run` and hoping
:: the port is free. See the header of that script for why.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-app.ps1" %*
exit /b %ERRORLEVEL%

@echo off
cd /d "C:\Users\Kelvin.okuda\techcolab-backlog"

:: Ensure vault path is set even if env var wasn't inherited
if "%TECHCOLAB_VAULT%"=="" (
    set "TECHCOLAB_VAULT=C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO"
)

call .venv\Scripts\activate.bat
streamlit run app.py --server.port 8501 >> "%~dp0streamlit.log" 2>&1

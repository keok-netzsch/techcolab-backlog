@echo off
cd /d "%USERPROFILE%\techcolab-backlog"

:: Ensure vault path is set even if env var wasn't inherited
if "%TECHCOLAB_VAULT%"=="" (
    set "TECHCOLAB_VAULT=%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\App\Personal toolkit"
)

:: Ensure the AI Gateway key is set even if the launcher's process tree
:: (e.g. an Explorer session started before the user env var existed)
:: hasn't picked it up yet. Read it straight from the registry as a fallback.
if "%NETZSCH_LLM_API_KEY%"=="" (
    for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v NETZSCH_LLM_API_KEY 2^>nul ^| findstr /i "NETZSCH_LLM_API_KEY"') do set "NETZSCH_LLM_API_KEY=%%B"
)

call .venv\Scripts\activate.bat
streamlit run app.py --server.port 8501 >> "%~dp0streamlit.log" 2>&1

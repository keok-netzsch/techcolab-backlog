@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo  Techco.lab Agent -- Phase 2
echo  Execution of approved actions
echo ========================================
echo.

:: Get today's date in YYYY-MM-DD format
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TODAY=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%

:: Vault path from env var or fallback
if "%TECHCOLAB_VAULT%"=="" (
    set "TECHCOLAB_VAULT=C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO"
)
set "REPORT=%TECHCOLAB_VAULT%\agent-reports\report-%TODAY%.md"

if not exist "%REPORT%" (
    echo [ERROR] Report not found:
    echo         %REPORT%
    echo.
    echo Run "3. Rodar Agente" first to generate today's report.
    pause
    exit /b 1
)

echo [1] Today's report found: %REPORT%
echo [2] Opening Claude Code in this directory...
echo.
echo When Claude opens, type exactly:
echo.
echo     Execute the approved items from today's agent report
echo.
echo Claude will read the report, list what you approved,
echo confirm with you, then implement and run the tests.
echo.
pause

start "Claude Code - TechColab Phase 2" cmd /k "cd /d %~dp0 && C:\Users\Kelvin.okuda\.local\bin\claude.exe"

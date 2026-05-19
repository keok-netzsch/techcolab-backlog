@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo  TechColab Backlog Agent -- Phase 2
echo  Execution of approved actions
echo ========================================
echo.

:: Get today's date in YYYY-MM-DD format
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TODAY=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%
set REPORT=agent-reports\report-%TODAY%.md

if not exist "%REPORT%" (
    echo [ERROR] Report not found: %REPORT%
    echo Run run_agent.bat first to generate today's report.
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

"%USERPROFILE%\.local\bin\claude.exe"

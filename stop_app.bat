@echo off
setlocal

for /f "tokens=5" %%a in ('netstat -ano ^| findstr " 0.0.0.0:8501 "') do (
    set "PID=%%a"
    goto :found
)

echo TechColab Backlog nao esta rodando.
timeout /t 2 >nul
exit /b 0

:found
taskkill /F /PID %PID% >nul 2>&1
echo TechColab Backlog encerrado (PID %PID%).
timeout /t 2 >nul

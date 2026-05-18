@echo off
setlocal

echo ============================================================
echo   TechColab Backlog -- Instalacao
echo ============================================================
echo.

REM ── Verificar se Python esta disponivel ─────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo        Instale o Python 3.10+ em https://www.python.org/downloads/
    echo        e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

REM ── Criar ambiente virtual ───────────────────────────────────
if exist ".venv\" (
    echo [INFO] Ambiente virtual ja existe. Pulando criacao.
) else (
    echo [1/3] Criando ambiente virtual em .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
)
echo.

REM ── Ativar ambiente virtual ──────────────────────────────────
echo [2/3] Ativando ambiente virtual ...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Nao foi possivel ativar o ambiente virtual.
    pause
    exit /b 1
)
echo [OK] Ambiente virtual ativo.
echo.

REM ── Instalar dependencias ────────────────────────────────────
echo [3/3] Instalando dependencias (requirements.txt) ...
pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    echo        Verifique sua conexao com a internet e tente novamente.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas com sucesso.
echo.

REM ── Criar atalho na Area de Trabalho ────────────────────────
echo [INFO] Criando atalho na Area de Trabalho ...
set "SCRIPT_DIR=%~dp0"
set "SHORTCUT=%USERPROFILE%\Desktop\TechColab Backlog.lnk"
set "TARGET=%SCRIPT_DIR%start_app.bat"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.WorkingDirectory = '%SCRIPT_DIR%'; ^
   $s.Description = 'Iniciar TechColab Backlog'; ^
   $s.Save()"

if exist "%SHORTCUT%" (
    echo [OK] Atalho criado na Area de Trabalho: "TechColab Backlog"
) else (
    echo [AVISO] Nao foi possivel criar o atalho automaticamente.
    echo         Use start_app.bat diretamente para iniciar o aplicativo.
)
echo.

REM ── Mensagem final ───────────────────────────────────────────
echo ============================================================
echo   Instalacao concluida!
echo ============================================================
echo.
echo  Proximos passos:
echo.
echo   1. Edite config.py e ajuste VAULT_ROOT para o caminho
echo      do seu cofre (vault) do Obsidian.
echo.
echo   2. Certifique-se de que o Ollama esta instalado e rodando.
echo      Baixe o modelo com: ollama pull llama3.2:3b
echo.
echo   3. Inicie o aplicativo:
echo        - Duplo clique em start_app.bat, ou
echo        - Use o atalho "TechColab Backlog" na Area de Trabalho.
echo.
echo ============================================================
echo.
pause
endlocal

# close-session.ps1 — commit e push nos dois repos com testes
# Uso: Win+C via Raycast, ou powershell -File close-session.ps1

$TB  = "C:\Users\Kelvin.okuda\techcolab-backlog"
$CR  = "C:\Users\Kelvin.okuda\Scripts\call-recorder"
# Tenta venv primeiro, cai no Python do sistema se nao existir
$PY  = if (Test-Path "$TB\.venv\Scripts\python.exe") { "$TB\.venv\Scripts\python.exe" } else { "python" }
$NOW = Get-Date -Format "yyyy-MM-dd HH:mm"
$TAG = Get-Date -Format "yyyy-MM-dd"
$ok  = $true

Clear-Host
Write-Host ""
Write-Host "  ================================" -ForegroundColor DarkCyan
Write-Host "      Encerramento de Sessao       " -ForegroundColor DarkCyan
Write-Host "  ================================" -ForegroundColor DarkCyan
Write-Host "  $NOW" -ForegroundColor DarkGray
Write-Host ""

# ── 1. Testes ─────────────────────────────────────────────────────────────────
Write-Host "  [1/3] Rodando testes..." -ForegroundColor Cyan
$result = & $PY -m pytest "$TB\tests" -q --tb=short --ignore="$TB\tests\test_config.py" 2>&1
if ($LASTEXITCODE -eq 0) {
    $summary = ($result | Select-Object -Last 1)
    Write-Host "  [OK] Testes passaram -- $summary" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Testes falharam:" -ForegroundColor Yellow
    $result | Select-Object -Last 6 | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    $confirm = Read-Host "  Continuar mesmo assim? (s/n)"
    if ($confirm -ne "s") { Write-Host "  Abortado."; exit 1 }
    $ok = $false
}

Write-Host ""

# ── 2. Mensagem de commit ──────────────────────────────────────────────────────
$msg = Read-Host "  [2/3] Mensagem de commit (ENTER = 'chore: session close $TAG')"
if ($msg -eq "") { $msg = "chore: session close $TAG" }

Write-Host ""

# ── 3. Commit e push ──────────────────────────────────────────────────────────
Write-Host "  [3/3] Commitando repos..." -ForegroundColor Cyan

function Push-Repo {
    param([string]$Dir, [string]$Label, [string]$Message)
    Push-Location $Dir
    $changed = git status --porcelain
    if ($changed) {
        git add -A | Out-Null
        git commit -m $Message | Out-Null
        git push 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] $Label -- pushed" -ForegroundColor Green
        } else {
            Write-Host "  [ERR] $Label -- push falhou" -ForegroundColor Red
        }
    } else {
        Write-Host "  [--] $Label -- sem mudancas" -ForegroundColor DarkGray
    }
    Pop-Location
}

Push-Repo -Dir $TB -Label "techcolab-backlog" -Message $msg
Push-Repo -Dir $CR -Label "call-recorder"     -Message $msg

# ── 4. Resumo ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  -- Commits de hoje -----------------------" -ForegroundColor DarkGray

function Show-TodayLog {
    param([string]$Dir, [string]$Label)
    Push-Location $Dir
    $log = git log --oneline --since="$TAG 00:00" 2>$null
    if ($log) {
        Write-Host "  $Label" -ForegroundColor DarkCyan
        $log | ForEach-Object { Write-Host "    . $_" -ForegroundColor Gray }
    }
    Pop-Location
}

Show-TodayLog -Dir $TB -Label "techcolab-backlog"
Show-TodayLog -Dir $CR -Label "call-recorder"

Write-Host ""
if ($ok) {
    Write-Host "  Sessao encerrada com sucesso. Bom descanso!" -ForegroundColor Green
} else {
    Write-Host "  Sessao encerrada (com testes pendentes)." -ForegroundColor Yellow
}
Write-Host ""
Start-Sleep -Seconds 2

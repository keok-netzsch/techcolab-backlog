# close-session.ps1 — encerra o dia: testes, commit e push em todos os repos
# Use via Raycast ou terminal: .\close-session.ps1

$TB  = "C:\Users\Kelvin.okuda\techcolab-backlog"
$CR  = "C:\Users\Kelvin.okuda\Scripts\call-recorder"
$PY  = "$TB\.venv\Scripts\python.exe"
$NOW = Get-Date -Format "yyyy-MM-dd HH:mm"
$TAG = Get-Date -Format "yyyy-MM-dd"

$ok  = $true

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor DarkCyan
Write-Host "  ║        Encerramento de Sessão         ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor DarkCyan
Write-Host "  $NOW" -ForegroundColor DarkGray
Write-Host ""

# ── 1. Testes ─────────────────────────────────────────────────────────────────
Write-Host "  [1/3] Rodando testes..." -ForegroundColor Cyan
$result = & $PY -m pytest "$TB\tests" -q --tb=short 2>&1
$last   = ($result | Select-Object -Last 3) -join "`n"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Testes OK — $($result | Select-Object -Last 1)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Testes falharam:" -ForegroundColor Yellow
    Write-Host ($result | Select-Object -Last 6 | Out-String) -ForegroundColor Yellow
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
            Write-Host "  ✅ $Label — pushed" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $Label — push falhou" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⬜ $Label — sem mudanças" -ForegroundColor DarkGray
    }
    Pop-Location
}

Push-Repo -Dir $TB  -Label "techcolab-backlog" -Message $msg
Push-Repo -Dir $CR  -Label "call-recorder"     -Message $msg

# ── 4. Resumo de hoje ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ── Commits de hoje ──────────────────────" -ForegroundColor DarkGray

function Show-TodayLog {
    param([string]$Dir, [string]$Label)
    Push-Location $Dir
    $log = git log --oneline --since="$TAG 00:00" 2>$null
    if ($log) {
        Write-Host "  $Label" -ForegroundColor DarkCyan
        $log | ForEach-Object { Write-Host "    · $_" -ForegroundColor Gray }
    }
    Pop-Location
}

Show-TodayLog -Dir $TB -Label "techcolab-backlog"
Show-TodayLog -Dir $CR -Label "call-recorder"

Write-Host ""
if ($ok) {
    Write-Host "  Sessão encerrada com sucesso. Bom descanso!" -ForegroundColor Green
} else {
    Write-Host "  Sessão encerrada (com testes pendentes)." -ForegroundColor Yellow
}
Write-Host ""
Start-Sleep -Seconds 2

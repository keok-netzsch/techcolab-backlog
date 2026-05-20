# quick-push.ps1 — commit e push rápido durante o desenvolvimento
# Sem rodar testes, sem pedir mensagem. Usa timestamp como mensagem.
# Use durante o dia quando quiser salvar progresso no GitHub.

$TB  = "C:\Users\Kelvin.okuda\techcolab-backlog"
$CR  = "C:\Users\Kelvin.okuda\Scripts\call-recorder"
$MSG = "wip: auto-push $(Get-Date -Format 'yyyy-MM-dd HH:mm')"

function Push-Repo {
    param([string]$Dir, [string]$Label)
    Push-Location $Dir
    $changed = git status --porcelain
    if ($changed) {
        git add -A | Out-Null
        git commit -m $MSG | Out-Null
        git push 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ $Label pushed" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $Label — erro no push" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⬜ $Label — sem mudanças" -ForegroundColor DarkGray
    }
    Pop-Location
}

Push-Repo -Dir $TB -Label "techcolab-backlog"
Push-Repo -Dir $CR -Label "call-recorder"

Start-Sleep -Seconds 1

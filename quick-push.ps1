# quick-push.ps1 — commit e push rapido sem testes
# Uso: atalho "5. Push Rapido" no Desktop ou Raycast

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
            Write-Host "  [OK] $Label pushed" -ForegroundColor Green
        } else {
            Write-Host "  [ERR] $Label -- erro no push" -ForegroundColor Red
        }
    } else {
        Write-Host "  [--] $Label -- sem mudancas" -ForegroundColor DarkGray
    }
    Pop-Location
}

Write-Host ""
Push-Repo -Dir $TB -Label "techcolab-backlog"
Push-Repo -Dir $CR -Label "call-recorder"
Write-Host ""
Start-Sleep -Seconds 1

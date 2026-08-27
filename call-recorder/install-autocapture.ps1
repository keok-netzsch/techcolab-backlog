# install-autocapture.ps1
# Registra (ou remove) a tarefa que sobe o autocapture.py no logon.
#   .\install-autocapture.ps1            -> instala
#   .\install-autocapture.ps1 -Remove    -> desinstala
#
# Keep this file ASCII-only in code lines: it runs under Windows PowerShell 5.1,
# which reads no-BOM files as ANSI and breaks on stray non-ASCII characters.

param([switch]$Remove)

$TaskName = "CallRecorder-AutoCapture"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$TaskName' removida." -ForegroundColor Yellow
    return
}

$pythonw = (Get-Command pythonw -ErrorAction Stop).Source
$dir     = "$env:USERPROFILE\techcolab-backlog\call-recorder"
$script  = Join-Path $dir "autocapture.py"

if (-not (Test-Path $script)) { throw "Nao encontrei: $script" }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $script + '"') -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# ExecutionTimeLimit zero = sem limite: a tarefa fica viva o dia inteiro.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Grava automaticamente enquanto o Teams estiver em call" -Force | Out-Null

Write-Host "Tarefa '$TaskName' registrada (inicia no logon)." -ForegroundColor Green
Write-Host "Pausar sem desinstalar: crie o arquivo $dir\autocapture.paused"
Write-Host "Desinstalar: .\install-autocapture.ps1 -Remove"

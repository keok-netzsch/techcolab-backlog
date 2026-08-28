# Installs (or removes) the triage reminder scheduled task.
#
#   .\install-triage-reminder.ps1            # instala / reinstala
#   .\install-triage-reminder.ps1 -Remove    # desinstala
#
# 18:30 on weekdays: after the working-hours window where daily_report.py refuses
# to run Whisper, and 90 minutes before the 20:00 queue. Anything Kelvin
# classifies in that gap is filed to the right place in the same nightly batch
# instead of landing in the Inbox to be moved by hand later.

param([switch]$Remove)

$nome = "CallRecorder-Triage-Reminder"
$script = Join-Path $env:USERPROFILE "techcolab-backlog\scripts\triage-reminder.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$nome' removida."
    exit 0
}

if (-not (Test-Path $script)) {
    Write-Host "ERRO: nao encontrei $script"
    exit 1
}

$arg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"'
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg

$gatilho = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "18:30"

# StartWhenAvailable: se a maquina estiver desligada as 18:30, o lembrete
# aparece no proximo logon em vez de simplesmente sumir naquele dia.
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Settings $cfg -Force `
    -Description "Pede ao Kelvin para classificar gravacoes que o autocapture nao conseguiu rotear. Roda antes da fila das 20:00." | Out-Null

$t = Get-ScheduledTask -TaskName $nome
$i = $t | Get-ScheduledTaskInfo
Write-Host ("Tarefa : {0}" -f $t.TaskName)
Write-Host ("Estado : {0}" -f $t.State)
Write-Host ("Proxima: {0}" -f $i.NextRunTime)
Write-Host ""
Write-Host "Para remover: .\install-triage-reminder.ps1 -Remove"

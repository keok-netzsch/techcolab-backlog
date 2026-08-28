# Installs (or removes) the triage reminder scheduled task.
#
#   .\install-triage-reminder.ps1            # instala / reinstala
#   .\install-triage-reminder.ps1 -Remove    # desinstala
#
# 16:00 on weekdays, deliberately INSIDE working hours: classifying is a task for
# Kelvin at his desk, not something to find at night. The queue that consumes the
# decisions runs at 20:00, long after he has stopped working - so the order is
# decide first, process later, and anything classified by 16:00 is filed to the
# right place in the same batch instead of landing in the Inbox to be moved by hand.

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
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "16:00"

# StartWhenAvailable: se a maquina estiver desligada as 16:00, o lembrete
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

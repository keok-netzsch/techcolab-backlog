# Installs (or removes) the triage reminder scheduled task.
#
#   .\install-triage-reminder.ps1            # instala / reinstala
#   .\install-triage-reminder.ps1 -Remove    # desinstala
#
# 09:00 on weekdays. It was 16:00 until 2026-08-28, which was simply too early:
# routing now happens against the TRANSCRIPT, and the transcript does not exist
# until the 20:00 batch has run. At 16:00 there was nothing to read.
#
# So the order is: record all day -> transcribe at 20:00 -> route in the morning,
# with the content in hand. See "Routing happens after transcription" in
# call-recorder/CLAUDE.md.

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
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "09:00"

# StartWhenAvailable: se a maquina estiver desligada as 09:00, o lembrete
# aparece no proximo logon em vez de simplesmente sumir naquele dia.
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Settings $cfg -Force `
    -Description "Avisa o Kelvin de manha que ha calls transcritas na noite anterior esperando destino no vault (route.py)." | Out-Null

$t = Get-ScheduledTask -TaskName $nome
$i = $t | Get-ScheduledTaskInfo
Write-Host ("Tarefa : {0}" -f $t.TaskName)
Write-Host ("Estado : {0}" -f $t.State)
Write-Host ("Proxima: {0}" -f $i.NextRunTime)
Write-Host ""
Write-Host "Para remover: .\install-triage-reminder.ps1 -Remove"

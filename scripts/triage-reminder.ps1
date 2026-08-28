# Triage reminder - call recorder
#
# Asks Kelvin to classify the recordings the machine could not place. The Teams
# window title carries the meeting SUBJECT and never the participants, so a call
# named "Power BI Data Export" cannot be routed automatically - it was Stefan and
# Ana discussing the OKR 05 export policy, and no string match could know that.
#
# Fires BEFORE the 20:00 queue run, so anything classified here is filed to the
# right place in the same nightly batch instead of landing in the Inbox.
#
# MessageBox, not toast, deliberately: the toast API reported success on every
# fire while Focus Assist suppressed the banner, so reminders were missed
# silently (see send-evening-push.ps1, 2026-08-11). A MessageBox is not subject
# to Focus Assist and stays until dismissed.
#
# Silent when there is nothing to classify - a reminder that cries wolf on empty
# nights stops being read.

Add-Type -AssemblyName System.Windows.Forms

$py = "python"
$triage = Join-Path $env:USERPROFILE "techcolab-backlog\call-recorder\triage.py"

if (-not (Test-Path $triage)) {
    Write-Host "triage.py nao encontrado em $triage"
    exit 1
}

$saida = & $py $triage 2>&1 | Out-String

if ($saida -match "nada aguardando") {
    Write-Host "Nada para classificar - sem lembrete."
    exit 0
}

# First line carries the count; the blocks below carry meeting names.
$linhas = $saida -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
$quantos = ($linhas | Select-Object -First 1)

$reunioes = $linhas |
    Where-Object { $_ -match "reuniao:" } |
    ForEach-Object { "  - " + ($_ -replace ".*reuniao:\s*", "" -replace "\s*\|\s*Microsoft Teams", "") } |
    Select-Object -First 8

$titulo = "Call Recorder - gravacoes esperando voce"
$corpo = @"
$quantos

$($reunioes -join "`n")

A fila das 20:00 transcreve tudo. O que voce classificar ate la
vai para o lugar certo; o resto cai no Inbox.

Para classificar, no PowerShell:

  python "%USERPROFILE%\techcolab-backlog\call-recorder\triage.py"

Use --lembrar nas recorrentes (Daily BIZ, Daily PM) para nao
precisar decidir de novo na semana que vem.
"@

try {
    $form = New-Object System.Windows.Forms.Form
    $form.TopMost = $true
    $form.Opacity = 0
    $form.ShowInTaskbar = $false
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(0, 0)
    $form.Show()
    [System.Windows.Forms.MessageBox]::Show($form, $corpo, $titulo,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    $form.Close()
    Write-Host "Lembrete exibido: $quantos"
} catch {
    Write-Host "MessageBox falhou: $($_.Exception.Message)"
    exit 1
}

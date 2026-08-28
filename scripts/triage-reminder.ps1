# Triage - call recorder
#
# Asks Kelvin to classify the recordings the machine could not place, and lets
# him answer IN the dialog. The first version only told him to go and type a
# command in a terminal; a reminder that creates homework does not get done.
#
# The Teams window title carries the meeting SUBJECT and never the participants,
# so "Power BI Data Export" cannot be routed automatically - it was Stefan and
# Ana discussing the OKR 05 export policy, and no string match could know that.
# Only Kelvin can say. This dialog is where he says it.
#
# Fires BEFORE the 20:00 queue run, so anything classified here is filed to the
# right place in the same nightly batch instead of landing in the Inbox.
#
# WinForms dialog, not toast: the toast API reported success on every fire while
# Focus Assist suppressed the banner, so reminders were missed silently (see
# send-evening-push.ps1, 2026-08-11). A window is not subject to Focus Assist.
#
# Silent when there is nothing to classify - a reminder that cries wolf on empty
# nights stops being read.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$py      = "python"
$base    = Join-Path $env:USERPROFILE "techcolab-backlog\call-recorder"
$triage  = Join-Path $base "triage.py"
$vault   = Join-Path $env:USERPROFILE "OneDrive - NETZSCH\Documents\TechColab_D&A_KO"

if (-not (Test-Path $triage)) { Write-Host "triage.py nao encontrado"; exit 1 }

# --- o que esta pendente -----------------------------------------------------
# Consome JSON, nao o texto formatado: a primeira versao raspava a listagem
# humana com regex e passou a achar ZERO itens quando o formato mudou por um
# espaco - falhando exatamente como "nao ha nada a classificar".
$json = & $py $triage --json 2>&1 | Out-String
try {
    $pendentes = @($json | ConvertFrom-Json)
} catch {
    Write-Host "Nao consegui ler a lista: $($_.Exception.Message)"
    Write-Host $json
    exit 1
}
if ($pendentes.Count -eq 0) { Write-Host "Nada a classificar."; exit 0 }

# --- destinos possiveis, lidos do vault de verdade ---------------------------
$opcoes = New-Object System.Collections.ArrayList
[void]$opcoes.Add(@{ rotulo = "Reuniao de projeto  (Inbox)"; kind = "project"; alvo = "" })
[void]$opcoes.Add(@{ rotulo = "Nota solta          (Inbox)"; kind = "note";    alvo = "" })
foreach ($d in (Get-ChildItem (Join-Path $vault "Team") -Directory -EA SilentlyContinue | Sort-Object Name)) {
    if ($d.Name -match "-") {
        [void]$opcoes.Add(@{ rotulo = "1:1  - " + ($d.Name -replace "-", " "); kind = "person"; alvo = $d.Name })
    }
}
foreach ($d in (Get-ChildItem (Join-Path $vault "Stakeholders") -Directory -EA SilentlyContinue | Sort-Object Name)) {
    if ($d.Name -match "-") {
        [void]$opcoes.Add(@{ rotulo = "Stakeholder - " + ($d.Name -replace "-", " "); kind = "manager"; alvo = $d.Name })
    }
}

# --- uma janela por gravacao -------------------------------------------------
$feitos = 0
foreach ($p in $pendentes) {

    $f = New-Object System.Windows.Forms.Form
    $f.Text = "Call Recorder - classificar gravacao"
    $f.Size = New-Object System.Drawing.Size(620, 330)
    $f.StartPosition = "CenterScreen"
    $f.TopMost = $true
    $f.FormBorderStyle = "FixedDialog"
    $f.MaximizeBox = $false; $f.MinimizeBox = $false

    $lbTitulo = New-Object System.Windows.Forms.Label
    $lbTitulo.Text = ($p.meeting -replace "\s*\|\s*Microsoft Teams", "")
    $lbTitulo.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $lbTitulo.SetBounds(20, 18, 570, 30)
    $f.Controls.Add($lbTitulo)

    $lbQuando = New-Object System.Windows.Forms.Label
    $lbQuando.Text = "$($p.date) $($p.time)   -   $($p.id)"
    $lbQuando.ForeColor = [System.Drawing.Color]::DimGray
    $lbQuando.SetBounds(20, 50, 570, 20)
    $f.Controls.Add($lbQuando)

    $lbP = New-Object System.Windows.Forms.Label
    $lbP.Text = "Onde isto deve ser arquivado?"
    $lbP.SetBounds(20, 88, 570, 20)
    $f.Controls.Add($lbP)

    $cb = New-Object System.Windows.Forms.ComboBox
    $cb.DropDownStyle = "DropDownList"
    $cb.SetBounds(20, 112, 560, 28)
    $cb.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    foreach ($o in $opcoes) { [void]$cb.Items.Add($o.rotulo) }
    $cb.SelectedIndex = 0
    $f.Controls.Add($cb)

    $chk = New-Object System.Windows.Forms.CheckBox
    $chk.Text = "Lembrar esta reuniao (recorrentes se classificam sozinhas depois)"
    $chk.SetBounds(20, 152, 560, 24)
    $f.Controls.Add($chk)

    $lbN = New-Object System.Windows.Forms.Label
    $lbN.Text = "Contexto (opcional) - vai junto para a nota:"
    $lbN.SetBounds(20, 182, 560, 20)
    $f.Controls.Add($lbN)

    $tx = New-Object System.Windows.Forms.TextBox
    $tx.SetBounds(20, 204, 560, 24)
    $f.Controls.Add($tx)

    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = "Classificar"; $ok.SetBounds(330, 244, 120, 32)
    $ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $f.Controls.Add($ok); $f.AcceptButton = $ok

    $pular = New-Object System.Windows.Forms.Button
    $pular.Text = "Depois"; $pular.SetBounds(460, 244, 120, 32)
    $pular.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $f.Controls.Add($pular); $f.CancelButton = $pular

    $lbRest = New-Object System.Windows.Forms.Label
    $lbRest.Text = "$($pendentes.Count - $feitos) restante(s)"
    $lbRest.ForeColor = [System.Drawing.Color]::DimGray
    $lbRest.SetBounds(20, 252, 200, 20)
    $f.Controls.Add($lbRest)

    $r = $f.ShowDialog()
    $f.Dispose()
    if ($r -ne [System.Windows.Forms.DialogResult]::OK) { continue }

    $esc = $opcoes[$cb.SelectedIndex]
    # Nao usar $args: e variavel automatica do PowerShell e sobrescreve-la e
    # fonte classica de comportamento estranho dentro de funcoes e blocos.
    $cmd = @($triage, $p.id, $esc.kind)
    if ($esc.alvo)          { $cmd += $esc.alvo }
    if ($chk.Checked)       { $cmd += "--lembrar" }
    if ($tx.Text.Trim())    { $cmd += "--nota"; $cmd += $tx.Text.Trim() }

    & $py $cmd 2>&1 | ForEach-Object { Write-Host $_ }
    $feitos++
}

Write-Host "Classificadas nesta rodada: $feitos de $($pendentes.Count)"

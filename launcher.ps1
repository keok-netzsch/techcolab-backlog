Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class DwmApi {
    [DllImport("dwmapi.dll")]
    public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);
}
public class ShellApp {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    public static extern void SetCurrentProcessExplicitAppUserModelID(string AppID);
}
'@

# Desvincular processo do ícone do powershell.exe na barra de tarefas
[ShellApp]::SetCurrentProcessExplicitAppUserModelID("Techcolab.Launcher.1")

$clrBg     = [System.Drawing.ColorTranslator]::FromHtml("#1C1C28")
$clrCard   = [System.Drawing.ColorTranslator]::FromHtml("#2D2E3E")
$clrHover  = [System.Drawing.ColorTranslator]::FromHtml("#3A3B50")
$clrAccent = [System.Drawing.ColorTranslator]::FromHtml("#02B793")
$clrText   = [System.Drawing.Color]::White
$clrSub    = [System.Drawing.ColorTranslator]::FromHtml("#9A9AB0")
$clrStatus = [System.Drawing.ColorTranslator]::FromHtml("#252535")
$clrSep    = [System.Drawing.ColorTranslator]::FromHtml("#3A3B50")

$TB = "C:\Users\Kelvin.okuda\techcolab-backlog"
$CR = "C:\Users\Kelvin.okuda\Scripts\call-recorder"

$groups = @(
    @{
        Label   = "APP"
        Actions = @(
            [pscustomobject]@{ Title="Open App"; Desc="Open http://localhost:8501 in the default browser"; Exe="http://localhost:8501"; PArgs="" },
            [pscustomobject]@{ Title="Kill App"; Desc="Stop Streamlit on port 8501";                      Exe="wscript.exe";          PArgs="`"$TB\stop_app.vbs`"" }
        )
    },
    @{
        Label   = "AGENT"
        Actions = @(
            [pscustomobject]@{ Title="Run Agent";     Desc="Phase 1: analyze backlog and write daily report"; Exe="cmd.exe"; PArgs="/k `"$TB\run_agent.bat`"" },
            [pscustomobject]@{ Title="Execute Agent"; Desc="Phase 2: copy command and open Claude Code";       Exe="cmd.exe"; PArgs="/k `"$TB\execute_agent.bat`"" }
        )
    },
    @{
        Label   = "GIT"
        Actions = @(
            [pscustomobject]@{ Title="Quick Push";    Desc="Instant commit + push, auto message, no tests"; Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$TB\quick-push.ps1`"" },
            [pscustomobject]@{ Title="Close Session"; Desc="Run tests, commit and push all repos";           Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$TB\close-session.ps1`"" }
        )
    },
    @{
        Label   = "SKILLS"
        Actions = @(
            [pscustomobject]@{ Title="SPM Bot";       Desc="Copy /spm-bot to clipboard and open Claude"; Exe="powershell.exe"; PArgs="-NoProfile -Command `"Set-Clipboard '/spm-bot'; Start-Process 'https://claude.ai'`"" },
            [pscustomobject]@{ Title="Deck Designer"; Desc="Copy /techcolab-deck to clipboard and open Claude"; Exe="powershell.exe"; PArgs="-NoProfile -Command `"Set-Clipboard '/techcolab-deck'; Start-Process 'https://claude.ai'`"" }
        )
    },
    @{
        Label   = "FEATURES"
        Actions = @(
            [pscustomobject]@{ Title="Call Recorder"; Desc="Record & transcribe 1on1 / English Coach sessions"; Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$CR\call-recorder.ps1`"" },
            [pscustomobject]@{ Title="Toilet Paper";  Desc="Text-to-diagram app - starts Vite dev server (localhost:5173)"; Exe="cmd.exe"; PArgs="/k cd /d C:\Users\Kelvin.okuda\napkin-clone ^&^& npm run dev" }
        )
    }
)

# ── Custom icon (green circle + "T") ──────────────────────────────────────────
function New-LauncherIcon {
    $bmp  = New-Object System.Drawing.Bitmap(32, 32)
    $g    = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $bg   = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml("#02B793"))
    $g.FillEllipse($bg, 0, 0, 31, 31)
    $font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
    $sf   = New-Object System.Drawing.StringFormat
    $sf.Alignment     = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString("T", $font, [System.Drawing.Brushes]::White,
                  [System.Drawing.RectangleF]::new(0, 1, 32, 32), $sf)
    $g.Dispose(); $bg.Dispose(); $font.Dispose(); $sf.Dispose()
    return [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
}

# ── Form ───────────────────────────────────────────────────────────────────────
$form = New-Object System.Windows.Forms.Form
$form.Text            = "Techco.lab Launcher"
$form.BackColor       = $clrBg
$form.ForeColor       = $clrText
$form.StartPosition   = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox     = $false
$form.ClientSize      = New-Object System.Drawing.Size(460, 800)
$form.Font            = New-Object System.Drawing.Font("Segoe UI", 10)
$form.Icon            = New-LauncherIcon

# Auto-start Streamlit + Ollama, and apply dark title bar
$form.add_Shown({
    $darkMode = 1
    [DwmApi]::DwmSetWindowAttribute($form.Handle, 20, [ref]$darkMode, 4) | Out-Null

    try { Start-Process "wscript.exe" -ArgumentList "`"$TB\start_silent.vbs`"" } catch {}

    if (-not (Get-Process "ollama" -ErrorAction SilentlyContinue)) {
        try { Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden } catch {}
    }

    $script:lblStatus.Text = "Starting Streamlit & Ollama...  $(Get-Date -Format 'HH:mm:ss')"
})

# ── Header ─────────────────────────────────────────────────────────────────────
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text      = "Techco.lab"
$lblTitle.ForeColor = $clrAccent
$lblTitle.Font      = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$lblTitle.Location  = New-Object System.Drawing.Point(20, 14)
$lblTitle.AutoSize  = $true
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text      = "Personal Toolkit Launcher"
$lblSub.ForeColor = $clrSub
$lblSub.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$lblSub.Location  = New-Object System.Drawing.Point(22, 43)
$lblSub.AutoSize  = $true
$form.Controls.Add($lblSub)

# ── Status bar ─────────────────────────────────────────────────────────────────
$pnlStatus = New-Object System.Windows.Forms.Panel
$pnlStatus.BackColor = $clrStatus
$pnlStatus.Height    = 30
$pnlStatus.Dock      = "Bottom"
$form.Controls.Add($pnlStatus)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text      = "Ready"
$lblStatus.ForeColor = $clrSub
$lblStatus.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$lblStatus.Location  = New-Object System.Drawing.Point(12, 7)
$lblStatus.AutoSize  = $true
$pnlStatus.Controls.Add($lblStatus)

# ── Hover handlers ─────────────────────────────────────────────────────────────
$onEnter = {
    param($sender, $e)
    $card = if ($sender.Tag -eq "card") { $sender } else { $sender.Parent }
    $card.BackColor = $script:clrHover
    foreach ($c in $card.Controls) {
        if ($c.Tag -ne "accent") { $c.BackColor = $script:clrHover }
    }
}

$onLeave = {
    param($sender, $e)
    $card = if ($sender.Tag -eq "card") { $sender } else { $sender.Parent }
    $card.BackColor = $script:clrCard
    foreach ($c in $card.Controls) {
        if ($c.Tag -ne "accent") { $c.BackColor = $script:clrCard }
    }
}

# ── Groups + Cards ─────────────────────────────────────────────────────────────
$cardW   = 420
$cardH   = 50
$cardGap = 6
$hdrH    = 22

$y          = 68
$firstGroup = $true

foreach ($group in $groups) {
    if (-not $firstGroup) {
        $y += 4

        $sep = New-Object System.Windows.Forms.Panel
        $sep.BackColor = $clrSep
        $sep.Size      = New-Object System.Drawing.Size($cardW, 1)
        $sep.Location  = New-Object System.Drawing.Point(20, $y)
        $form.Controls.Add($sep)
        $y += 1 + 8
    }
    $firstGroup = $false

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text      = $group.Label
    $lbl.ForeColor = $clrAccent
    $lbl.Font      = New-Object System.Drawing.Font("Segoe UI", 7.5, [System.Drawing.FontStyle]::Bold)
    $lbl.Location  = New-Object System.Drawing.Point(20, $y)
    $lbl.AutoSize  = $true
    $form.Controls.Add($lbl)
    $y += $hdrH

    for ($ci = 0; $ci -lt $group.Actions.Count; $ci++) {
        $a     = $group.Actions[$ci]
        $exe   = $a.Exe
        $pargs = $a.PArgs
        $title = $a.Title

        $card = New-Object System.Windows.Forms.Panel
        $card.BackColor = $clrCard
        $card.Size      = New-Object System.Drawing.Size($cardW, $cardH)
        $card.Location  = New-Object System.Drawing.Point(20, $y)
        $card.Cursor    = [System.Windows.Forms.Cursors]::Hand
        $card.Tag       = "card"
        $form.Controls.Add($card)

        $accent = New-Object System.Windows.Forms.Panel
        $accent.BackColor = $clrAccent
        $accent.Size      = New-Object System.Drawing.Size(4, $cardH)
        $accent.Location  = New-Object System.Drawing.Point(0, 0)
        $accent.Tag       = "accent"
        $card.Controls.Add($accent)

        $lblT = New-Object System.Windows.Forms.Label
        $lblT.Text      = $a.Title
        $lblT.ForeColor = $clrText
        $lblT.BackColor = $clrCard
        $lblT.Font      = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
        $lblT.Location  = New-Object System.Drawing.Point(16, 8)
        $lblT.AutoSize  = $true
        $card.Controls.Add($lblT)

        $lblD = New-Object System.Windows.Forms.Label
        $lblD.Text      = $a.Desc
        $lblD.ForeColor = $clrSub
        $lblD.BackColor = $clrCard
        $lblD.Font      = New-Object System.Drawing.Font("Segoe UI", 8.5)
        $lblD.Location  = New-Object System.Drawing.Point(16, 29)
        $lblD.AutoSize  = $true
        $card.Controls.Add($lblD)

        $onClick = {
            param($sender, $e)
            try {
                if ($exe -match "^https?://") {
                    Start-Process $exe
                } elseif ($pargs -ne "") {
                    Start-Process $exe -ArgumentList $pargs
                } else {
                    Start-Process $exe
                }
                $script:lblStatus.Text = "Launched: $title  |  $(Get-Date -Format 'HH:mm:ss')"
            } catch {
                $script:lblStatus.Text = "Error: $_"
            }
        }.GetNewClosure()

        $card.add_MouseEnter($onEnter)
        $card.add_MouseLeave($onLeave)
        $card.add_Click($onClick)
        $lblT.add_MouseEnter($onEnter)
        $lblT.add_MouseLeave($onLeave)
        $lblT.add_Click($onClick)
        $lblD.add_MouseEnter($onEnter)
        $lblD.add_MouseLeave($onLeave)
        $lblD.add_Click($onClick)

        $y += $cardH
        if ($ci -lt $group.Actions.Count - 1) { $y += $cardGap }
    }
}

[System.Windows.Forms.Application]::Run($form)

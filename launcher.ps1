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

# ── Palette — aligned with the Streamlit app dark theme (design system) ────────
$clrBg     = [System.Drawing.ColorTranslator]::FromHtml("#0E1117")   # app background
$clrCard   = [System.Drawing.ColorTranslator]::FromHtml("#1A1D2E")   # card surface
$clrHover  = [System.Drawing.ColorTranslator]::FromHtml("#1E2640")   # card hover
$clrAccent = [System.Drawing.ColorTranslator]::FromHtml("#02B793")   # brand accent
$clrText   = [System.Drawing.ColorTranslator]::FromHtml("#E2E8F0")   # primary text
$clrSub    = [System.Drawing.ColorTranslator]::FromHtml("#94A3B8")   # secondary text
$clrMuted  = [System.Drawing.ColorTranslator]::FromHtml("#64748B")   # section labels
$clrStatus = [System.Drawing.ColorTranslator]::FromHtml("#161B2E")   # status bar
$clrSep    = [System.Drawing.ColorTranslator]::FromHtml("#2D3748")   # borders / dividers

$TB = "$env:USERPROFILE\techcolab-backlog"
$CR = "$TB\call-recorder"

$groups = @(
    @{
        Label   = "APP"
        Actions = @(
            [pscustomobject]@{ Title="Open App"; Desc="Open localhost:8501 in the browser";  Exe="http://localhost:8501"; PArgs="" },
            [pscustomobject]@{ Title="Kill App"; Desc="Stop Streamlit on port 8501";          Exe="wscript.exe";          PArgs="`"$TB\stop_app.vbs`"" }
        )
    },
    @{
        Label   = "AGENT"
        Actions = @(
            [pscustomobject]@{ Title="Run Agent";     Desc="Phase 1 - analyze backlog, write report"; Exe="cmd.exe"; PArgs="/k `"$TB\run_agent.bat`"" },
            [pscustomobject]@{ Title="Execute Agent"; Desc="Phase 2 - copy command, open Claude";      Exe="cmd.exe"; PArgs="/k `"$TB\execute_agent.bat`"" }
        )
    },
    @{
        Label   = "GIT"
        Actions = @(
            [pscustomobject]@{ Title="Quick Push";    Desc="Instant commit + push, no tests";  Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$TB\quick-push.ps1`"" },
            [pscustomobject]@{ Title="Close Session"; Desc="Run tests, commit and push";        Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$TB\close-session.ps1`"" }
        )
    },
    @{
        Label   = "SKILLS"
        Actions = @(
            [pscustomobject]@{ Title="SPM Bot";       Desc="Copy /spm-bot, open Claude";        Exe="powershell.exe"; PArgs="-NoProfile -Command `"Set-Clipboard '/spm-bot'; Start-Process 'https://claude.ai'`"" },
            [pscustomobject]@{ Title="Deck Designer"; Desc="Copy /techcolab-deck, open Claude";  Exe="powershell.exe"; PArgs="-NoProfile -Command `"Set-Clipboard '/techcolab-deck'; Start-Process 'https://claude.ai'`"" }
        )
    },
    @{
        Label   = "FEATURES"
        Actions = @(
            [pscustomobject]@{ Title="Call Recorder"; Desc="Record & transcribe 1on1 / English"; Exe="powershell.exe"; PArgs="-ExecutionPolicy Bypass -NoExit -File `"$CR\call-recorder.ps1`"" },
            [pscustomobject]@{ Title="Toilet Paper";  Desc="Text-to-diagram (Vite, :5173)";       Exe="cmd.exe"; PArgs="/k `"$TB\start_toilet_paper.bat`"" }
        )
    }
)

# ── Custom icon (green circle + "T") ──────────────────────────────────────────
$script:_iconBmp = New-Object System.Drawing.Bitmap(32, 32)
function New-LauncherIcon {
    $g  = [System.Drawing.Graphics]::FromImage($script:_iconBmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    $bg = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml("#02B793"))
    $g.FillEllipse($bg, 0, 0, 31, 31)
    $font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
    $sf   = New-Object System.Drawing.StringFormat
    $sf.Alignment     = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString("T", $font, [System.Drawing.Brushes]::White,
                  [System.Drawing.RectangleF]::new(0, 1, 32, 32), $sf)
    $g.Dispose(); $bg.Dispose(); $font.Dispose(); $sf.Dispose()
    $script:_iconHandle = $script:_iconBmp.GetHicon()
    $script:_icon = [System.Drawing.Icon]::FromHandle($script:_iconHandle)
    return $script:_icon
}

# ── Layout metrics (generous spacing — avoids the cramped feel) ────────────────
$winW    = 600
$pad     = 26
$colGap  = 14
$colW    = [int](($winW - $pad * 2 - $colGap) / 2)
$cardH   = 58
$rowGap  = 10
$hdrH    = 26
$grpGap  = 18   # vertical breathing room between groups

# ── Form ───────────────────────────────────────────────────────────────────────
$form = New-Object System.Windows.Forms.Form
$form.Text            = "Techco.lab Launcher"
$form.BackColor       = $clrBg
$form.ForeColor       = $clrText
$form.StartPosition   = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox     = $false
$form.ClientSize      = New-Object System.Drawing.Size($winW, 640)
$form.Font            = New-Object System.Drawing.Font("Segoe UI", 10)
$form.Icon            = New-LauncherIcon

$form.add_Shown({
    $darkMode = 1
    [DwmApi]::DwmSetWindowAttribute($form.Handle, 20, [ref]$darkMode, 4) | Out-Null
    $form.Icon = $script:_icon

    try { Start-Process "wscript.exe" -ArgumentList "`"$TB\start_silent.vbs`"" } catch {}
    if (-not (Get-Process "ollama" -ErrorAction SilentlyContinue)) {
        try { Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden } catch {}
    }
    $script:lblStatus.Text = "  Starting Streamlit & Ollama...   $(Get-Date -Format 'HH:mm:ss')"
})

# ── Header ─────────────────────────────────────────────────────────────────────
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text      = "Techco.lab"
$lblTitle.ForeColor = $clrAccent
$lblTitle.Font      = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$lblTitle.Location  = New-Object System.Drawing.Point($pad, 18)
$lblTitle.AutoSize  = $true
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text      = "Personal Toolkit Launcher"
$lblSub.ForeColor = $clrSub
$lblSub.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$lblSub.Location  = New-Object System.Drawing.Point(($pad + 1), 49)
$lblSub.AutoSize  = $true
$form.Controls.Add($lblSub)

# Thin accent divider under the header
$hdrSep = New-Object System.Windows.Forms.Panel
$hdrSep.BackColor = $clrSep
$hdrSep.Size      = New-Object System.Drawing.Size(($winW - $pad * 2), 1)
$hdrSep.Location  = New-Object System.Drawing.Point($pad, 76)
$form.Controls.Add($hdrSep)

# ── Status bar ─────────────────────────────────────────────────────────────────
$pnlStatus = New-Object System.Windows.Forms.Panel
$pnlStatus.BackColor = $clrStatus
$pnlStatus.Height    = 28
$pnlStatus.Dock      = "Bottom"
$form.Controls.Add($pnlStatus)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text      = "  Ready"
$lblStatus.ForeColor = $clrSub
$lblStatus.Font      = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblStatus.Location  = New-Object System.Drawing.Point(12, 8)
$lblStatus.AutoSize  = $true
$pnlStatus.Controls.Add($lblStatus)

# ── Hover handlers ─────────────────────────────────────────────────────────────
$onEnter = {
    param($sender, $e)
    $card = if ($sender.Tag -eq "card") { $sender } else { $sender.Parent }
    $card.BackColor = $script:clrHover
    foreach ($c in $card.Controls) {
        if ($c.Tag -eq "accent") { $c.Width = 4 } else { $c.BackColor = $script:clrHover }
    }
}
$onLeave = {
    param($sender, $e)
    $card = if ($sender.Tag -eq "card") { $sender } else { $sender.Parent }
    $card.BackColor = $script:clrCard
    foreach ($c in $card.Controls) {
        if ($c.Tag -eq "accent") { $c.Width = 0 } else { $c.BackColor = $script:clrCard }
    }
}

# ── Groups + Cards (2-column grid, generous rhythm) ───────────────────────────
$y          = 92
$firstGroup = $true

foreach ($group in $groups) {
    if (-not $firstGroup) { $y += $grpGap }
    $firstGroup = $false

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text      = ($group.Label.ToCharArray() -join " ")   # letter-spaced label
    $lbl.ForeColor = $clrMuted
    $lbl.Font      = New-Object System.Drawing.Font("Segoe UI", 7.5, [System.Drawing.FontStyle]::Bold)
    $lbl.Location  = New-Object System.Drawing.Point($pad, $y)
    $lbl.AutoSize  = $true
    $form.Controls.Add($lbl)
    $y += $hdrH

    $actions = $group.Actions
    $numRows = [Math]::Ceiling($actions.Count / 2)

    for ($ci = 0; $ci -lt $actions.Count; $ci++) {
        $a     = $actions[$ci]
        $exe   = $a.Exe
        $pargs = $a.PArgs
        $title = $a.Title

        $row  = [int]($ci / 2)
        $col  = $ci % 2
        $xPos = $pad + $col * ($colW + $colGap)
        $yPos = $y + $row * ($cardH + $rowGap)

        $card = New-Object System.Windows.Forms.Panel
        $card.BackColor = $clrCard
        $card.Size      = New-Object System.Drawing.Size($colW, $cardH)
        $card.Location  = New-Object System.Drawing.Point($xPos, $yPos)
        $card.Cursor    = [System.Windows.Forms.Cursors]::Hand
        $card.Tag       = "card"
        $form.Controls.Add($card)

        # Accent bar — hidden until hover (cleaner resting state)
        $accent = New-Object System.Windows.Forms.Panel
        $accent.BackColor = $clrAccent
        $accent.Size      = New-Object System.Drawing.Size(0, $cardH)
        $accent.Location  = New-Object System.Drawing.Point(0, 0)
        $accent.Tag       = "accent"
        $card.Controls.Add($accent)

        $lblT = New-Object System.Windows.Forms.Label
        $lblT.Text      = $a.Title
        $lblT.ForeColor = $clrText
        $lblT.BackColor = $clrCard
        $lblT.Font      = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
        $lblT.Location  = New-Object System.Drawing.Point(14, 9)
        $lblT.AutoSize  = $true
        $card.Controls.Add($lblT)

        $lblD = New-Object System.Windows.Forms.Label
        $lblD.Text        = $a.Desc
        $lblD.ForeColor   = $clrSub
        $lblD.BackColor   = $clrCard
        $lblD.Font        = New-Object System.Drawing.Font("Segoe UI", 8)
        $lblD.Location    = New-Object System.Drawing.Point(14, 32)
        $lblD.AutoSize    = $false
        $lblD.Size        = New-Object System.Drawing.Size(($colW - 22), 18)
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
                $script:lblStatus.Text = "  Launched: $title   |   $(Get-Date -Format 'HH:mm:ss')"
            } catch {
                $script:lblStatus.Text = "  Error: $_"
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
    }

    $y += $numRows * $cardH + ($numRows - 1) * $rowGap
}

# Size the window to fit content + status bar, with a comfortable bottom margin
$form.ClientSize = New-Object System.Drawing.Size($winW, ($y + 20 + $pnlStatus.Height))

[System.Windows.Forms.Application]::Run($form)

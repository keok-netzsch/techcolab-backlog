# Weekly digest - Second Brain vault system
# Reads the past 7 daily consolidation reports and summarizes them.
# Scoped to Kelvin only for now - team-wide participation breakdown needs
# per-person data the agent doesn't collect yet (source field parsing).

$ErrorActionPreference = "Stop"

$reportsDir = "C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\AI\vault-central-reports"
$digestDir = "C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\AI\vault-weekly-digests"
$today = Get-Date -Format "yyyy-MM-dd"
$weekStart = (Get-Date).AddDays(-6)

if (-not (Test-Path $digestDir)) {
    New-Item -ItemType Directory -Path $digestDir -Force | Out-Null
}

if (-not (Test-Path $reportsDir)) {
    Write-Host "No reports directory found - agent may not have run yet."
    exit 0
}

$reportFiles = Get-ChildItem $reportsDir -Filter "*.md" | Where-Object {
    $dateStr = $_.BaseName
    try {
        $fileDate = [datetime]::ParseExact($dateStr, "yyyy-MM-dd", $null)
        $fileDate -ge $weekStart.Date
    } catch {
        $false
    }
} | Sort-Object Name

if ($reportFiles.Count -eq 0) {
    Write-Host "No reports found in the last 7 days."
    exit 0
}

$totalCritical = 0
$totalWarning = 0
$totalNewFiles = 0
$daysChecked = 0
$daysWithChanges = 0

foreach ($file in $reportFiles) {
    $content = Get-Content $file.FullName -Raw
    $daysChecked++
    if ($content -match "CRITICAL") { $totalCritical++ }
    if ($content -match "WARNING") { $totalWarning++ }
    if ($content -match "New files since last check \((\d+)\)") {
        $totalNewFiles += [int]$matches[1]
        $daysWithChanges++
    }
}

$digestLines = @()
$digestLines += "# Weekly Vault Digest - $today"
$digestLines += ""
$digestLines += "Period: $($weekStart.ToString('yyyy-MM-dd')) to $today ($daysChecked reports found)"
$digestLines += ""
$digestLines += "## Summary"
$digestLines += ""
$digestLines += "- New files graduated this week: $totalNewFiles"
$digestLines += "- Days with CRITICAL flags: $totalCritical"
$digestLines += "- Days with WARNING flags: $totalWarning"
$digestLines += "- Days with any change: $daysWithChanges / $daysChecked"
$digestLines += ""

if ($totalCritical -gt 0) {
    $digestLines += "## Action needed"
    $digestLines += ""
    $digestLines += "CRITICAL flags appeared this week. Review the daily reports in AI/vault-central-reports/ before next graduation."
    $digestLines += ""
}

$digestLines += "## Reports included"
$digestLines += ""
foreach ($file in $reportFiles) {
    $digestLines += "- $($file.Name)"
}

$digestPath = Join-Path $digestDir "$today.md"
Set-Content -Path $digestPath -Value ($digestLines -join "`n") -Encoding utf8

Write-Host "Digest written to: $digestPath"

# Blocking MessageBox notification - switched from toast 2026-08-11, same reason
# as send-morning-reminder.ps1 / send-evening-push.ps1 (toast reported success but
# was never visibly seen; MessageBox cannot be silently suppressed by Focus Assist).
Add-Type -AssemblyName System.Windows.Forms

$title = "Second Brain - digest semanal"
$message = "$totalNewFiles arquivos novos essa semana. $totalCritical dias com CRITICAL. Veja AI/vault-weekly-digests/."

try {
    $form = New-Object System.Windows.Forms.Form
    $form.TopMost = $true
    $form.Opacity = 0
    $form.ShowInTaskbar = $false
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(0, 0)
    $form.Show()
    [System.Windows.Forms.MessageBox]::Show($form, $message, $title, [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    $form.Close()
    Write-Host "MessageBox shown and dismissed: $title"
} catch {
    Write-Host "MessageBox failed (digest file was still written): $($_.Exception.Message)"
}

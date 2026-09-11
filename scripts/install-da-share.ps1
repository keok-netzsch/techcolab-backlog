# Installs D&A Share on a teammate's machine: two Claude Code skills, the intake
# program, and a Friday reminder to review the queue.
#
# Order matters here. The first version wrote three user environment variables and
# copied the skills before it ever checked that Python could run the program, so a
# machine without Python — or with 3.10, which cannot import datetime.UTC — ended
# up half installed, with a green-looking setup and a broken first use. Everything
# that can fail is checked before anything is written.

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$CentralVault,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$ContributorName,

    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),

    [switch]$NoReminder
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- checks first

if (-not (Test-Path -LiteralPath $CentralVault)) {
    throw "Central vault path was not found: '$CentralVault'. Open the 10_2ndBrain folder in File Explorer, copy the path from the address bar, and use that."
}
$central = (Resolve-Path -LiteralPath $CentralVault).Path
if (-not (Test-Path -LiteralPath (Join-Path $central '_CLAUDE.md') -PathType Leaf)) {
    throw "'$central' is not the D&A central vault: _CLAUDE.md was not found there. Point this at the 10_2ndBrain folder itself, not at its parent."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    throw "Python was not found on your PATH. Install it from the Microsoft Store (search 'Python 3.12'), reopen PowerShell, and run this again."
}
$versionText = (& $python.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1) -join ''
if ($LASTEXITCODE -ne 0) { throw "Could not run '$($python.Source)': $versionText" }
$version = [version]$versionText
if ($version -lt [version]'3.8') {
    throw "D&A Share needs Python 3.8 or newer; '$($python.Source)' reports $versionText."
}

$skillsSource = Join-Path $SourceRoot '.claude\skills'
$scriptSource = Join-Path $SourceRoot 'scripts\da_intake.py'
$reminderSource = Join-Path $SourceRoot 'scripts\da-share-reminder.ps1'
if (-not (Test-Path -LiteralPath $scriptSource -PathType Leaf)) {
    throw "D&A intake program was not found at '$scriptSource'. Run this script from inside the extracted da-share-package folder."
}
if (-not $NoReminder -and -not (Test-Path -LiteralPath $reminderSource -PathType Leaf)) {
    throw "Reminder script was not found at '$reminderSource'. Re-extract the package, or pass -NoReminder."
}
foreach ($skill in @('da-compartilhar', 'da-revisar')) {
    if (-not (Test-Path -LiteralPath (Join-Path $skillsSource $skill) -PathType Container)) {
        throw "Claude Code skill source was not found: '$(Join-Path $skillsSource $skill)'."
    }
}

# ------------------------------------------------------------------- then write

$shareRoot = Join-Path $env:LOCALAPPDATA 'DAShare'
New-Item -ItemType Directory -Force -Path $shareRoot | Out-Null
$installedScript = Join-Path $shareRoot 'da_intake.py'
Copy-Item -LiteralPath $scriptSource -Destination $installedScript -Force

$claudeSkills = Join-Path $env:USERPROFILE '.claude\skills'
New-Item -ItemType Directory -Force -Path $claudeSkills | Out-Null
foreach ($skill in @('da-compartilhar', 'da-revisar')) {
    $destination = Join-Path $claudeSkills $skill
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $skillsSource $skill) -Destination $destination -Recurse -Force
}

[Environment]::SetEnvironmentVariable('DA_CENTRAL_VAULT', $central, 'User')
[Environment]::SetEnvironmentVariable('DA_CONTRIBUTOR_NAME', $ContributorName.Trim(), 'User')
[Environment]::SetEnvironmentVariable('DA_SHARE_SCRIPT', $installedScript, 'User')
$env:DA_CENTRAL_VAULT = $central
$env:DA_SHARE_SCRIPT = $installedScript

# The Friday review only happens if something asks for it. The graduation flow it
# replaces died waiting for people to remember to open a file, and nothing in the
# first version of this package reminded anyone of anything.
if (-not $NoReminder) {
    $reminder = Join-Path $shareRoot 'da-share-reminder.ps1'
    Copy-Item -LiteralPath $reminderSource -Destination $reminder -Force

    $taskName = 'D&A Share - Friday Review'
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$reminder`""
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At '09:00'
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Description 'Shows the D&A Share queue on Friday morning if anything is pending.' | Out-Null
}

# ------------------------------------------------------------- verify it runs

$check = & $python.Source $installedScript queue 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "D&A Share was installed but the intake program failed on a first run:`n$check"
}

Write-Host 'D&A Share installed.'
Write-Host "  Central vault : $central"
Write-Host "  Contributor   : $ContributorName"
Write-Host "  Python        : $($python.Source) ($versionText)"
if (-not $NoReminder) { Write-Host '  Reminder      : Fridays at 09:00, only when the queue is not empty.' }
Write-Host ''
Write-Host $check.Trim()
Write-Host ''
Write-Host 'Close and reopen Claude Code before the first use.'

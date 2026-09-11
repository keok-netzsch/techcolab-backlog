# Friday 09:00: shows the D&A Share queue, and only when it has something in it.
#
# The review that this reminds you of is the step the previous graduation flow never
# got: over 86 daily reports it emitted 1,986 checkboxes and collected 32 approvals,
# because it needed someone to remember to open a file.
#
# Two things here are deliberate, both found by running it on 2026-09-11:
#
#   Reads the variables from the User scope instead of trusting the process
#   environment. Task Scheduler inherits it, but a terminal opened before the
#   installer ran does not, and the reminder then failed claiming the vault was
#   not configured.
#
#   Does not set ErrorActionPreference to Stop. With it, Python writing a single
#   line to stderr became a NativeCommandError and the reminder died with a
#   PowerShell stack trace instead of showing the person a readable message.

$script = [Environment]::GetEnvironmentVariable('DA_SHARE_SCRIPT', 'User')
$vault = [Environment]::GetEnvironmentVariable('DA_CENTRAL_VAULT', 'User')

function Show-Message([string]$text, [string]$title) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($text, $title) | Out-Null
}

if (-not $script -or -not (Test-Path -LiteralPath $script -PathType Leaf)) {
    Show-Message "D&A Share is not installed on this machine. Run install-da-share.ps1 again." 'D&A Share'
    exit 1
}
if (-not $vault) {
    Show-Message "DA_CENTRAL_VAULT is not set. Run install-da-share.ps1 again." 'D&A Share'
    exit 1
}
$env:DA_CENTRAL_VAULT = $vault

$output = (& python $script queue 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    Show-Message "D&A Share could not read the queue:`n`n$output" 'D&A Share - error'
    exit 1
}
if ($output -match 'Nothing pending') { exit 0 }

Show-Message "$output`n`nOpen Claude Code and say: revisar minhas pendencias do D&A" 'D&A Share - review queue'
exit 0

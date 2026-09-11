# Builds Templates/da-share-package.zip, the copy of D&A Share the team installs from.
#
# This exists as a script and not as a hand-assembled zip because the zip is a
# derived artifact: when the skills or the intake program change, the zip is stale
# and the team keeps installing the old one. The first package was assembled by
# hand and shipped internal files that had to be pulled before distribution.
#
# It verifies the result instead of trusting it: every expected entry present, no
# unexpected entry, and a string from the current source found inside the zipped
# copy. A timestamp would not catch a zip built from the wrong folder.

[CmdletBinding()]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$CentralVault = [Environment]::GetEnvironmentVariable('DA_CENTRAL_VAULT', 'User')
)

$ErrorActionPreference = 'Stop'

if (-not $CentralVault) { throw 'DA_CENTRAL_VAULT is not set and -CentralVault was not given.' }
$templates = Join-Path $CentralVault 'Templates'
if (-not (Test-Path -LiteralPath $templates -PathType Container)) {
    throw "Templates folder was not found in the central vault: '$templates'"
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("da-share-build-" + [guid]::NewGuid().ToString('N'))
$package = Join-Path $staging 'da-share-package'
New-Item -ItemType Directory -Force -Path (Join-Path $package 'scripts') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $package '.claude\skills') | Out-Null

Copy-Item (Join-Path $RepoRoot 'scripts\da_intake.py') (Join-Path $package 'scripts') -Force
Copy-Item (Join-Path $RepoRoot 'scripts\install-da-share.ps1') (Join-Path $package 'scripts') -Force
Copy-Item (Join-Path $RepoRoot 'scripts\da-share-reminder.ps1') (Join-Path $package 'scripts') -Force
foreach ($skill in @('da-compartilhar', 'da-revisar')) {
    Copy-Item (Join-Path $RepoRoot ".claude\skills\$skill") `
        (Join-Path $package '.claude\skills') -Recurse -Force
}

@'
# D&A Share

Two Claude Code skills plus the program that writes to the D&A central vault.

## Install

Open PowerShell in this folder and run, with your own values:

    .\scripts\install-da-share.ps1 -CentralVault 'C:\your-path\10_2ndBrain' -ContributorName 'Your Full Name'

Then close and reopen Claude Code.

Needs Python 3.8 or newer on your PATH. The installer checks before it changes
anything, so a missing or old Python stops it with a message instead of leaving a
half-finished setup.

## What it installs

    %USERPROFILE%\.claude\skills\da-compartilhar    share something with the team
    %USERPROFILE%\.claude\skills\da-revisar         review the queue (project/area owners)
    %LOCALAPPDATA%\DAShare\da_intake.py             the program that writes
    Scheduled task "D&A Share - Friday Review"      Fridays 09:00, quiet when the queue is empty

Three user environment variables are set: DA_CENTRAL_VAULT, DA_CONTRIBUTOR_NAME and
DA_SHARE_SCRIPT. Use -NoReminder to skip the scheduled task.

## Use

Share:   "Share this decision with D&A: ..."
Check:   "What happened to what I sent to D&A?"
Review:  "revisar minhas pendencias do D&A"

The full guide is Templates/da-share-onboarding.md in the central vault.

## What it will refuse

Pay, health, identity and credentials are refused with no way around it. Ambiguous
words like "promotion" and "headcount" get one question, because in this team they
usually mean a pipeline and a dashboard column. Publishing into a folder that does
not exist is refused with a suggestion.

Nothing is ever edited, moved or deleted in the central vault.
'@ | Set-Content -LiteralPath (Join-Path $package 'README.md') -Encoding UTF8

$zip = Join-Path $templates 'da-share-package.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path $package -DestinationPath $zip -CompressionLevel Optimal

# ------------------------------------------------------------------- verify

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entries = @($archive.Entries | Where-Object { $_.Length -gt 0 } |
        ForEach-Object { $_.FullName -replace '\\', '/' })
    $expected = @(
        'da-share-package/README.md',
        'da-share-package/scripts/da_intake.py',
        'da-share-package/scripts/install-da-share.ps1',
        'da-share-package/scripts/da-share-reminder.ps1',
        'da-share-package/.claude/skills/da-compartilhar/SKILL.md',
        'da-share-package/.claude/skills/da-compartilhar/scripts/da_intake.py',
        'da-share-package/.claude/skills/da-revisar/SKILL.md',
        'da-share-package/.claude/skills/da-revisar/scripts/da_intake.py'
    )
    $missing = $expected | Where-Object { $entries -notcontains $_ }
    if ($missing) { throw "Package is missing: $($missing -join ', ')" }
    $extra = $entries | Where-Object { $expected -notcontains $_ }
    if ($extra) { throw "Package contains unexpected files: $($extra -join ', ')" }

    # Content check, not a timestamp: read the zipped copy and look for a string
    # that only the current source has.
    $marker = 'confirm_not_personal'
    $entry = $archive.GetEntry('da-share-package/scripts/da_intake.py')
    $reader = New-Object System.IO.StreamReader($entry.Open())
    $zipped = $reader.ReadToEnd()
    $reader.Dispose()
    if ($zipped -notmatch $marker) {
        throw "The zipped da_intake.py does not contain '$marker'; it was built from a stale source."
    }
    if ($zipped -match 'from datetime import UTC') {
        throw 'The zipped da_intake.py uses datetime.UTC, which needs Python 3.11.'
    }
    Write-Host "Package verified: $($entries.Count) files, source is current."
}
finally {
    $archive.Dispose()
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Written: $zip"

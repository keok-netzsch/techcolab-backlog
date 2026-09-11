[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$CentralVault,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$ContributorName,

    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'

$central = (Resolve-Path -LiteralPath $CentralVault).Path
if (-not (Test-Path -LiteralPath (Join-Path $central '_CLAUDE.md') -PathType Leaf)) {
    throw "'$central' is not a D&A central vault: _CLAUDE.md was not found."
}

$shareRoot = Join-Path $env:LOCALAPPDATA 'DAShare'
$skillsSource = Join-Path $SourceRoot '.claude\skills'
$scriptSource = Join-Path $SourceRoot 'scripts\da_intake.py'
if (-not (Test-Path -LiteralPath $scriptSource -PathType Leaf)) {
    throw "D&A intake program was not found at '$scriptSource'."
}

New-Item -ItemType Directory -Force -Path $shareRoot | Out-Null
Copy-Item -LiteralPath $scriptSource -Destination (Join-Path $shareRoot 'da_intake.py') -Force

$claudeSkills = Join-Path $env:USERPROFILE '.claude\skills'
New-Item -ItemType Directory -Force -Path $claudeSkills | Out-Null
foreach ($skill in @('da-compartilhar', 'da-revisar')) {
    $source = Join-Path $skillsSource $skill
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "Claude Code skill source was not found: '$source'."
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $claudeSkills $skill) -Recurse -Force
}

[Environment]::SetEnvironmentVariable('DA_CENTRAL_VAULT', $central, 'User')
[Environment]::SetEnvironmentVariable('DA_CONTRIBUTOR_NAME', $ContributorName.Trim(), 'User')
[Environment]::SetEnvironmentVariable('DA_SHARE_SCRIPT', (Join-Path $shareRoot 'da_intake.py'), 'User')

& python (Join-Path $shareRoot 'da_intake.py') --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Python could not run the D&A intake program.'
}

Write-Host 'D&A Share installed.'
Write-Host "Central vault: $central"
Write-Host "Contributor: $ContributorName"
Write-Host 'Close and reopen Claude Code or the terminal before the first use.'

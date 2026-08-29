# Daily consolidation check for the D&A team central vault (10_2ndBrain).
# Report-only - never writes to, edits, or deletes anything inside the central vault.
# PowerShell owns every file write in this script; the Claude invocation below is
# given Read/Glob/Grep only (no Write/Edit/Bash), so it cannot touch anything even
# if a prompt were somehow manipulated. Mirrors the read-only design decided
# 2026-08-05 (see vault/backlog.md, "agente de conciliacao" entries).
#
# Also takes a full independent backup (zip) of the vault every run, and detects
# files whose CONTENT changed (not just added/removed) via hash comparison - this
# catches manual edits made directly in Obsidian/SharePoint, outside the graduation
# flow, which the add-only rule forbids regardless of who made them. Added 2026-08-06.

$ErrorActionPreference = "Stop"

$vaultPath = "C:\Users\Kelvin.okuda\NETZSCH\Business Intelligence & Analytics - General\02_Organization\10_2ndBrain"
$snapshotPath = "C:\Users\Kelvin.okuda\techcolab-backlog\scripts\vault-central-snapshot.csv"
$reportDir = "C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\AI\vault-central-reports"
$backupDir = "C:\Users\Kelvin.okuda\VaultBackups\10_2ndBrain"
$backupRetentionDays = 30
$today = Get-Date -Format "yyyy-MM-dd"
$reportPath = Join-Path $reportDir "$today.md"

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

if (-not (Test-Path $vaultPath)) {
    Set-Content -Path $reportPath -Value "# Vault Central Consolidation Report - $today`n`nERROR: central vault path not found at $vaultPath. OneDrive may not be synced. No check performed." -Encoding utf8
    exit 1
}

# Everything from here on is wrapped in a top-level try/catch. A report-only
# safety agent that crashes silently (no report written at all) is worse than
# one that reports a problem - the person reviewing has no idea anything was
# even attempted. Confirmed happening in practice 2026-08-10: this task can
# fire in a "missed schedule catch-up" burst right after login, before the
# session is fully ready, and something in that state can kill the process
# with no report written. This wrapper guarantees a report exists either way.
try {

# --- Step 0: independent backup, off SharePoint/OneDrive, before anything else.
#     Protects against the SharePoint folder/library itself being deleted, not just
#     a single file - that scenario is NOT covered by SharePoint version history. ---
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}
$backupZipPath = Join-Path $backupDir "10_2ndBrain-$today.zip"
$backupOk = $true
$backupErrorMessage = $null
try {
    if (Test-Path $backupZipPath) { Remove-Item $backupZipPath -Force }
    Compress-Archive -Path $vaultPath -DestinationPath $backupZipPath -CompressionLevel Optimal -ErrorAction Stop
} catch {
    $backupOk = $false
    $backupErrorMessage = $_.Exception.Message
}
Get-ChildItem $backupDir -Filter "10_2ndBrain-*.zip" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$backupRetentionDays) } |
    Remove-Item -Force

# --- Step 1: mechanical diff (plain PowerShell, no LLM involved, always reliable) ---
$before = if (Test-Path $snapshotPath) { Import-Csv $snapshotPath } else { @() }
$beforePaths = $before.RelativePath
$beforeHasHash = ($before.Count -gt 0) -and ($before[0].PSObject.Properties.Name -contains 'Hash')

$after = Get-ChildItem $vaultPath -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.obsidian\\' } |
    ForEach-Object {
        [PSCustomObject]@{
            RelativePath  = $_.FullName.Substring($vaultPath.Length + 1)
            Length        = $_.Length
            LastWriteTime = $_.LastWriteTime
            Hash          = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash
        }
    }
$afterPaths = $after.RelativePath

$added = $after | Where-Object { $_.RelativePath -notin $beforePaths }
$removed = $beforePaths | Where-Object { $_ -notin $afterPaths }

$modified = @()
if ($beforeHasHash) {
    foreach ($a in $after) {
        $b = $before | Where-Object { $_.RelativePath -eq $a.RelativePath } | Select-Object -First 1
        if ($b -and $b.Hash -and $b.Hash -ne $a.Hash) {
            $modified += $a
        }
    }
}

# --- Step 2: nothing changed - short report, no Claude call, save cost/time ---
if ($added.Count -eq 0 -and $removed.Count -eq 0 -and $modified.Count -eq 0) {
    $report = "# Vault Central Consolidation Report - $today`n`n"
    $report += if ($backupOk) { "Backup: OK ($backupZipPath)`n`n" } else { "Backup: FAILED - $backupErrorMessage`n`n" }
    $report += "No changes since last check ($($before.Count) files, unchanged). Nothing to review."
    Set-Content -Path $reportPath -Value $report -Encoding utf8
    $after | Export-Csv -Path $snapshotPath -NoTypeInformation -Encoding utf8
    exit 0
}

# --- Step 3: build the report skeleton - structural safety check first, always,
#     regardless of what Claude says (this is the most important signal) ---
$reportLines = @()
$reportLines += "# Vault Central Consolidation Report - $today"
$reportLines += ""

$reportLines += "## Backup Status"
$reportLines += ""
if ($backupOk) {
    $reportLines += "Backup: **OK** - independent copy created at"
    $reportLines += "  $backupZipPath"
} else {
    $reportLines += "Backup: **FAILED** - $backupErrorMessage"
    $reportLines += "Recovery is limited to SharePoint version history only."
}
$reportLines += ""

if ($removed.Count -gt 0) {
    $reportLines += "## CRITICAL - files missing since last check"
    $reportLines += ""
    $reportLines += "These existed in the previous snapshot and are gone now. Per the vault's"
    $reportLines += "add-only rule, this should never happen without your explicit approval."
    $reportLines += "Investigate before anything else."
    $reportLines += ""
    foreach ($r in $removed) { $reportLines += "- $r" }
    $reportLines += ""
}

if ($modified.Count -gt 0) {
    $reportLines += "## WARNING - files edited in-place (not via graduation flow)"
    $reportLines += ""
    $reportLines += "These files existed in the snapshot but their content has changed"
    $reportLines += "(hash mismatch). Per the vault's add-only rule, files should never be"
    $reportLines += "edited after graduation - new versions should graduate as separate notes."
    $reportLines += "This usually means direct edits in Obsidian/SharePoint, bypassing the"
    $reportLines += "graduation review process. Flag them for manual review."
    $reportLines += ""
    foreach ($m in $modified) { $reportLines += "- $($m.RelativePath) (modified: $($m.LastWriteTime))" }
    $reportLines += ""
}

if ($added.Count -gt 0) {
    $reportLines += "## New files since last check ($($added.Count))"
    $reportLines += ""
    foreach ($a in $added) { $reportLines += "- $($a.RelativePath) ($($a.LastWriteTime))" }
    $reportLines += ""
}

# --- Step 4: Claude review of the new files' content (read-only tools only) ---
if ($added.Count -gt 0) {
    $addedList = ($added | ForEach-Object { $_.RelativePath }) -join "`n"
    $promptLines = @(
        "You are reviewing new files added to a shared team Obsidian vault (the D&A team's",
        "central vault at $vaultPath). You have Read/Glob/Grep only - you cannot write, edit,",
        "or delete anything, by design. Just analyze and report in plain text.",
        "",
        "First read _CLAUDE.md in that vault root for the full rules, and",
        "Resources/filing-and-naming-guide.md. Key rules to check each new file against:",
        "- Frontmatter required: date, type, tags, ai-first: true",
        "- Every note should open with a short 'For future Claude' preamble",
        "- If the file has a source field or text citing a personal vault, check whether",
        "  that origin was a Daily/ folder - if so, this violates the bright-line rule",
        "  (Daily/ never graduates, no exception) and should be flagged clearly",
        "- Check for content that looks personal/evaluative about a specific person",
        "  (performance, compensation, promotion, departures, leave) - that should never be",
        "  in this vault",
        "- Check the file landed in a sensible folder per the filing-and-naming-guide's",
        "  inference table",
        "",
        "New files to review (read each one):",
        $addedList,
        "",
        "For each file, write one short paragraph: file path, one-line verdict (OK or flag),",
        "and if flagged, exactly why and what you'd recommend Kelvin do about it. Keep it",
        "concise - this is a daily report, not an essay. Do not attempt to fix anything."
    )
    $prompt = $promptLines -join "`n"

    try {
        $claudeOutput = & claude -p $prompt --allowedTools "Read,Glob,Grep" 2>&1
        $reportLines += "## Claude's review of new content"
        $reportLines += ""
        $reportLines += $claudeOutput
    } catch {
        $reportLines += "## Claude's review of new content"
        $reportLines += ""
        $reportLines += "Could not run the review - claude CLI call failed: $($_.Exception.Message)"
        $reportLines += "The structural check above (added/removed files) is still accurate."
    }
}

Set-Content -Path $reportPath -Value ($reportLines -join "`n") -Encoding utf8

# --- Step 5: update the snapshot baseline for tomorrow's diff ---
$after | Export-Csv -Path $snapshotPath -NoTypeInformation -Encoding utf8

} catch {
    $crashLines = @()
    $crashLines += "# Vault Central Consolidation Report - $today"
    $crashLines += ""
    $crashLines += "## CRITICAL - agent crashed before finishing"
    $crashLines += ""
    $crashLines += "The consolidation check did not complete. Error captured:"
    $crashLines += ""
    $crashLines += "``````"
    $crashLines += "$($_.Exception.Message)"
    $crashLines += "``````"
    $crashLines += ""
    $crashLines += "This has happened before when the scheduled task fires in a 'missed"
    $crashLines += "schedule catch-up' burst right after login, before the session is fully"
    $crashLines += "ready (multiple tasks firing at once). Treat today as unaudited - the"
    $crashLines += "structural check (added/removed/modified files) did not run. If this"
    $crashLines += "keeps happening, check manually or run the script by hand:"
    $crashLines += "  cd C:\Users\Kelvin.okuda\techcolab-backlog\scripts"
    $crashLines += "  .\vault-central-consolidation-agent.ps1"
    Set-Content -Path $reportPath -Value ($crashLines -join "`n") -Encoding utf8
    exit 1
}

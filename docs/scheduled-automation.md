# Toolkit scheduled automation — consolidated map

Every unattended job on this machine, in one place. Verified against Task Scheduler on
2026-08-29. Day codes: Mon–Fri = weekdays. All scripts are local; none call external APIs
unless noted. This is the "production = hardened local" record required by the ADR
`vault/decisions/2026-08-29-doc-triad-e-producao.md`.

## Call Recorder (docs: `call-recorder/CLAUDE.md`, `GOVERNANCE.md`, `USER-GUIDE.md`)

| Task | When | Runs |
|---|---|---|
| `CallRecorder-AutoCapture` | resident (auto-start) | `call-recorder/autocapture.py` — records when Teams takes the mic |
| `CallRecorder-Queue` | daily 20:00 | `scripts/run-queue.ps1` — classifies pendings, transcribes, parks autocapture jobs for routing, then sweeps failed transcripts. Single-flight: `recordings/.queue.lock` (PID); a second queue exits without touching anything |
| `CallRecorder-Triage-Reminder` | weekdays 09:00 | `scripts/triage-reminder.ps1` — morning review prompt |

## Team Memory Agent (docs: `~/TeamMemoryAgent/README.md` + GOVERNANCE + USER-GUIDE)

| Task | When | Runs |
|---|---|---|
| `TeamMemoryAgent-Capture` | hourly | `bin/tma_capture.py` |
| `TeamMemoryAgent-Weekly` | hourly | `bin/tma_weekly.py` — consolidates Fridays, graduates approved drafts every run |

## Vault (personal + team library)

| Task | When | Runs |
|---|---|---|
| `D&A Vault - Morning Reminder` | weekdays 07:35 | `scripts/send-morning-reminder.ps1` |
| `D&A Vault - Evening Push` | weekdays 16:30 | `scripts/send-evening-push.ps1` |
| `D&A Vault - Weekly Digest` | Fri 16:00 | `scripts/generate-weekly-vault-digest.ps1` |
| `D&A Vault Central Consolidation` | daily 08:15 | `scripts/vault-central-consolidation-agent.ps1` — read-only watch of 10_2ndBrain graduation |
| `D&A Vault Central Sensitive Scan` | 08:25 + hourly | `scripts/vault-central-sensitive-scan.ps1` vs `vault-central-sensitive-baseline.json` |

## Backlog / Toolkit 2.0

| Task | When | Runs |
|---|---|---|
| `TechColab Backlog Agent` | daily 07:00 | `run_agent_silent.vbs` — daily agent run + recording-queue health check (flags pendings >36h, jobs >36h, parked routing >72h, `.exhausted`) |
| `triagem-gravacoes` | weekdays 09:00 | Claude scheduled routine (not Task Scheduler) — reads `route.py --json` and proposes content-based routing slices |
| `closer-semanal` | Mon 08:30 | Claude scheduled routine (not Task Scheduler) — reads weekly brief + backlog, drafts actions for one-line approval |
| `TechColab Opus Price Recalc` | Mon 08:35 | `recalc_opus_price.bat` → `scripts/recalc_opus_price.py` |

## Study / usage

| Task | When | Runs |
|---|---|---|
| `TechColab English Coach` | Mon 08:30 | `run_english_coach.bat` → `agent/english_coach.py` |
| `CDMP Daily Study Reminder` | weekdays 15:30 | vault `cdmp-notify.ps1` |
| `study-notify-diario` | daily 15:40 | vault `study-notify.ps1` — study-monitor toast (reads `study-plan.json` + area trackers, zero LLM); created 2026-08-29, pairs with the `/study` skill |
| `NETZSCH-AI-Usage-Capture` | daily 09:00 | `~/NETZSCH-AI-Usage/Capture-Usage.ps1` |

## Disabled / retired

- `TechColab Daily Agent` — **deleted 2026-08-29** (was the second task pointing at
  `run_agent.bat`; the duplication starved the transcription queue). Definition backed up
  at `vault/rollback/techcolab-daily-agent-2026-08-29/` in the personal vault.

## Rules for changing anything here

- New scheduled job → add it to this table in the same change.
- A task that touches a window/foreground: check for a live Teams call first
  (2026-08-28 incident: a task stole focus mid-call with camera on).
- The vault is on OneDrive: clock skew has bitten before — verify dates with
  `Get-Date` before trusting file mtimes.

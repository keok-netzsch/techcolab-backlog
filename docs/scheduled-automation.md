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
| `CallRecorder-Triage-Reminder` | weekdays 09:00 | `scripts/notify.ps1 -Profile triage-reminder` — morning review prompt; silent when nothing is parked |

## Team Memory Agent (docs: `~/TeamMemoryAgent/README.md` + GOVERNANCE + USER-GUIDE)

| Task | When | Runs |
|---|---|---|
| `TeamMemoryAgent-Capture` | hourly | `bin/tma_capture.py` |
| `TeamMemoryAgent-Weekly` | hourly | `bin/tma_weekly.py` — consolidates Fridays, graduates approved drafts every run |

## Vault (personal + team library)

| Task | When | Runs |
|---|---|---|
| `D&A Vault - Morning Reminder` | weekdays 07:35 | `scripts/notify.ps1 -Profile morning-reminder` |
| `D&A Vault - Evening Push` | weekdays 16:30 | `scripts/notify.ps1 -Profile evening-push` |
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
| `cdmp-diario` | daily 15:37 | Claude scheduled routine (not Task Scheduler) — generates 1 ready CDMP practice question via the cdmp skill (was missing from this map; added 2026-08-31) |
| `study-diario` | daily 15:40 | Claude scheduled routine (not Task Scheduler) — opens a `/study` session with status + day menu and waits for Kelvin in the app's routines area; interactive from there. Created 2026-08-31, pairs with the `study-reminder` toast |
| `study-notify-diario` | daily 15:40 | `scripts/notify.ps1 -Profile study-reminder` → body from `scripts/notify-body/study-body.ps1` (reads `study-plan.json` + area trackers, zero LLM; silent when every active area already studied today); pairs with the `/study` skill. Migrated to the engine 2026-08-30 as messagebox (was balloon — Focus Assist rationale); old `vault/study-notify.ps1` retired |
| `NETZSCH-AI-Usage-Capture` | daily 09:00 | `~/NETZSCH-AI-Usage/Capture-Usage.ps1` |

## Disabled / retired

- `TechColab Daily Agent` — **deleted 2026-08-29** (was the second task pointing at
  `run_agent.bat`; the duplication starved the transcription queue). Definition backed up
  at `vault/rollback/techcolab-daily-agent-2026-08-29/` in the personal vault.

## Notification engine (P3, since 2026-08-30)

Reminders no longer have one script each. They are profiles in
`scripts/notify-config.json`, fired by `scripts/notify.ps1 -Profile <name>`:

```
scripts\notify.ps1 -List                          # what profiles exist
scripts\notify.ps1 -Profile triage-reminder -WhatIf   # resolve and print, open no window
```

Two window modes, and the choice is not cosmetic. `messagebox` (WinForms, TopMost,
blocking) is the right mode for a reminder that must not be missed — it bypasses Focus
Assist, which in 2026-08-11 was silently swallowing toasts while the API reported success.
`balloon` (tray NotifyIcon) is less intrusive and *can* be suppressed; it exists because
the CDMP reminder still uses it (the study reminder switched to messagebox on 2026-08-30).

A profile's body is either fixed (`message`) or generated (`messageScript` → a script in
`scripts/notify-body/` that prints the body). **A generator that prints nothing produces
no window** — a reminder that fires on an empty day stops being read.

Still on its own script, by design (see `_pendentes` in the config): `CDMP Daily Study
Reminder`, which also sends e-mail via Outlook COM — the engine only notifies, so
migrating it needs a decision on what happens to the e-mail.

Old scripts are kept in `scripts/_retired-notify-2026-08-30/` for rollback.

## Rules for changing anything here

- New scheduled job → add it to this table in the same change.
- New reminder → add a **profile** to `notify-config.json`; do not write another script.
- A task that touches a window/foreground: check for a live Teams call first
  (2026-08-28 incident: a task stole focus mid-call with camera on).
- The vault is on OneDrive: clock skew has bitten before — verify dates with
  `Get-Date` before trusting file mtimes.

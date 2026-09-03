# Toolkit scheduled automation — consolidated map

Every unattended job on this machine, in one place. Verified against Task Scheduler on
2026-08-29. Day codes: Mon–Fri = weekdays. All scripts are local; none call external APIs
unless noted. This is the "production = hardened local" record required by the ADR
`vault/decisions/2026-08-29-doc-triad-e-producao.md`.

## Call Recorder (docs: `call-recorder/CLAUDE.md`, `GOVERNANCE.md`, `USER-GUIDE.md`)

| Task | When | Runs |
|---|---|---|
| `CallRecorder-AutoCapture` | resident (auto-start) | `call-recorder/autocapture.py` — records when Teams takes the mic |
| `CallRecorder-Queue` | daily 20:00, **12h limit** | `scripts/run-queue.ps1` — classifies pendings, transcribes, parks autocapture jobs for routing, then sweeps failed transcripts. Single-flight: `recordings/.queue.lock` (PID); a second queue exits without touching anything. Limit raised from 6h on 2026-09-01: the 31/08 run was **killed** by the old cap (`0x41306`), which is how a 27/08 recording sat unprocessed for two days with nothing reporting it. A cap sized for the typical day guarantees the queue can never catch up on a backlog — the 01/09 batch was 6.6h of work against a 6h cap. Still finite: a hung Whisper holding the lock would block the following night, and orphan-lock cleanup only covers a dead PID |
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
| `TechColab Vault Index` | daily 18:00 (**since 2026-09-03**) | `scripts/vault-index-nightly.ps1` → `python -m vaultindex build --embed` with the repo `.venv`: incremental index of the vault + local ONNX embeddings for the chunks that lack one, then `lint` (regenerates `_reports/Vault-Lint.md`, 2 s). Log `logs/vault-index-YYYY-MM.log`. 18:00 sits after `vault-daily-commit` (17:30). 1h limit is slack, not an estimate: the typical night takes seconds. Exit 3 = a search refresh held the lock at that instant; tomorrow catches up. Docs: `docs/vault-index.md`, governance `docs/vault-index-governanca.md`, ADR 2026-09-03 (idea-097) |

## Backlog / Toolkit 2.0

| Task | When | Runs |
|---|---|---|
| `TechColab Backlog Agent` | daily 07:00 | `run_agent_silent.vbs` — daily agent run + recording-queue health check (flags pendings >36h, jobs >36h, parked routing >72h, `.exhausted`) |
| `TechColab Todo Reminder` | weekdays 08:45 | `notify.ps1 -Profile todo-reminder` — overdue/due-today action items extracted from calls (+ curation count); silent on empty days |
| `pendencias-do-kelvin` | weekdays 08:30 (**1×/dia desde 2026-08-31**; era 3×: 08:30/13:30/17:30) | Claude scheduled routine — renders the pending ledger as a clickable widget and closes what Kelvin resolves. Dedicated session on purpose (his ask, 2026-08-31): the ritual must not get lost inside coding sessions |
| `triagem-gravacoes` | weekdays 09:00 | Claude scheduled routine (not Task Scheduler) — reads `route.py --json` and proposes content-based routing slices |
| `closer-semanal` | Mon 08:30 | Claude scheduled routine (not Task Scheduler) — reads weekly brief + backlog, drafts actions for one-line approval |
| `TechColab Opus Price Recalc` | Mon 08:35 | `recalc_opus_price.bat` → `scripts/recalc_opus_price.py` |

## Study / usage

| Task | When | Runs |
|---|---|---|
| `TechColab English Coach` | Mon 08:30 | `run_english_coach.bat` → `agent/english_coach.py` |
| `CDMP Daily Study Reminder` | weekdays 15:30 | vault `study-tools/cdmp/cdmp-notify.ps1` (a ação da tarefa foi repontada em 2026-09-02, quando o estado de estudo saiu de `vault/` para `vault/study-tools/<área>/`) |
| `study-diario` | daily 15:40 | Claude scheduled routine (not Task Scheduler) — the **single** study routine: `/study` status + day menu, and when the focus is CDMP it already delivers the ready question. **Absorbed `cdmp-diario` on 2026-08-31** (it fired 3 min earlier for the same purpose). Pairs with the `study-reminder` toast |
| `study-notify-diario` | daily 15:40 | `scripts/notify.ps1 -Profile study-reminder` → body from `scripts/notify-body/study-body.ps1` (reads `study-tools/study/study-plan.json` + area trackers, zero LLM; silent when every active area already studied today); pairs with the `/study` skill. Migrated to the engine 2026-08-30 as messagebox (was balloon — Focus Assist rationale); old `vault/study-notify.ps1` retired |
| `NETZSCH-AI-Usage-Capture` | daily 09:00 | `~/NETZSCH-AI-Usage/Capture-Usage.ps1` |


## Claude scheduled routines — the full list

These do NOT live in Task Scheduler. They are Claude routines, listed by
`list_scheduled_tasks`, each backed by a `SKILL.md` under
`C:\Users\Kelvin.okuda\.claude\scheduled-tasks\<taskId>\`. They fire a fresh Claude
session at the cron time, and each one carries a jitter of a few minutes, so the wall-clock
time drifts from the cron expression.

Verified against `list_scheduled_tasks` on 2026-09-02. Until that date this file listed only
4 of them; 6 had been created without the table being updated, which is exactly the gap the
rule at the bottom exists to prevent.

| Routine | Cron | When | What it does |
|---|---|---|---|
| `pendencias-do-kelvin` | `30 8 * * 1-5` | weekdays 08:30 | Renders the pending ledger as a clickable widget and closes what Kelvin resolves. Dedicated session on purpose (his ask, 2026-08-31): the ritual must not get lost inside coding sessions. **1×/day since 2026-08-31**, was 3× |
| `linkedin-engagement-reminder` | `0 8 * * 2,4` | Tue and Thu 08:00 | Reminder to engage on LinkedIn across the 3 pillars before the golden hour. **2×/week since 2026-09-02**, was every weekday |
| `closer-semanal` | `30 8 * * 1` | Mon 08:30 | Reads the weekly brief + backlog and drafts the action for every open point, ready for one-line approval |
| `triagem-gravacoes` | `0 9 * * 1-5` | weekdays 09:00 | Reads the calls transcribed overnight and proposes, by subject, where each slice should be filed in the vault. Kelvin decides |
| `team-memory-alerta` | `7 11 * * 1-5` | weekdays 11:07 | Checks whether the Team Memory Agent captured and drafted today; speaks only on failure |
| `study-diario` | `40 15 * * *` | daily 15:40 | The single study routine: `/study` status + day menu, and when the focus is CDMP it already delivers the question. Absorbed `cdmp-diario` on 2026-08-31 |
| `vault-daily-commit` | `30 17 * * 1-5` | weekdays 17:30 | Consolidates the daily note, commits the local vault, and proposes what deserves to graduate to the central vault. Absorbed `vault-central-graduation` on 2026-08-31 |
| `timesheet-check-sexta` | `40 16 * * 5` | Fri 16:40 | Weekly ServiceNow timesheet check for the team (coverage + quality) |
| `organize-downloads-semanal` | `0 20 * * 0` | Sun 20:00 | Reorganises the Downloads folder, reversible, deletes nothing |
| `lembrete-fechamento-fatura` | `0 9 28 * *` | day 28, 09:00 | Monthly reminder to update bank balance and card statements, with the previous month's closing report |

Personal, not work: `linkedin-engagement-reminder`, `organize-downloads-semanal` and
`lembrete-fechamento-fatura`.

Four of these also appear in the topic tables above, where their domain context lives.
This table is the authoritative list of what exists.

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

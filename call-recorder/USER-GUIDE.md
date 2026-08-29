# Call Recorder — user guide

Audience: Kelvin. Since 2.0 the system is autonomous — you don't start recordings and you
don't run commands during the day. Your touchpoints are two: the morning triage and the
occasional manual recording.

## What happens without you

1. **Recording starts and stops by itself** when Teams takes/releases the mic
   (`CallRecorder-AutoCapture`, resident). Two channels: ch0 = you, ch1 = the other side.
2. **20:00 daily** — the queue (`CallRecorder-Queue`) transcribes the day's recordings
   (Whisper, local). Autocaptured jobs are then **parked** (`.job.json.routing`), not filed.
3. **09:00 weekdays** — the triage reminder (`CallRecorder-Triage-Reminder`) points you at
   yesterday's parked transcripts.

## Your morning triage (the one ritual)

Review the parked jobs and let `route.py` file them by content — one call can feed
several destinations (a 1:1 note, an OKR mention, a backlog idea). Remember:

- **Daily BIZ / Daily PM recordings are not yours to route** — they belong to the Team
  Memory Agent flow and its approval gate.
- A recording that should not exist (personal call, sensitive matter): delete it at
  triage. Nothing has been filed yet — that is the point of parking.

## Manual recording

Start one yourself (Raycast launcher / `call-recorder.ps1`) when you already know the
destination — manual recordings skip the parking and route straight through.

## English coach

Mondays 08:30 (`TechColab English Coach`) the coach evaluates your English calls against
B2 business level — see `docs/english-practice-architecture.md` in the repo root for how
it works. Use `--topic` when you want a themed session.

## When something looks wrong

- **A call is missing:** check the Windows volume mixer first — a dead channel usually
  means Windows gave another app exclusive control of the device, not a code bug. Test
  mics with your real voice only; synthetic tones pick up jack crosstalk and lie.
- **Nothing transcribed at 16:00:** normal — the batch runs at 20:00. Review is in the
  morning.
- Logs: `autocapture.log` in this folder, and `logs/` in the repo root for coach/queue.

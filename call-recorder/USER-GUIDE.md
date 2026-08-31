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

## What the routing session extracts for you (since 2026-08-31)

While routing, the 09:00 session also pulls two things out of each call:

- **Commitments** — written into the routed notes as `- [ ] (Owner) text @YYYY-MM-DD`.
  These feed `Action-Dashboard.md` and the **08:45 weekday reminder**, which pops only
  when something is overdue or due today (silent otherwise).
- **Opportunities** — filed into the backlog with status *em análise*. That status IS
  your curation queue: approve or reject them in the app (or tell Claude), and the
  08:45 reminder shows the pending count.

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

## Aprovar o que o modelo escreveu sobre uma pessoa (desde 2026-08-31)

PDI, OKR e Overview **não recebem mais texto do modelo direto**. O que ele propõe fica
parado até você aprovar. O `1on1.md` continua automático — é log de sessão, não afirmação
sobre a pessoa.

Por que existe: em 03/06 o modelo inventou uma "Daniela" como responsável por um objetivo
da Ana, a partir de uma call sobre o projeto ENH, e isso entrou no PDI, no OKR, no
Overview e no dashboard sem ninguém ver.

**Você não precisa abrir o Obsidian.** Cada proposta vira uma pendência no ledger, então
ela aparece onde você já olha: a página de pendências do app e a rotina
`pendencias-do-kelvin` das 08:30. Aprovar ou descartar é uma ação:

```
python call-recorder/process.py review                                   # o que espera, com os ids
python call-recorder/process.py review --approve Ana-Leite/2026-06-03-PDI
python call-recorder/process.py review --reject  Ana-Leite/2026-06-03-PDI
```

Na prática você diz ao Claude "aprova o PDI da Ana" ou clica na pendência — o comando é o
que roda por baixo. Aprovar aplica **só aquela** proposta; as outras continuam esperando.
Descartar não apaga: o texto vai para `_rejected/`, caso você queira ver depois.

Se quiser corrigir antes de aprovar, peça a correção ao Claude (ou edite o arquivo em
`_review/`, se preferir) — o que entra no arquivo real é o texto revisado, não o original
do modelo.

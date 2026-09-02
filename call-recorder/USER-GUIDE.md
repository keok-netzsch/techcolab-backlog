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

## Stefan and Alberto jump the queue (since 2026-09-02)

The 20:00 queue used to transcribe strictly oldest-first, so a call with your boss
recorded this morning waited behind every older recording in the batch. It no longer
does: anything whose Teams title or resolved target points at Stefan Lautenschlager
or Alberto Reuters is transcribed first, and the rest of the batch keeps its usual
oldest-first order.

Two things this does **not** do:

- It does not change where a call is filed. Routing still happens in the morning
  triage, against the content, with you deciding. The queue only picks what to
  transcribe first.
- It does not tell the two Stefans apart. A title that says only "Stefan" gets
  priority either way, which is cheap to be wrong about; the destination is never
  guessed from a first name.

To run one specific call now instead of waiting for 20:00:

```powershell
python process_one.py 2026-09-02_08-03
```

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

## One call can leave several notes on the same person (since 2026-09-01)

If a call covers three subjects with the same person, you get three notes, not one.
Each carries its subject in the heading (`## 2026-08-27 - GPTW`) and in the filename
(`2026-08-27_1on1_Alberto-Reuters.gptw.md`), so you can tell them apart and find the
exact slice of transcript behind each.

Until 2026-09-01 the second note silently overwrote the first. Nothing warned you:
the routing said it had filed three destinations and the folder held one. If you are
looking at notes filed before that date and a day feels thinner than the
conversation was, that is why - the audio and the full transcript were never
touched, so it can be routed again.

## Someone refuses to be recorded

One command, right after the call — it does not matter that the recording already
happened:

```powershell
python "$env:USERPROFILE\techcolab-backlog\call-recorder\process.py" objecao --motivo "Fulano pediu para nao gravar"
```

With no `--alvo` it marks the **last** recording, which is the usual case. You can also
pass part of the filename (`--alvo Ana-Leite`) or a full path.

What that does: the audio **stays** on disk and is **never transcribed** — no job, no
Whisper, no vault note, and the 7-day cleanup leaves it alone. Nothing is deleted, so
there is no way to lose the wrong call by acting fast.

- `--listar` — what is currently marked
- `--desfazer` — marked the wrong one; the recording goes back into the queue
- If that call had *already* been transcribed, the command says so and leaves the
  transcript alone. Deleting it is your call, and you can just ask Claude.

## Manual recording

Start one yourself (Raycast launcher / `call-recorder.ps1`) when you already know the
destination — manual recordings skip the parking and route straight through.

## English coach

Since 2026-08-31 the session note opens with **Contexto da call** — two sentences
on what the conversation was about, so the feedback is not judging sentences with
no idea what they answered. It is generated on your machine (Ollama); only your
own speech ever leaves it.

Long calls are now evaluated **in full**. Before that a 5.000-character cap —
sized for the old local model — meant a long call was graded on about a fifth of
what you said.

Mondays 08:30 (`TechColab English Coach`) the coach evaluates your English calls against
B2 business level — see `docs/english-practice-architecture.md` in the repo root for how
it works. Use `--topic` when you want a themed session.

## What the quality gate now catches (since 2026-09-02)

`python transcript_quality.py --todos` flags a transcript when it finds a decoder
loop (short lines repeating about a second apart), a stretch in a non-Latin
alphabet, or lines that are only punctuation. It is advisory and never blocks.

One thing it cannot catch, and you should know before trusting any transcript of
a call that switched languages: **translation**. Whisper picks one language per
recording. If a call starts in Portuguese and continues in English, the English
half comes out as fluent Portuguese, and no text check can tell that apart from a
real Portuguese transcript. If a recording holds two calls in two languages, treat
the second one as a paraphrase until it is re-transcribed with its own language.

## Filing is faster now, and a hand-corrected note is safe (since 2026-09-02)

Structuring a 1:1, a stakeholder call or an agenda runs on the NETZSCH gateway
instead of the local model. A batch that took hours now takes minutes, and the
laptop stops swapping while it runs. Inbox notes still run locally.

If you corrected a note by hand, reprocessing that call will not overwrite it. It
stops and tells you which note is protected and why. To overwrite anyway:

```powershell
python process.py transcript --person Ana-Leite --transcript <ficheiro> --date 2026-08-27 --force
```

Use `--force` when you know the old note is worse than what the model will write.
The default is the other way round because it already went wrong once: on
2026-09-02 three notes were regenerated from cleaner transcripts and all three came
out worse, because the model rewrote away corrections a human had made.

## When something looks wrong

- **A call is missing:** check the Windows volume mixer first — a dead channel usually
  means Windows gave another app exclusive control of the device, not a code bug. Test
  mics with your real voice only; synthetic tones pick up jack crosstalk and lie.
- **Nothing transcribed at 16:00:** normal — the batch runs at 20:00. Review is in the
  morning.
- **The transcript repeats itself, or is in a language nobody spoke.** That is Whisper
  degenerating on silence, not a mis-heard word. Do not forward it and do not treat it
  as a record of what was said — the text tracks the real speech loosely enough to look
  plausible while being wrong. The cause was fixed on 2026-09-01 (`vad_filter` was
  missing on the 2-channel path), so new transcripts should not do this. If one still
  does, say so instead of cleaning it by hand.
- **`route.py` prints `[HOLD] N job(s) segurado(s)`:** those recordings were pulled out
  of the routing queue on purpose because their transcripts are not trustworthy. Read
  `recordings/LEIA-ANTES-DE-ROTEAR.md` before releasing them — it says why and how.
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

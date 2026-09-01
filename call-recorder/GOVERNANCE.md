# Call Recorder — purpose & governance (business documentation)

Owner: Kelvin Okuda. Technical documentation: [CLAUDE.md](CLAUDE.md) (architecture 2.0,
dead assumptions, routing). User guide: [USER-GUIDE.md](USER-GUIDE.md).

## Why this exists

Calls are where decisions, feedback and commitments actually happen, and they evaporated.
The recorder turns Kelvin's Teams calls into transcripts that feed the vault (stakeholder
notes, 1:1 records, backlog captures) and the English coach. Version 2.0 exists because
1.x recorded only the microphone: measured on the 2026-08-26 1:1s, 18–53% of each call —
the other person talking — was simply missing.

## Privacy posture (facts on record)

- **Everything is local.** Recording (WASAPI, 2 channels), transcription (Whisper on CPU)
  and English evaluation (Ollama) run on this machine. No API keys, no cloud audio.
- **Channel separation is the attribution.** ch0 = Kelvin's mic, ch1 = the other party.
  No voice identification is performed; attribution comes from the physical channel.
- **Routing is content-based and human-reviewable**: autocaptured recordings are parked
  after transcription (`.job.json.routing`) and filed by `route.py`; the morning triage
  is Kelvin's review point before anything settles in the vault.
- **Daily BIZ / Daily PM are Team Memory Agent territory** (Kelvin's routing decision,
  2026-08-29) — team meeting records go through the TMA approval gate, not the recorder's
  direct routing (see `~/TeamMemoryAgent/GOVERNANCE.md`).
- Transcripts land in the personal vault, which is local-only and never pushed to a
  remote (vault git rule).

## Consent — decided, not open

Kelvin decided this on 2026-08-26, and the decision is recorded in `CLAUDE.md`:
**autocapture stays on by default, and he discloses the recording himself, case by case.**

What that means for anyone touching this code: do **not** add prompts, banners or nags on
his behalf, and do **not** quietly disable capture either. The existing controls are
considered sufficient — the `autocapture.paused` file and `CAPTURE_SYSTEM_AUDIO=0`.

**How he does it (his words, 2026-08-31):** *"Eu irei informar as pessoas."* Disclosure is
his, spoken, per situation — not a banner this software puts on the screen.

**If someone objects — DECIDED 2026-09-01: keep and mark.** He asked in August whether the
other party's audio could be discarded (it can — capture is 2-channel and `ch1` is the
other side). Offered the three options, his words were **"manter e marcar"** (ledger
`P-017`, after resolving it with *"ok, concordo"*).

So the recording is **not deleted and not transcribed**. The `.wav` stays in `recordings/`
with a `<base>.no-consent.json` sidecar next to it, and every stage that would have
consumed that audio stops consuming it: `classify.py` does not create a job, the 20:00
queue does not transcribe (the job is parked as `.job.json.no-consent`), and retention
neither prunes nor quarantines it.

```powershell
python "$env:USERPROFILE\techcolab-backlog\call-recorder\process.py" objecao --motivo "Fulano pediu para nao gravar"
```

Two properties of this policy that are deliberate, not oversights:

- **The mark deletes nothing** — not the audio, and not a transcript that already exists.
  If the call had already been transcribed, the command says so out loud and leaves the
  transcript alone: what to do with something already produced is his decision, per case.
  A command that silently destroyed prior output would be worse than no command.
- **The audio is kept indefinitely**, outside the 7-day rule. It never gets a transcript,
  so under the previous logic it would have been read as an orphan and deleted within the
  week — which is the opposite of what he chose. `_recording_state` returns `no-consent`
  before any other verdict for exactly this reason.

Reversible with `--desfazer` (marked the wrong call), which also returns the job to the
queue. `--listar` shows what is currently marked.

(An earlier version of this document listed consent as an open question. That was an error
of research, not a gap in the decision: the answer was already in `CLAUDE.md`. Corrected
2026-08-30.)

## Retention — DECIDED 2026-08-31

Kelvin confirmed the current numbers as policy (ledger `P-005`, his words: *"por mim
ok"*). They are no longer an implementation state:

- Audio that was **successfully transcribed** is deleted after **7 days**
  (`RECORDINGS_RETENTION_DAYS`, enforced by the 07:00 agent).
- Audio that never produced a usable transcript is **quarantined into `failed/`**, not
  deleted — deleting it would destroy the only copy of a call the pipeline failed on.
- Audio marked after an objection (`no-consent`, 2026-09-01) is **kept indefinitely and
  never transcribed** — it is neither pruned nor quarantined. See the consent section.
- **Transcripts are kept indefinitely.**

Changing any of these is a policy change: ask him, do not infer it from a cleanup task.

## Nothing open

Every policy question this document has carried is decided: consent (2026-08-26),
retention (2026-08-31) and what to do when someone objects (2026-09-01), above.

A note worth keeping, because it cost twice: this doc listed consent as "open" after the
decision already existed in `CLAUDE.md`, and a session (this one, 2026-08-31) read the
stale text and filed `P-004` in the pending ledger — a pendência for a decision Kelvin had
already made. **Before writing that something "awaits Kelvin", check whether he already
decided it**; a stale "OPEN" heading is not evidence of an open question.

## Gate de aprovação para arquivos canônicos de pessoas (2026-08-31)

`PDI.md`, `OKR.md` e `Overview.md` não são log: são o que o vault **afirma ser verdade**
sobre uma pessoa, e alimentam decisão de carreira. Até esta data um modelo local de 7B
escrevia neles sem revisão, direto de uma transcrição do Whisper.

**O custo está documentado.** Em 2026-06-03, de uma call sobre o projeto ENH, o modelo
produziu um objetivo cujo responsável era uma "Daniela" — nome que ninguém do time
reconhece — e o pipeline gravou isso no PDI, no OKR, no Overview, no 1on1 e no
Action-Dashboard da Ana Leite. O mesmo parágrafo afirmava que a reunião discutiu "a
criação de um quarto adequado". Ficou lá quase três meses, e a aba Team do app exibia
como fato.

Agora esses blocos param em `Team/<Pessoa>/_review/` como **proposta**. Só entram no
arquivo real quando um humano aprova — e aprovar é uma **ação**
(`process.py review --approve <id>`), não uma edição de arquivo. Regra do Kelvin
(2026-08-31): *o vault é camada de registro, não camada de interação* — ele não aprova
nada abrindo o Obsidian. Cada proposta também vira uma pendência no ledger, para aparecer
na página de pendências do app e na rotina `pendencias-do-kelvin` das 08:30, que é onde
ele de fato olha. Silêncio não é consentimento: proposta não aprovada nunca é aplicada, e
descartar move para `_rejected/` em vez de apagar.

Mesma forma do gate do Team Memory Agent, e pela mesma razão: **nada vira fato sobre uma
pessoa sem alguém dizer que é.**

`1on1.md` fica de fora do gate de propósito — é registro datado do que foi dito numa
sessão, não uma afirmação sobre a pessoa, e uma linha errada ali está visivelmente
atrelada a um dia.

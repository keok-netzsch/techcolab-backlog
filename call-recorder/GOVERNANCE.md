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

(An earlier version of this document listed consent as an open question. That was an error
of research, not a gap in the decision: the answer was already in `CLAUDE.md`. Corrected
2026-08-30.)

## OPEN — needs Kelvin's answer before this document is complete

One question remains, and it is a policy call nobody else can make:

1. **Retention:** how long SHOULD raw audio and transcripts be kept? What runs today
   (fact, not the answer): audio that was **successfully transcribed** is deleted after
   7 days (`RECORDINGS_RETENTION_DAYS`, enforced by the 07:00 agent); audio that never
   produced a usable transcript is quarantined into `failed/`, not deleted; transcripts
   themselves are kept indefinitely. Whether 7 days / indefinitely are the RIGHT numbers
   — and what the rule for transcripts should be — is Kelvin's call.

Until it is answered, the mechanical defaults above stay as they are — they are an
implementation state, not a policy.

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

Agora esses blocos param em `Team/<Pessoa>/_review/` como **proposta**, com
`status: draft`. Só entram no arquivo real depois que um humano lê, corrige e marca
`approved` (`process.py review --apply`). Silêncio não é consentimento: o que continua
`draft` nunca é aplicado.

Mesma forma do gate do Team Memory Agent, e pela mesma razão: **nada vira fato sobre uma
pessoa sem alguém dizer que é.**

`1on1.md` fica de fora do gate de propósito — é registro datado do que foi dito numa
sessão, não uma afirmação sobre a pessoa, e uma linha errada ali está visivelmente
atrelada a um dia.

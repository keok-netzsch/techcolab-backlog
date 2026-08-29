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

## OPEN — needs Kelvin's answer before this document is complete

These two facts cannot be written by anyone but Kelvin, and this doc is explicitly
incomplete without them:

1. **Consent/awareness:** how are the other parties informed that calls with Kelvin may
   be recorded and transcribed? (Standing notice to the team? Per-call? Not yet done?)
2. **Retention:** how long SHOULD raw audio and transcripts be kept? What runs today
   (fact, not the answer): audio that was **successfully transcribed** is deleted after
   7 days (`RECORDINGS_RETENTION_DAYS`, enforced by the 07:00 agent); audio that never
   produced a usable transcript is quarantined into `failed/`, not deleted; transcripts
   themselves are kept indefinitely. Whether 7 days / indefinitely are the RIGHT numbers
   — and what the rule for transcripts should be — is Kelvin's call.

Until (1) is answered, treat recordings of anyone outside the direct team as
review-before-filing. Until (2) is answered, the current mechanical defaults above stay
as-is — they are an implementation state, not a policy.

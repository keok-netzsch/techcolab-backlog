# English Practice — Architecture Proposal

**Project:** techcolab-backlog personal toolkit  
**Feature:** Conversational English practice with automatic coach evaluation and vault persistence  
**Date:** 2026-06-02  
**Status:** Pre-implementation — pending senior review

---

## 1. Context

The toolkit already has an English Coach pipeline:

```
english-coach.ps1 → record.py (Whisper STT) → coach.py (Ollama eval) → Obsidian vault
```

This feature extends it with a **conversational practice loop** — a dedicated mode where the user speaks in English with an AI interlocutor, receives spoken responses, and at the end of the session the full transcript is automatically routed through the existing `coach.py` evaluation pipeline.

---

## 2. Stack (100% local, zero cost)

| Layer | Component | Detail |
|---|---|---|
| UI | Streamlit (existing) | New page added to `app.py` |
| Audio capture | `sounddevice` (existing) | System mic via Python, same as `record.py` |
| STT | `faster-whisper` medium (existing) | CPU, int8, `~1.4 GB` model already on disk |
| LLM conversation | Ollama `qwen2.5-coder:latest` (existing) | `http://localhost:11434` |
| TTS | `edge-tts` (new dependency) | Microsoft neural voices, free, no API key |
| Audio playback | `pygame` or `playsound` (new dependency) | Plays the TTS `.mp3` output |
| Coach evaluation | `coach.py` (existing, unchanged) | Called via `subprocess` at session end |
| Persistence | Obsidian vault (existing) | `Areas/English-Learning/sessions/` + `progress.md` |

---

## 3. New files

```
call-recorder/
  practice.py          ← NEW: conversation loop (STT → LLM → TTS)

app.py                 ← MODIFIED: new page "English Practice" added to sidebar
pages/
  english_practice.py  ← NEW: Streamlit page that launches and controls practice.py
```

No existing files are deleted or structurally changed.

---

## 4. Conversation loop (`practice.py`)

```
┌─────────────────────────────────────────────────────┐
│                  practice.py loop                   │
│                                                     │
│  1. Record mic chunk (sounddevice, 30s max)         │
│         ↓                                           │
│  2. Whisper transcribe (CPU, int8)     ~8-15s       │
│         ↓                                           │
│  3. Append to session transcript (timestamped .txt) │
│         ↓                                           │
│  4. Build prompt → Ollama generate     ~5-10s       │
│     (role: native English interlocutor,             │
│      topic injected at session start)               │
│         ↓                                           │
│  5. edge-tts → .mp3 → playback         ~2-3s        │
│         ↓                                           │
│  6. Loop until user ends session                    │
│         ↓                                           │
│  7. [END] subprocess → coach.py --transcript <file> │
│           --topic-type casual|meeting|...           │
└─────────────────────────────────────────────────────┘
```

**Per-turn latency estimate (CPU):**
- Whisper medium: ~8–15s for a 15–30s audio chunk
- Ollama qwen2.5-coder: ~5–10s for a short conversational reply
- edge-tts + playback: ~2–3s
- **Total per turn: ~15–28s** — conversational, not real-time

**Ollama conversation prompt context:** The session maintains a rolling window of the last N turns (configurable, default 6) to keep the conversation coherent without exceeding the model's context window.

---

## 5. Streamlit page (`pages/english_practice.py`)

Controls visible to the user:

- **Topic** — free text (e.g. "meeting with Stefan about Q3 roadmap")
- **Session type** — dropdown: `casual`, `meeting`, `technical`, `negotiation`, `interview` (maps directly to existing `coach.py` `--topic-type`)
- **Start / Stop session** — launches `practice.py` as a subprocess
- **Live transcript** — scrollable, auto-updated as turns come in
- **Post-session panel** — shows coach scores + errors after evaluation completes

---

## 6. Resource usage and concurrency considerations

### Ollama
- `practice.py` uses `http://localhost:11434/api/generate` (same endpoint as `coach.py`)
- Requests are **sequential within a session** — no parallel Ollama calls from this feature
- **Risk:** If a separate `coach.py` evaluation or the agent pipeline runs simultaneously, both will queue on Ollama. Ollama handles this natively (queues requests); no deadlock risk, but latency will increase
- **Mitigation:** `practice.py` checks Ollama availability before starting and warns the user if a long evaluation is in progress

### Whisper model
- Model is loaded once at session start and held in memory for the session duration (`~1.4 GB` RAM)
- `record.py` also loads the Whisper model when called — **they must not run simultaneously** (RAM constraint on CPU-only machine)
- `practice.py` will be a standalone process; it does not call `record.py` — it reimplements the capture+transcribe loop internally to keep the session state coherent
- Concurrent use of `english-coach.ps1` (which calls `record.py`) while a practice session is running would load Whisper twice (~2.8 GB). The Streamlit page will display a warning and recommend closing other recording sessions first

### sounddevice (microphone)
- Only one process can hold the default microphone input stream at a time on Windows
- `practice.py` acquires the mic for each recording chunk and releases it immediately after
- `record.py` holds the mic for the full session duration
- **Hard conflict:** running `english-coach.ps1` (which calls `record.py`) while a practice session is active will cause the second process to fail to open the mic. The Streamlit page checks for this and blocks start if another recording process is detected

### Streamlit
- The new page runs as part of the existing Streamlit process (port 8501)
- `practice.py` is launched as a **subprocess** (not a thread) to avoid blocking the Streamlit event loop
- Session state is communicated back to Streamlit via a shared temp file (transcript path + status flag)

### Port / process conflicts
| Process | Port/Resource | Notes |
|---|---|---|
| Streamlit app | 8501 (TCP) | Existing, unchanged |
| Ollama | 11434 (TCP) | Existing, shared |
| practice.py | No port | Subprocess, mic + disk only |
| coach.py (post-session) | No port | Subprocess, Ollama HTTP call |

No new ports are opened.

---

## 7. New dependency: `edge-tts`

```
pip install edge-tts
```

- Communicates with `speech.platform.bing.com` on first use per voice to fetch voice metadata; subsequent calls generate audio locally from cached data
- **No API key, no account, no cost**
- Recommended voice: `en-US-GuyNeural` (male) or `en-US-JennyNeural` (female) — both natural, B2-friendly pace
- Output: `.mp3` written to a temp file, played back and deleted

**Offline behavior:** edge-tts requires a network connection. If offline, `practice.py` will fall back to printing the response as text (no audio) and continue the session.

---

## 8. Vault output (no schema changes)

The feature reuses the existing coach output format exactly:

```
Areas/English-Learning/
  sessions/
    YYYY-MM-DD_HH-MM_english-coach.md   ← same format as today's sessions
  progress.md                            ← same append row format
  _index.md                              ← same Current Status update
```

No new vault directories or file schemas are introduced.

---

## 9. What is NOT changing

- `coach.py` — called as-is via subprocess, zero modifications
- `record.py` — not called by this feature; no modifications
- `english-coach.ps1` — not modified; remains the existing manual recording flow
- `app.py` sidebar — one new entry added: `English Practice`
- Vault schema — no changes
- Ollama model — same `qwen2.5-coder:latest`
- Whisper model — same medium int8 on disk

---

## 10. Open questions for senior review

1. **Whisper double-load risk** — Is it acceptable to warn the user rather than hard-block a second Whisper load? The machine's RAM headroom determines this.
2. **Ollama context window** — `qwen2.5-coder:latest` context window is ~32k tokens. Rolling 6-turn window should stay well within limits, but confirm for long sessions (30+ turns).
3. **Mic conflict detection** — On Windows, detecting whether another process holds the mic requires either trying to open it (and catching the error) or scanning running processes. Preference?
4. **Streamlit subprocess communication** — Using a shared temp file for status is simple but polling-based. Is a named pipe or queue preferred for cleaner IPC, given this is a personal toolkit?
5. **edge-tts offline fallback** — Should a silent fallback (text only) be acceptable, or should the session be blocked if no network is available for TTS?

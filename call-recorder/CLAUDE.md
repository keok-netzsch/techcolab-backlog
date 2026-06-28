# CLAUDE.md — call-recorder

## Project overview
PowerShell + Python tool that records speech, transcribes with Whisper (local, CPU, medium model), and evaluates English with Ollama (`qwen2.5-coder:latest`). No API keys — Ollama only.

**Part of:** https://github.com/keok-netzsch/techcolab-backlog (subfolder `call-recorder/`)
**Vault output root:** `%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO`

---

## File map

| File | Purpose |
|---|---|
| `call-recorder.ps1` | Unified flow: pick contact/session → record once → process → if English, also run coach. Menu order: [1] Stefan, [2] Alberto, team, divider, other stakeholders, divider, then session types (Project Meeting / Retrospective / Idea Capture / Outro). People/stakeholder lists read live from the vault. `--SEP--` renders as an unnumbered, non-selectable divider. |
| `english-coach.ps1` | Standalone English session: record → Whisper → Ollama eval (also reachable via category=any + language=English in `call-recorder.ps1`) |
| `record.py` | Mic capture + faster-whisper transcription (CPU, int8). Saves audio to `recordings/*.wav` (7-day retention). |
| `coach.py` | Ollama evaluation — reads transcript, writes to vault |
| `process.py` | Processes transcripts → vault notes. Subcommands: `transcript` (Team 1:1), `manager` (Stakeholder), `note` (Outro → `Inbox/<date>_<time>_nota-avulsa.md`), `capture --mode {project,retro,idea}` (idea-031 standalone sessions → `Inbox/<date>_<time>_{project-meeting,retrospective,idea-capture}.md`, status `a-triar`), `agenda`, `sweep`, `queue`. |
| `transcripts/` | Persisted transcript archive (named `YYYY-MM-DD_HH-MM_Person.txt`) |
| `recordings/` | Saved raw audio `.wav` (same base name as transcript). **Auto-purged after 7 days** (`RECORDINGS_RETENTION_DAYS` in `record.py`). `.gitignore`d. |

---

## English Coach flow

**Full flow (via PS1):**
```
english-coach.ps1 [-Topic "..."]
  → record.py --language en --output transcript_en_YYYY-MM-DD_HH-mm.txt
  → coach.py --transcript <file> [--topic "..."]
  → (temp transcript deleted after)
```

**Manual flow (when transcript already exists):**
```powershell
.\.venv\Scripts\python.exe coach.py --transcript path\to\file.txt --topic "optional"
```

**Transcript naming:**
- From `english-coach.ps1`: `transcript_en_YYYY-MM-DD_HH-mm.txt` in project root (temp, deleted after)
- From `record.py` standalone: `transcript_YYYY-MM-DD_HH-mm.txt` in project root
- Archived manually: `transcripts/YYYY-MM-DD_HH-MM_Person.txt`

**Output (vault):**
- Session note: `Areas/English-Learning/sessions/YYYY-MM-DD_HH-MM_english-coach.md`
- Progress log: `Areas/English-Learning/progress.md`

---

## No API key

- `coach.py` uses Ollama (`http://localhost:11434`) — no `ANTHROPIC_API_KEY`
- `english-coach.ps1` no longer checks for API key (fixed 2026-05-28)
- Ollama must be running: `ollama serve`
- Model required: `qwen2.5-coder:latest`

---

## Whisper model

- Stored locally: `%USERPROFILE%\techcolab-backlog\call-recorder\model` (NOT committed — `.gitignore`d, ~1.4 GB)
- Size: medium — download from HuggingFace (`Systran/faster-whisper-medium`) into `model/`
- Runs on CPU with int8 quantization
- Long recordings (30+ min) can take 10–20 min to transcribe on CPU

---

## Known issues / gotchas

| Issue | Fix |
|---|---|
| `english-coach.ps1` requires ANTHROPIC_API_KEY | Removed 2026-05-28 — uses Ollama only |
| `coach.py` COACH_DIR was pointing to `English-Coach/` | Fixed 2026-05-28 → now `Areas/English-Learning/` |
| `coach.py` evaluation timeout on CPU | Bumped to 1200s (2026-05-29). Warm model: ~14 min. Cold start (fresh `ollama serve`): +5 min. |
| `coach.py` UnicodeEncodeError on Windows terminal (cp1252 vs █░) | Fixed 2026-05-28 — `sys.stdout.reconfigure(encoding="utf-8")` in main() |
| `.venv` does not exist — `english-coach.ps1` falls back to system Python | Expected behavior — `python` in PATH resolves to Python 3.13 |
| `process.py` docstrings still reference `English-Coach/` | Not critical — not used at runtime |
| Save-Block in PS1 inserts in wrong place in 1on1.md | Fixed — rewritten with line-based frontmatter parsing (deterministic) |
| Transcription of long English calls takes time | Normal — Whisper medium on CPU: ~1/3x realtime |
| `.ps1` fails to parse (`Unexpected token`, `Missing closing`) when run from the launcher | The `.ps1` files run under **Windows PowerShell 5.1** which reads no-BOM files as ANSI. **Keep all `.ps1` code lines ASCII-only** — a stray `—` (em-dash) or smart-quote breaks quote balance and cascades parse errors. Use `-`, `...`, `"`. (Comments tolerate non-ASCII.) |

---

## Venv

Path: `%USERPROFILE%\techcolab-backlog\call-recorder\.venv`
Activate: `.\.venv\Scripts\Activate.ps1`
Key packages: `faster-whisper`, `sounddevice`, `soundfile`, `numpy`, `requests`

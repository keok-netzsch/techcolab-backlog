# CLAUDE.md — call-recorder

## Project overview
PowerShell + Python tool that records speech, transcribes with Whisper (local, CPU, medium model), and evaluates English with Ollama (`qwen2.5-coder:latest`). No API keys — Ollama only.

**Part of:** https://github.com/keok-netzsch/techcolab-backlog (subfolder `call-recorder/`)
**Vault output root:** `%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO`

---

## Call Recorder 2.0 (2026-08-26) — READ THIS FIRST

Two assumptions from 1.x are **dead**. Do not reason from them, and do not
"restore" them when touching this code:

| Dead assumption (1.x) | Reality from 2.0 on |
|---|---|
| A recording contains **only Kelvin's microphone** | Recordings are **2-channel**: ch0 = Kelvin (mic), ch1 = the other party (WASAPI loopback). Never mixed. |
| Speaker attribution has to be **guessed from text** (`process.py diarize`) | Attribution is **exact**, from the channel. `diarize` is legacy — only for old 1-channel files. |
| Recording **starts from a menu**, after choosing person/category/language | Recording starts and stops **by itself** when Teams takes and releases the mic. Classification happens *after*. |

**Why it changed.** The mic-only design silently lost the other half of every
call: on a headset the other party never reaches the mic at all. Measured on the
2026-08-26 1:1s, the share of audio that was pure gap — the other person talking,
unrecorded — was 44% (Pedro Hennig), 52% (Ana Leite), 53% (Pedro Klein), 18%
(Lucas Shizuno). The recordings were, in practice, a log of Kelvin talking to
himself.

**What this means for anything that consumes a transcript:** a 2-channel file
transcribes to `[012.4s] Kelvin: ...` / `[021.7s] Interlocutor: ...`. Parsers that
assume the old bare `[012.4s] texto` format must handle both — 1-channel files
from before this date still exist and still produce the old shape.

### Routing happens after transcription (2026-08-28)

A third 1.x assumption is dead: **that a recording has one destination, decidable
from its title.**

```
grava → classify (transcrever?) → transcreve (batch 20:00) → .job.json.routing
      → route.py: le o conteudo, N destinos por assunto → vault
```

The Teams window title carries the *scheduled* subject and never the participants,
and it was being read hours before anyone could see the transcript. Worse, a call
covers several subjects at once — a Daily BIZ with ten minutes of Daniel's OKR and
the rest on delivery has two destinations, and the old `kind`/`target` pair could
only hold one.

So `cmd_queue` now **parks** autocapture jobs after transcribing (`.job.json.routing`)
instead of filing them, and `route.py` files them against the content. A manually
started recording still routes straight through: whoever hit record already knew
where it belonged.

Consequence for the 16:00 `triagem-gravacoes` routine: at 16:00 there is nothing
transcribed to read. Review belongs in the morning, after the 20:00 batch.

### Regras de roteamento (decisoes do Kelvin)

- **Daily BIZ / Daily PM = territorio do Team Memory Agent** (29/08/2026). O TMA
  ja captura o resumo docx dessas series e consolida no vault central; rotear o
  audio inteiro duplicaria o mesmo fato com versoes divergentes. No roteamento:
  ficar SO com o que e pessoal do Kelvin (decisao dele, 1:1 embutido, item de
  stakeholder) e `--descartar` o resto. A regra vive em `ROUTING_RULES` no
  `route.py` e aparece na propria listagem (humana e `--json`, campo `rule`) -
  a sessao que roteia a ve sem depender deste arquivo.

### Consent

Recording now captures the other person's voice, not just Kelvin's. He chose to
keep autocapture on by default and to disclose it himself, case by case
(decision of 2026-08-26). Do not add prompts, banners, or nags on his behalf —
and do not quietly disable capture either. The controls that exist are enough:
`autocapture.paused` and `CAPTURE_SYSTEM_AUDIO=0`.

---

## File map

| File | Purpose |
|---|---|
| `call-recorder.ps1` | Unified flow: pick contact/session → record once → process → if English, also run coach. Menu order: [1] Stefan, [2] Alberto, team, divider, other stakeholders, divider, then session types (Project Meeting / Retrospective / Idea Capture / Outro). People/stakeholder lists read live from the vault. `--SEP--` renders as an unnumbered, non-selectable divider. The "Quando processar?" step has 3 options: [1] enqueue (17h), [2] record now, [3] **File Processing (idea-031)** — transcribe an existing audio/video file (`record.py --input`) instead of the mic, then the same post-processing (`.lang` → `process.py` → coach if English). |
| `english-coach.ps1` | Standalone English session: record → Whisper → Ollama eval (also reachable via category=any + language=English in `call-recorder.ps1`) |
| `autocapture.py` | **2.0.** Background watcher: polls `LastUsedTimeStop` under `HKCU\...\ConsentStore\microphone\MSTeams_8wekyb3d8bbwe` every 3 s — the value is `0` exactly while Teams holds the mic. Transition idle→held starts a dual-channel capture; held→idle (2 consecutive reads, so mute/unmute does not split a call) stops it. Writes `recordings/<date>_<time>_auto.wav` plus a **`.pending.json`** sidecar — deliberately *not* a `.job.json`, so capture never waits on a classification decision. Drops anything under `MIN_SECONDS` (120). Best-effort meeting name from the Teams window title. Pause with the file `autocapture.paused`; nothing is recorded while it exists. Runs under `pythonw`, where `sys.stdout` is `None` — `log()` writes the file first and only prints if a console exists, because an unguarded `print` kills the watcher on its first call. Log: `autocapture.log`. |
| `record.py` spool (2.0.1, 2026-08-27) | Durante a captura cada canal flui para disco a cada 200ms (`recordings/_spool_ch{0,1}.<pid>.wav`), nao so para RAM: crash/logoff/reboot no meio da call preserva o audio ate ali, e a RAM fica constante (antes, call de 2h seguraria ~460 MB). `autocapture` resgata spools FRIOS (mtime > 30s; captura viva toca o spool a cada 200ms — frescor e o sinal de vida, imune a reuso de PID) no startup e os transforma em `*_auto-recovered.wav` + `.pending.json`. Spools sao limpos apos o wav final ser escrito, ou apos descarte deliberado (<120s). PID no nome evita que record.py manual e o watcher truncem a captura um do outro. |
| `install-autocapture.ps1` | Registers/removes the `CallRecorder-AutoCapture` scheduled task (at logon, no window, no execution time limit). `-Remove` uninstalls. |
| `classify.py` | Turns a `.pending.json` into a `.job.json` so `process.py queue` transcribes it. Consults `meeting-aliases.json` first (recurring meeting → fixed destination), then name matching. Sets `route_after_transcript: True` on everything it emits — see `route.py`. What it decides is *whether to transcribe*, no longer *where to file*. |
| `route.py` | **Routing by subject (2026-08-28).** Lists jobs that are transcribed and parked (`.job.json.routing`), and files each one into **N destinations**, each receiving only its own slice of the transcript. `--para kind[:alvo] --assunto "..."` (repeatable), `--texto` to read the transcript, `--descartar` when the call is not worth filing. Slices are saved next to the transcript, so the exact text behind any note stays on disk. ADR: `vault/decisions/2026-08-28-roteamento-por-assunto.md`. |
| `record.py` | Capture + faster-whisper transcription (CPU, int8). Saves audio to `recordings/*.wav` (7-day retention). **2.0:** `capture_dual()` records mic (`sounddevice`, the proven path — the WASAPI route to this mic returns digital silence) and system loopback (`soundcard`, WASAPI) on two threads, returning separate channels; falls back to mic-only and says so when `soundcard` or a loopback endpoint is missing. Disable with `CAPTURE_SYSTEM_AUDIO=0`. `transcribe()` detects a 2-channel file and routes to `_transcribe_dual()`, which transcribes each channel and interleaves by timestamp, labelling with `SPEAKER_LABELS`. A channel that is silent is skipped with a warning. **File Processing (idea-031):** `--input <file>` transcribes an existing audio/video file (mp4/mov/mkv/wav/m4a/…) instead of the mic — faster-whisper decodes the container via ffmpeg/PyAV, so a video's audio track is transcribed directly. Writes the same `.txt` + `.lang` sidecar. `--language auto` lets Whisper detect. Runs without PortAudio (mic imports are skipped in `--input` mode). |
| `coach.py` | Ollama evaluation — reads transcript, writes to vault |
| `process.py` | Processes transcripts → vault notes. Subcommands: `transcript` (Team 1:1), `manager` (Stakeholder), `note` (Outro → `Inbox/<date>_<time>_nota-avulsa.md`), `capture --mode {project,retro,idea,requirements,learning}` (idea-031 standalone sessions → `Inbox/<date>_<time>_{project-meeting,retrospective,idea-capture,requirements,learning-capture}.md`, status `a-triar`), `agenda`, `sweep`, `queue`, `dashboard` (idea-031 → consolida todos os `- [ ]` com dono/prazo do vault em `Action-Dashboard.md`, agrupado por status de prazo; gitignored), `diarize` (**LEGADO desde 2.0** — só para `.wav` de 1 canal gravados antes de 2026-08-26; arquivo de 2 canais já vem com falante exato, não passe por aqui. idea-031 → **speaker labeling por TEXTO**, interino: `--transcript <file> [--people "Kelvin Okuda,Ana Leite"] [--output]` pede ao Ollama para atribuir falantes pelo contexto e grava `<nome>.diarized.txt`. Aproximado — sem sinal de voz, não distingue falantes com confiança; passo separado pois é um 2º passe de LLM), `diarize`... , `memory` (idea-031 → **Cross-Session Memory**, determinístico/sem LLM: `--person <folder>` gera `Team/<folder>/memory.md` com ações ainda abertas acumuladas entre sessões + tópicos recorrentes (>=2 sessões); sem `--person` gera todos + `Cross-Session-Memory.md` na raiz com tópicos compartilhados entre pessoas), `velocity` (idea-031 → **Action Velocity**, determinístico/sem LLM: rastreia cada action item de `[ ]`→`[x]` pelas sessões datadas do `1on1.md`, mede tempo-de-fechamento (avg/median), sinaliza abertas `stale` (>30d). `--person` → `Team/<folder>/velocity.md`; sem `--person` → todos + rollup `Action-Velocity.md`), `alerts` (idea-031 → **PDI/OKR Alerts**, determinístico/sem LLM: varre `OKR.md`+`PDI.md` por prazos vencidos (`YYYY-MM-DD` e `DD/MM/YYYY`), marcadores `OVERDUE`/`ALERTA` e progresso zero, ignorando seções Completed/Concluídos e itens ✅/`[x]`; dedup dos blocos repetidos. `--person` → `Team/<folder>/alerts.md`; sem `--person` → todos + `PDI-OKR-Alerts.md`), `health` (idea-031 → **Team Health Metrics**, determinístico/sem LLM: consolida recência do último 1:1 + carga de ações abertas/stale + alertas PDI/OKR num score 0-100 por pessoa (sinal, não veredito). `--person` → `Team/<folder>/health.md`; sem `--person` → todos + `Team-Health.md` (tabela worst-first)). |
| `capture_multi.py` | **Captura redundante (2026-08-28).** Grava TODAS as entradas presentes e TODOS os endpoints de saida ao mesmo tempo, e escolhe no fim pela ATIVIDADE DE FALA — nao pelo nivel. Existe porque toda falha medida veio de escolher um dispositivo no inicio e estar errado na hora da call. Nao deduplica por nome: o mesmo microfone entregou 79% de fala no WASAPI e 0% no DirectSound, e a dedup ficava com o errado. Abre na taxa NATIVA do dispositivo (WASAPI recusa 16 kHz e some da captura em silencio). WDM-KS fica de fora de proposito — abre em modo exclusivo e poderia roubar o mic do Teams. Custo ~12 MB/hora, apagado apos a escolha. |
| `which_mic.py` | Diagnostico: grava TODAS as entradas por N segundos enquanto o Kelvin fala e diz qual ouviu a voz dele. Dirigido por VOZ HUMANA de proposito — um teste com tom sintetico declarou o microfone bom quando o que a entrada captava era crosstalk eletrico do proprio jack, e as tres calls seguintes gravaram zumbido. Reporta tambem as entradas que NAO ABRIRAM, com o codigo do PortAudio: engolir esse erro faz "nem abriu" parecer "gravou e nao ouviu nada". Salva em `which_mic_result.txt`. |
| `transcript_quality.py` | **Gate de qualidade por TRECHO (2026-08-28).** Complementa `audit_transcripts.py`, nao substitui: aquele julga o arquivo inteiro por palavras-por-minuto e pega "tudo degenerado"; este pega "estes 15 minutos degeneraram". Sinal principal e ESTRUTURAL — o Whisper decodifica em janelas de 30 s e, em janela sem fala, emite algo que cai em 0.0/30.0/60.0; tres seguidas e conclusivo, em qualquer idioma. Reporta POR FALANTE, porque a falha do OKR 05 era de um canal so. Advisory: nunca bloqueia. `--todos` audita tudo, `--limpar` grava versao limpa. |
| `triage.py` | O Kelvin classifica o que a maquina nao soube. Gravacao marcada `needs_review` espera aqui em vez de ser arquivada sob palpite. `--lembrar` grava o titulo em `meeting-aliases.json`, entao reuniao recorrente se classifica sozinha da segunda vez — a decisao humana e tomada uma vez, nao toda semana. `--json` para consumo por script (o lembrete grafico lia o texto formatado com regex e passou a achar ZERO pendentes quando o formato mudou por um espaco). |
| `process.py queue` (trava) | A fila e **single-flight**: `recordings/.queue.lock` com o PID. Segunda fila sai sem tocar em nada, e os jobs continuam intactos para o proximo lote. Existe desde 2026-08-29, quando a fila ganhou tarefa propria as 20:00 (`CallRecorder-Queue`) — um lote manual iniciado de dia ainda pode estar rodando na hora do gatilho, e as duas leem a MESMA lista de `.job.json`: a nota iria ao vault duas vezes e dois Whisper disputariam a mesma CPU. Trava de processo morto e tratada como orfa e removida (reboot no meio do lote nao pode impedir o lote seguinte). |
| `process_one.py` | Processa UM job pelo nome. `cmd_queue` e tudo-ou-nada, o que e certo para o lote noturno e errado quando se quer uma call especifica agora: 45 min de audio sao ~1,5 h de Whisper nesta maquina, e transcrever dez gravacoes para chegar em uma nao e opcao durante o expediente. |
| `verify_capture.py` | Veredito sobre a captura em 2 canais da gravacao mais recente: o canal do interlocutor tem fala de verdade, ou o arquivo tem so o Kelvin? Ferramenta manual — nada a chama automaticamente. |
| `audit_transcripts.py` | Varre `transcripts/` procurando transcricao degenerada no arquivo inteiro (o caso de 2026-08-26: 43 min que viraram 98% de "."). Ver `transcript_quality.py` para o caso complementar, de trecho. |
| `transcripts/` | Persisted transcript archive (named `YYYY-MM-DD_HH-MM_Person.txt`) — output of the normal `call-recorder.ps1` flow (person/manager/note/capture), always routed through `process.py` into the vault. **This is where 1:1s, manager calls, and captures actually live — check here first.** |
| `recordings/` | Saved raw audio `.wav` (same base name as transcript). **Auto-purged after 7 days** (`RECORDINGS_RETENTION_DAYS` in `record.py`). `.gitignore`d. |
| Project root (`.`) | **Separate, ad-hoc category — do not confuse with `transcripts/`.** `record.py` run standalone (not via `call-recorder.ps1`'s menu) writes `transcript_<stem>_<timestamp>.txt` directly here (`record.py`'s default `out_path`), e.g. `transcript_reuniao_diretoria_*.txt` — Kelvin's own recurring leadership-meeting recordings, unrelated to any team member's 1:1/manager session. These are **not** auto-routed through `process.py` and never land in the vault unless processed manually. If searching for a specific person's session and the filename pattern doesn't match `YYYY-MM-DD_HH-MM_Person.txt`, it's in `transcripts/`, not here — don't assume a same-day root-level file is that person's session.|

---

### Tarefas agendadas (revisto 2026-08-29)

| Tarefa | Hora | Faz |
|---|---|---|
| `CallRecorder-AutoCapture` | logon | Grava sozinha quando o Teams pega o mic |
| `TechColab Backlog Agent` | 07:00 | Relatorio de backlog (`run_agent.bat`) |
| `CallRecorder-Queue` | 20:00 | So a fila (`scripts/run-queue.ps1` -> `process.py queue`) |
| lembrete de roteamento | 09:00 | `scripts/triage-reminder.ps1` (janela) + rotina `triagem-gravacoes` do Claude |
| ~~`TechColab Daily Agent`~~ | ~~20:00~~ | **DESABILITADA.** Era a segunda tarefa no mesmo `run_agent.bat` |

A fila saiu do agente de backlog porque as duas cargas estavam amarradas no mesmo
`.bat`: a analise de ideias consumia o limite de 6h e a transcricao nunca era
alcancada. Em 29/08 havia 10 gravacoes paradas em `.wav`, ~4h de audio, sem que
nada indicasse falha. Reinstalar/desinstalar: `scripts/install-queue-task.ps1`.

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

## LLM providers (changed 2026-08-26)

All LLM calls go through `coach_llm.py`, which routes **by purpose**:

| Purpose | Provider | Why |
|---|---|---|
| `coach`, `coach-probe` | **NETZSCH LiteLLM gateway** when `NETZSCH_LLM_API_KEY` is set, else Ollama | Kelvin's own speech in project calls. A 7B *code* model judging English produced invented grammar rules and graded one identical transcript B2 four times and C1 once |
| everything else (`transcript`, `manager`, `note`, `capture`, agendas) | **Ollama, always** | 1:1s, PDI, OKR — HR content that never leaves the machine |

Remote is the **company gateway** (`litellm.chatbot.netzsch.com`), not a personal
Anthropic account — Kelvin has no direct Anthropic key. Traffic therefore stays inside
NETZSCH's contracted boundary, which is what `vault/decisions/2026-08-13-ai-local-vs-api-assessment.md`
required before any non-local processing. The gateway is OpenAI-compatible
(`/v1/chat/completions`) and fronts 19 models, including `claude-opus-5`,
`claude-sonnet-5`, `claude-haiku-4-5`, GPT-5.x and Gemini.

`REMOTE_ALLOWED` in `coach_llm.py` is the allowlist; a purpose outside it cannot reach
the gateway even if the env says otherwise. Adding to it must be deliberate.

If the gateway fails — no credit, expired key, rate limit, network — the call **falls
back to Ollama** instead of aborting, logs the distinguishable reason, and sets
`last_run_degraded()` so the session can be stamped as lower quality. A scheduled run
must never die because of billing.

### Model choice — decided 2026-08-26, with numbers

`claude-sonnet-5` is the default. **This was measured, do not change it casually.**

Both models were run through the production prompt on two real transcripts:

| | 2026-06-30 (946 w) | 2026-07-08 (4016 w) |
|---|---|---|
| `claude-sonnet-5` | ok | **42 s**, C1/7, quotes 3/3 grounded |
| `claude-opus-5` | 204 s after 2x HTTP 504 | **1466 s, 3x 504, then failed** |

Opus is genuinely better where it matters — it reaches pragmatic calibration that
Sonnet does not (`"do you think it's necessary for us to record the call?"` ->
`"are you okay if I record the call?"`), and grounded 6/6 errors and 6/6
refinements. But through this gateway it times out on long transcripts. On the
second session it exhausted its retries and fell through to Ollama, which then
produced an **ungrammatical** "correction" (`"they don't have a top player for
years"` -> `"There haven't been a top player for years"`).

For a weekly scheduled job, a model that takes 24 minutes and then degrades is
worse than a good one that answers in 42 seconds. Revisit if gateway latency for
Opus improves.

```powershell
# NETZSCH_LLM_API_KEY is already a user env var on this machine
setx COACH_MODEL "claude-opus-5"   # opt-in for one deep pass on a SHORT transcript
setx COACH_MODEL "claude-sonnet-5" # back to the default
setx COACH_LLM   "ollama"          # forces the coach local again
```

Never hardcode a key — this repo is PUBLIC. `python coach_llm.py` prints the active
routing and self-tests without revealing the key.

- Ollama must be running for the local path: `ollama serve`
- Local model: `qwen2.5-coder:latest`

## Guard modules (added 2026-08-26)

| File | Purpose |
|---|---|
| `coach_guards.py` | Input/output integrity: text-based language gate (Whisper's own `.lang` said `en` for Portuguese calls), artifact filter by repetition coverage, quote-grounding for **errors and strengths**, prompt-echo guard, backchannel allowlist, CEFR one-step clamp + rolling window. `python coach_guards.py` self-tests |
| `coach_patterns.py` | Personal error inventory: deterministic PT-L1 interference rules (certain) + narrow yes/no probes for false friends (`actually`, `realize`, `support`, `until`). Reframes the task from open-ended grading to grounded detection. `python coach_patterns.py` self-tests |

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

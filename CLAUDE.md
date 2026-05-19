# CLAUDE.md — TechColab Backlog

Operating instructions for Claude Code when working in this project.

---

## Project context

**TechColab Backlog** is a local idea management app built with Streamlit, integrated
with an Obsidian vault and optionally with a local LLM (Ollama). It runs entirely
offline — no external API keys required.

- **Main app:** `app.py` (Streamlit)
- **Vault path:** read from env var `TECHCOLAB_VAULT` (fallback in `config.py`)
- **Backlog items:** `{VAULT_ROOT}/Backlog - to do - app/backlog items/idea-NNN.md`
- **Agent reports:** `{VAULT_ROOT}/Backlog - to do - app/agent-reports/`
- **Tests:** `tests/` — run with `python -m pytest tests/ -v`
- **Repository:** https://github.com/keok-netzsch/techcolab-backlog

---

## Mandatory checklist after ANY change

After completing any task that modifies code, documentation, or configuration,
you MUST complete all applicable items below before reporting the task as done.

### 1. Push to GitHub

```bash
git add -A
git commit -m "<type>: <short description>"
git push
```

Commit types: `feat` (new feature), `fix` (bug fix), `docs` (documentation only),
`refactor` (code change without feature/fix), `test` (tests), `chore` (tooling/config).

### 2. Update the desktop shortcut

If `start_app.bat`, `start_silent.vbs`, or `install.bat` were modified, recreate
the shortcut on the real desktop (OneDrive path):

```powershell
$desktop = [System.Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("$desktop\TechColab Backlog.lnk")
$s.TargetPath = "wscript.exe"
$s.Arguments = '"C:\Users\Kelvin.okuda\techcolab-backlog\start_silent.vbs"'
$s.WorkingDirectory = "C:\Users\Kelvin.okuda\techcolab-backlog"
$s.Description = "Iniciar TechColab Backlog"
$s.IconLocation = "shell32.dll,13"
$s.Save()
```

Key points:
- Desktop is at `[System.Environment]::GetFolderPath("Desktop")` — NOT `%USERPROFILE%\Desktop`
  (on this machine it resolves to the OneDrive-synced desktop)
- Shortcut must point to `wscript.exe` + `start_silent.vbs` (hides terminal window)
- `start_app.bat` must activate `.venv` and set `TECHCOLAB_VAULT` as fallback

### 3. Update Tutorial and Documentation

If any of the following changed, update the Tutorial (`📖 Tutorial` page in `app.py`)
and/or the Documentation (`📚 Documentation` page) accordingly:

| Changed | Update |
|---|---|
| Installation steps | Tutorial → Installation section |
| `config.py` settings or env vars | Tutorial → Configuration section |
| Agent flow or report format | Tutorial → Daily agent section |
| New feature added to the app | Tutorial → Using the app table |
| Planned phases changed | Documentation → Planned next phases |
| Architecture changed | Documentation → System architecture |

After updating the app pages, also check if `README.md` needs updating.

---

## Environment

- **Python:** 3.13 (system) — no venv needed for running Claude Code tools
- **Streamlit:** runs inside `.venv` via `start_app.bat`
- **Vault env var:** `TECHCOLAB_VAULT` — set as a permanent user env var on this machine
- **Agent schedule:** Windows Task Scheduler, daily at 08:00, runs `run_agent.bat`
- **Tests:** 40 tests in `tests/`, all must pass before committing

## Agent Phase 2 — Executing approved actions

When the user opens a Claude Code session via `execute_agent.bat` and says
"Execute the approved items from today's agent report", follow this protocol:

1. **Find today's report** — read `{VAULT_ROOT}/Backlog - to do - app/agent-reports/report-YYYY-MM-DD.md`
2. **List approved items** — show the user all checked boxes (`- [x]`) and confirm before acting
3. **Update status — start of work:**
   ```
   python agent/update_status.py <idea_id> "em desenvolvimento"
   ```
4. **Execute the item** — implement, fix, or run whatever the to-do describes
5. **Run tests:** `python -m pytest tests/ -v`
6. **Update status — end of work:**
   - If implementation is complete and needs user review: `python agent/update_status.py <idea_id> "em validação"`
   - If done and verified: `python agent/update_status.py <idea_id> "concluído"`
7. **Commit and push** (mandatory checklist step 1)

> The `update_status.py` script only changes the `status` field in the vault markdown file.
> It does not touch `updated_at` (the store sets it automatically on save).

---

## What NOT to do

- Do not use `ANTHROPIC_API_KEY` — this project uses Ollama (local LLM) only
- Do not hardcode the vault path — always read from `TECHCOLAB_VAULT` env var or `config.py`
- Do not use `%USERPROFILE%\Desktop` for shortcuts — use `GetFolderPath("Desktop")`
- Do not commit `__pycache__/`, `.venv/`, or `.pyc` files — they are in `.gitignore`

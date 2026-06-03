# SECURITY — data isolation

> **This is a PUBLIC repository.** Treat everything here as world-readable.

## Golden rule

**Vault data and project code are SEPARATE and must never mix.**

The Obsidian vault `TechColab_D&A_KO` (team profiles, stakeholders, PDIs, OKRs,
performance assessments, compensation, retention notes) is a **separate, local-only
git repo** synced via OneDrive. It has **no remote and must never get one.**
This project repo (`techcolab-backlog`) only contains **code** and runs *against*
the vault through the `TECHCOLAB_VAULT` environment variable — it never stores
vault content.

## What must NEVER be committed here

- Anything under the vault (`Team/`, `Stakeholders/`, `Performance/`, `1on1/`, `PDI.md`, `OKR.md`, `Overview.md`, `backlog items/`, `agent-reports/`, daily `Log/`)
- Frontmatter/content with HR markers (`compensation-band`, `promotion-status`, flight/retention risk, `hard-skills-score`)
- Secrets / API keys / `.env` / `secrets.toml`
- Personal content (`linkedin/`, generated `reports/`, `logs/`, call-recorder transcripts)

These are covered by `.gitignore` and enforced by a pre-commit hook.

## Enable the protection (one-time, per clone)

```bash
git config core.hooksPath .githooks
```

This activates `.githooks/pre-commit`, which blocks any commit that stages vault
paths or HR content. To intentionally bypass (NOT recommended): `git commit --no-verify`.

> CI/automation note: if a `quick-push` / `close-session` script runs `git add -A`,
> the hook + `.gitignore` are the safety net. Keep them in place.

## For team members cloning this repo

1. Run `git config core.hooksPath .githooks` right after cloning.
2. Set `TECHCOLAB_VAULT` to *your own* vault path — never point it inside this repo.
3. Never copy vault files into the repo working tree.

## Vault path hygiene

The vault path comes from `TECHCOLAB_VAULT` (fallback in `config.py`). Avoid hardcoding
personal absolute paths (`C:\Users\<you>\OneDrive\...`) in committed files — some docs
still contain them (cleanup tracked separately); prefer the env var / placeholders.

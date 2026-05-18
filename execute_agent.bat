@echo off
:: TechColab Backlog — Phase 2: Execute approved actions from today's report.
:: Run this after reviewing and checking items in the agent report on Obsidian.
:: Opens a Claude Code session pre-loaded with the agent execution context.

cd /d "%~dp0"
claude --system-prompt-file agent\AGENT_PROMPT.md

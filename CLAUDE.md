# CLAUDE.md

Guidance for Claude Code sessions opened in this folder.

## What this is

Iroas: a personal-trainer bot. A Telegram bot (`bot.py`) that answers via the
Claude Agent SDK (`agent.py`) using the owner's **Claude subscription** (token in
`.env` as `CLAUDE_CODE_OAUTH_TOKEN`, created by `claude setup-token`). **Never
configure or suggest an `ANTHROPIC_API_KEY`** — subscription auth only.

- `persona/IROAS.md` — the agent's instructions (placeholders `{PYTHON}` and
  `{ROOT}` are filled in by `agent.build_system_prompt`)
- `skills/personal-trainer/` — training knowledge base the agent reads
- `hevy.py` — Hevy API client + CLI the agent runs via Bash
- `settings.py` — `settings.json` feature switches + CLI
- `scheduler.py` — pure logic for the evening check-in
- `doctor.py` — health check; `setup.ps1` — installer (ASCII only: PowerShell 5.1)
- `data/` — the owner's personal files (profile, routine, log, measurements).
  **Never delete or overwrite these**; they're the agent's memory and are not in git.

Run tests: `.venv\Scripts\python -m pytest -q`

## Auto-start at logon (the owner may ask for this)

If asked to make Iroas start automatically:

1. Make sure it's not already running twice: `start_iroas.bat` and a logon task
   must not both run. The bot holds localhost port 47391 as a single-instance
   lock and exits with code 3 if another copy is running.
2. Create a Task Scheduler task (PowerShell `Register-ScheduledTask`, current
   user, no admin needed):
   - Action: `<this folder>\.venv\Scripts\pythonw.exe` with argument `bot.py`,
     **working directory = this folder** (required — paths and `.env` are relative)
   - Trigger: at logon of the current user
   - Settings: run only when user is logged on; restart on failure every 1 minute
     up to 3 times; no execution time limit (`-ExecutionTimeLimit ([TimeSpan]::Zero)`);
     allow start on batteries and don't stop when going on batteries
3. Start it (`Start-ScheduledTask`), wait ~20 seconds, and confirm
   `logs\iroas.log` shows "Iroas is running". Tell the owner they no longer need
   `start_iroas.bat`, and how to stop it (Task Scheduler → Iroas → End /
   Disable, or `Stop-ScheduledTask -TaskName Iroas`).
4. Suggest setting Windows sleep to "Never" while plugged in, or at least later
   than the evening check-in time, so the check-in isn't missed.

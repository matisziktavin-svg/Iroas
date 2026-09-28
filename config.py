"""Paths and environment for Iroas. Everything is relative to this folder, so
the whole project can live anywhere (Documents, Desktop, ...)."""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # tests / bare runs without deps installed
    load_dotenv = None

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
if load_dotenv is not None:
    load_dotenv(ENV_PATH)

DATA_DIR = ROOT / "data"          # the owner's personal files (gitignored)
TEMPLATES_DIR = ROOT / "templates"  # blank starting copies of the data files
LOG_DIR = ROOT / "logs"
PERSONA_PATH = ROOT / "persona" / "IROAS.md"
SKILL_DIR = ROOT / "skills" / "personal-trainer"
SETTINGS_PATH = ROOT / "settings.json"
STATE_PATH = ROOT / "state.json"   # scheduler bookkeeping + chat session id

# The Python running the bot (the .venv one). The agent uses it to run hevy.py
# and settings.py, so the commands work no matter what's on PATH.
PYTHON = sys.executable

DATA_FILES = ("profile.md", "routine.md", "log.md", "measurements.md", "hevy_reference.md")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PAIRING_CODE = os.environ.get("PAIRING_CODE", "")
# Optional model override; blank = Claude Code's default for the subscription.
MODEL = os.environ.get("IROAS_MODEL") or None

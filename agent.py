"""Runs Iroas: builds the system prompt from the persona + the data files, then asks
Claude (via the Claude Agent SDK, on the owner's Claude *subscription*) for a reply.

Memory model: one Claude session per calendar day (resumed across messages for
chat continuity). Long-term memory is only the markdown files in data/, which
are re-read into the prompt on every turn — so nothing is lost when the day's
session rolls over.
"""
import asyncio
import datetime as dt
import logging
import os
import time

import config

# Subscription auth only: if an API key were in the environment the Claude
# CLI would bill the pay-per-use API instead of the Claude plan. Never allow it.
os.environ.pop("ANTHROPIC_API_KEY", None)

import windows_subprocess  # noqa: E402

windows_subprocess.patch_for_no_window()

from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None

import hevy  # noqa: E402
import scheduler  # noqa: E402
import settings as settings_mod  # noqa: E402

logger = logging.getLogger(__name__)

TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
_LOG_TAIL_LINES = 60
_FILE_CAP_CHARS = 12_000
_HEVY_CACHE_S = 300

_lock = asyncio.Lock()  # one Claude turn at a time (chat + scheduler share it)
_hevy_cache: tuple[float, str] = (0.0, "")


class ClaudeUnavailable(RuntimeError):
    """Claude couldn't answer for a reason he can act on (login, usage limit...).
    `user_message` is safe to send to Telegram as-is."""

    def __init__(self, detail: str, user_message: str):
        super().__init__(detail)
        self.user_message = user_message


class AuthError(ClaudeUnavailable):
    """Claude rejected the login — the subscription token needs refreshing."""

    def __init__(self, detail: str):
        super().__init__(detail, (
            "I can't reach Claude — my login token has expired or is wrong. On the PC, "
            "open the Iroas folder and double-click refresh_claude_login.bat. "
            "Once it says the token is saved, message me again."))


def _unavailable(kind: str, detail: str) -> ClaudeUnavailable:
    """Map the SDK's AssistantMessage.error kinds to a plain-English message."""
    if kind == "authentication_failed" or _looks_like_auth_error(detail):
        return AuthError(detail)
    if kind == "rate_limit":
        return ClaudeUnavailable(detail, "I've hit the Claude usage limit for your plan. "
                                 "It resets after a few hours — message me again later.")
    if kind == "billing_error":
        return ClaudeUnavailable(detail, "Claude says there's a billing problem with the "
                                 "subscription. Check your plan at claude.ai, then try again.")
    return ClaudeUnavailable(detail, "Claude is having trouble right now. Give it a few "
                             "minutes and try again.")


def ensure_data_files() -> None:
    """Copy blank templates into data/ for any file that doesn't exist yet."""
    config.DATA_DIR.mkdir(exist_ok=True)
    (config.ROOT / "tmp").mkdir(exist_ok=True)
    for name in config.DATA_FILES:
        dest = config.DATA_DIR / name
        src = config.TEMPLATES_DIR / name
        if not dest.exists() and src.exists():
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _read(name: str) -> str:
    try:
        return (config.DATA_DIR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _capped(text: str) -> str:
    if len(text) <= _FILE_CAP_CHARS:
        return text
    return text[:_FILE_CAP_CHARS] + "\n...(truncated — Read the file for the rest)"


def _log_view(text: str) -> str:
    """Header + newest entries of log.md (newest-first file, so the top)."""
    lines = text.splitlines()
    if len(lines) <= _LOG_TAIL_LINES:
        return text
    return "\n".join(lines[:_LOG_TAIL_LINES]) + "\n...(older entries omitted — Read log.md for full history)"


def _hevy_block() -> str:
    global _hevy_cache
    stamp, block = _hevy_cache
    if time.time() - stamp < _HEVY_CACHE_S and block:
        return block
    block = hevy.recent_workouts_block(limit=5) or "(HEVY_API_KEY not set.)"
    _hevy_cache = (time.time(), block)
    return block


def invalidate_hevy_cache() -> None:
    global _hevy_cache
    _hevy_cache = (0.0, "")


def build_system_prompt(now: dt.datetime | None = None, *, include_hevy: bool = True) -> str:
    now = now or dt.datetime.now()
    s = settings_mod.load()
    persona = config.PERSONA_PATH.read_text(encoding="utf-8")
    persona = (persona.replace("{PYTHON}", config.PYTHON.replace("\\", "/"))
                      .replace("{ROOT}", str(config.ROOT).replace("\\", "/")))

    status = "COMPLETE" if s.get("onboarded") else "NOT DONE — run onboarding now (see Onboarding)"
    sections = [
        persona,
        "\n# Right now",
        f"- Date/time: {now:%A, %B %d, %Y, %I:%M %p} (local time)",
        f"- Who you're talking to: {s.get('owner_name') or '(name not known yet — ask)'}",
        f"- Onboarding: {status}",
        "- Settings (settings.json):",
        settings_mod.describe(s),
    ]
    for name in ("profile.md", "routine.md", "measurements.md", "hevy_reference.md"):
        sections += [f"\n# data/{name}", _capped(_read(name)) or "(empty)"]
    sections += ["\n# data/log.md (newest entries)", _log_view(_read("log.md")) or "(empty)"]
    if include_hevy:
        sections += ["\n# Recent Hevy workouts (live; summary only — use `recent --detail` for sets)",
                     _hevy_block()]
    return "\n".join(sections)


def _session_for_today(state: dict, today: str) -> str | None:
    return state.get("session_id") if state.get("session_date") == today else None


def _looks_like_auth_error(text: str) -> bool:
    low = (text or "").lower()
    return ("401" in low and "auth" in low) or "invalid api key" in low or \
        "oauth token" in low or "please run /login" in low or "not logged in" in low


def _claude_env() -> dict[str, str]:
    """Re-read the token from .env every turn, so refresh_claude_login.bat
    takes effect without restarting the bot."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if dotenv_values is not None and config.ENV_PATH.exists():
        token = dotenv_values(config.ENV_PATH).get("CLAUDE_CODE_OAUTH_TOKEN") or token
    return {"CLAUDE_CODE_OAUTH_TOKEN": token} if token else {}


async def _run(prompt: str, system_prompt: str, resume: str | None) -> tuple[str, str | None]:
    options = ClaudeAgentOptions(
        env=_claude_env(),
        system_prompt=system_prompt,
        cwd=str(config.ROOT),
        allowed_tools=TOOLS,
        permission_mode="bypassPermissions",
        model=config.MODEL,
        resume=resume,
    )
    # Text written after the last tool call is the reply; earlier text is
    # usually "let me check..." narration that shouldn't reach Telegram.
    segments: list[list[str]] = [[]]
    session_id: str | None = None
    result_text = ""
    is_error = False
    api_error: tuple[str, str] | None = None  # (kind, text) from a failed API call
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                if getattr(msg, "error", None):
                    text = " ".join(b.text for b in msg.content if isinstance(b, TextBlock))
                    api_error = (msg.error, text)
                    continue
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        segments.append([])
                    elif isinstance(block, TextBlock) and block.text.strip():
                        segments[-1].append(block.text.strip())
            elif isinstance(msg, ResultMessage):
                session_id = msg.session_id
                result_text = msg.result or ""
                is_error = msg.is_error
    except Exception as e:
        # The SDK raises a generic error after an API failure; report the real cause.
        if api_error:
            raise _unavailable(*api_error) from e
        raise
    reply = "\n\n".join(segments[-1]) or "\n\n".join(t for seg in segments for t in seg)
    if api_error and not reply:
        raise _unavailable(*api_error)
    if is_error and not reply:
        if _looks_like_auth_error(result_text):
            raise AuthError(result_text)
        raise RuntimeError(result_text or "Claude returned an error with no message")
    return reply or result_text, session_id


async def ask(prompt: str, *, now: dt.datetime | None = None) -> str:
    """One Iroas turn. Resumes today's session; starts fresh on a new day or if
    the old session can't be resumed. Raises ClaudeUnavailable (AuthError for
    login problems) when Claude can't answer."""
    now = now or dt.datetime.now()
    today = now.date().isoformat()
    async with _lock:
        ensure_data_files()
        system_prompt = build_system_prompt(now)
        state = scheduler.load_state()
        resume = _session_for_today(state, today)
        try:
            reply, session_id = await _run(prompt, system_prompt, resume)
        except ClaudeUnavailable:
            raise
        except Exception as e:
            if _looks_like_auth_error(str(e)):
                raise AuthError(str(e)) from e
            if not resume:
                raise
            logger.warning("resume of session %s failed (%s); starting fresh", resume, e)
            reply, session_id = await _run(prompt, system_prompt, None)
        # Iroas may have pushed to Hevy or edited settings this turn.
        invalidate_hevy_cache()
        state = scheduler.load_state()
        if session_id:
            state["session_id"], state["session_date"] = session_id, today
            scheduler.save_state(state)
        return reply.strip()


def reset_session() -> None:
    state = scheduler.load_state()
    state.pop("session_id", None)
    state.pop("session_date", None)
    scheduler.save_state(state)

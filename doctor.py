"""Checks that everything Iroas needs is working. setup.bat runs it at the end;
run it yourself any time with doctor.bat (or `python doctor.py`).

    python doctor.py            # full check, including a tiny Claude test
    python doctor.py --no-claude
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OK, BAD = "[ OK ]", "[FAIL]"


def check_python() -> bool:
    good = sys.version_info >= (3, 10)
    print(f"{OK if good else BAD} Python {sys.version.split()[0]}")
    return good


def check_packages() -> bool:
    missing = []
    for mod in ("claude_agent_sdk", "telegram", "dotenv"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"{BAD} Missing packages: {', '.join(missing)} — run setup.bat again")
        return False
    print(f"{OK} Python packages installed")
    return True


def check_telegram() -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(f"{BAD} TELEGRAM_BOT_TOKEN missing from .env")
        return False
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=15) as r:
            me = json.loads(r.read().decode())["result"]
        print(f"{OK} Telegram bot: @{me['username']}")
        return True
    except urllib.error.HTTPError as e:
        print(f"{BAD} Telegram rejected the bot token (HTTP {e.code}) — get a fresh one from @BotFather")
    except Exception as e:
        print(f"{BAD} Couldn't reach Telegram: {e}")
    return False


def check_hevy() -> bool:
    import hevy
    if not hevy.is_configured():
        print(f"{BAD} HEVY_API_KEY missing from .env")
        return False
    try:
        c = hevy.HevyClient()
        info = c.user_info()
        print(f"{OK} Hevy account: {info.get('name') or info.get('id') or '?'} "
              f"({c.workout_count()} workouts logged)")
        return True
    except hevy.HevyError as e:
        print(f"{BAD} Hevy: {e}")
        return False


def check_pairing() -> bool:
    import settings
    s = settings.load()
    if s.get("owner_telegram_id"):
        print(f"{OK} Paired with Telegram user {s.get('owner_name') or s['owner_telegram_id']}")
    elif config.PAIRING_CODE:
        print(f"{OK} Not paired yet — send your bot:  /start {config.PAIRING_CODE}")
    else:
        print(f"{BAD} No PAIRING_CODE in .env — run setup.bat again")
        return False
    return True


async def _claude_ping() -> str:
    os.environ.pop("ANTHROPIC_API_KEY", None)
    import windows_subprocess
    windows_subprocess.patch_for_no_window()
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
    text, err = "", ""
    opts = ClaudeAgentOptions(system_prompt="Reply with exactly: OK", allowed_tools=[],
                              max_turns=1, cwd=str(config.ROOT), model=config.MODEL)
    try:
        async for m in query(prompt="ping", options=opts):
            if isinstance(m, AssistantMessage):
                joined = "".join(b.text for b in m.content if isinstance(b, TextBlock))
                if getattr(m, "error", None):
                    err = f"{m.error}: {joined}"
                    continue
                text += joined
            elif isinstance(m, ResultMessage) and m.is_error and not err:
                err = m.result or "error"
    except Exception:
        if not err:  # the SDK raises a generic error after an API failure
            raise
    if err and not text:
        raise RuntimeError(err)
    return text.strip()


def check_claude() -> bool:
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        print(f"{BAD} CLAUDE_CODE_OAUTH_TOKEN missing from .env — run setup.bat again")
        return False
    try:
        reply = asyncio.run(asyncio.wait_for(_claude_ping(), timeout=120))
        print(f"{OK} Claude (subscription) replied: {reply[:40]!r}")
        return True
    except Exception as e:
        print(f"{BAD} Claude didn't answer: {str(e)[:300]}")
        print("       If this mentions login/401/auth: double-click refresh_claude_login.bat.")
        return False


def main(argv: list[str]) -> int:
    print("Iroas health check\n")
    results = [check_python(), check_packages()]
    if results[-1]:
        results += [check_telegram(), check_hevy(), check_pairing()]
        if "--no-claude" not in argv:
            results.append(check_claude())
    print()
    if all(results):
        print("All good.")
        return 0
    print("Something needs fixing (see [FAIL] lines above).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

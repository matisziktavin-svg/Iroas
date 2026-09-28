"""Iroas on Telegram. Start with start_iroas.bat (or `python bot.py`).

Only one person can talk to it: whoever first sends `/start <pairing code>`
(the code is printed by setup and stored in .env). Everyone else is ignored.

Commands:  /help  /settings  /new (fresh conversation)  /checkin (run tonight's
check-in now)
"""
import asyncio
import contextlib
import datetime as dt
import logging
import logging.handlers
import socket
import sys

import config
import agent
import scheduler
import settings as settings_mod

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import InvalidToken
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logger = logging.getLogger("iroas")

TG_LIMIT = 4000  # Telegram caps messages at 4096 chars
CHECK_EVERY_S = 60
LOCK_PORT = 47391  # a local port held open so only one copy of Iroas runs
EXIT_NOT_CONFIGURED = 2
EXIT_ALREADY_RUNNING = 3


def setup_logging() -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_h = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / "iroas.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_h.setFormatter(fmt)
    handlers = [file_h]
    if sys.stdout is not None:  # pythonw has no console
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        handlers.append(console)
    logging.basicConfig(level=logging.INFO, handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def chunk(text: str, limit: int = TG_LIMIT) -> list[str]:
    """Split on paragraph, then line, then hard boundaries to fit Telegram."""
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    out.append(text)
    return out


def is_owner(user_id: int | None, s: dict) -> bool:
    return user_id is not None and s.get("owner_telegram_id") == user_id


def try_pair(user_id: int, first_name: str, code: str, s: dict) -> str:
    """Result of `/start <code>`: 'paired', 'already-owner', 'taken', or 'bad-code'."""
    owner = s.get("owner_telegram_id")
    if owner == user_id:
        return "already-owner"
    if owner is not None:
        return "taken"
    if not config.PAIRING_CODE or code.strip() != config.PAIRING_CODE:
        return "bad-code"
    s["owner_telegram_id"] = user_id
    if not s.get("owner_name"):
        s["owner_name"] = first_name or ""
    settings_mod.save(s)
    return "paired"


async def send(bot, chat_id: int, text: str) -> None:
    for part in chunk(text):
        await bot.send_message(chat_id=chat_id, text=part)


@contextlib.asynccontextmanager
async def typing(bot, chat_id: int):
    """Keep "Iroas is typing…" showing while Claude works (it expires after 5s)."""
    async def loop():
        while True:
            with contextlib.suppress(Exception):
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()


async def run_turn(bot, chat_id: int, prompt: str) -> None:
    async with typing(bot, chat_id):
        try:
            reply = await agent.ask(prompt)
        except agent.ClaudeUnavailable as e:
            logger.error("Claude unavailable: %s", e)
            reply = e.user_message
        except Exception:
            logger.exception("Iroas turn failed")
            reply = ("Something went wrong on my end (details are in logs/iroas.log). "
                     "Try again in a minute.")
    await send(bot, chat_id, reply or "(no reply)")


# --- handlers ----------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    s = settings_mod.load()
    code = " ".join(ctx.args or [])
    result = try_pair(user.id, user.first_name, code, s)
    chat_id = update.effective_chat.id
    if result == "taken":
        logger.warning("ignored /start from non-owner %s", user.id)
        return
    if result == "bad-code":
        await update.message.reply_text(
            "Send /start followed by the pairing code shown during setup, e.g. /start 123456")
        return
    if result == "paired":
        logger.info("paired with owner %s (%s)", user.id, user.first_name)
        await update.message.reply_text("Paired. This bot now only listens to you.")
        prompt = ("[System: they just paired with you on Telegram for the very first time. "
                  "Introduce yourself briefly and begin onboarding.]")
    else:
        prompt = "[System: they sent /start again. Greet them and pick up where you left off.]"
    await run_turn(ctx.bot, chat_id, prompt)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_user.id, settings_mod.load()):
        return
    await update.message.reply_text(
        "Just talk to me like a person — tell me about workouts, ask for advice, "
        "or ask me to change a setting.\n\n"
        "/settings — show what's switched on\n"
        "/new — start a fresh conversation (your files are kept)\n"
        "/checkin — run tonight's check-in right now")


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    s = settings_mod.load()
    if not is_owner(update.effective_user.id, s):
        return
    await update.message.reply_text(
        settings_mod.describe(s) + "\n\nTo change one, just tell me "
        "(\"turn off the weekly weigh-in\", \"check in at 8pm\").")


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_user.id, settings_mod.load()):
        return
    agent.reset_session()
    await update.message.reply_text("Fresh conversation started. I still have all your notes.")


async def cmd_checkin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    s = settings_mod.load()
    if not is_owner(update.effective_user.id, s):
        return
    due = {"daily": bool(s["features"].get("daily_review")),
           "body_comp": bool(s["features"].get("body_comp")),
           "nudges": bool(s["features"].get("nudges"))}
    if not any(due.values()):
        await update.message.reply_text("All check-in features are switched off (see /settings).")
        return
    await run_turn(ctx.bot, update.effective_chat.id, scheduler.checkin_prompt(due, dt.datetime.now()))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    s = settings_mod.load()
    if not is_owner(update.effective_user.id, s):
        if s.get("owner_telegram_id") is None:
            await update.message.reply_text(
                "I'm not paired yet. Send /start followed by the pairing code from setup.")
        return
    await run_turn(ctx.bot, update.effective_chat.id, update.message.text)


async def on_other(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_user.id, settings_mod.load()):
        return
    await update.message.reply_text("I can only read text messages for now — type it out for me.")


# --- scheduled check-in ------------------------------------------------------

async def checkin_tick(bot) -> None:
    now = dt.datetime.now()
    s = settings_mod.load()
    state = scheduler.load_state()
    log_text = (config.DATA_DIR / "log.md").read_text(encoding="utf-8") \
        if (config.DATA_DIR / "log.md").exists() else ""
    meas_text = (config.DATA_DIR / "measurements.md").read_text(encoding="utf-8") \
        if (config.DATA_DIR / "measurements.md").exists() else ""
    due = scheduler.due_checkin(now, s, state, log_text, meas_text)
    if due is None:
        return
    # Record first so a crash mid-turn can't cause a re-ping loop.
    state["last_checkin_date"] = now.date().isoformat()
    if due["body_comp"]:
        state["last_body_comp_ask_date"] = now.date().isoformat()
    scheduler.save_state(state)
    logger.info("running scheduled check-in: %s", due)
    chat_id = s["owner_telegram_id"]  # private chat id == user id
    try:
        reply = await agent.ask(scheduler.checkin_prompt(due, now), now=now)
    except agent.ClaudeUnavailable as e:
        logger.error("check-in: Claude unavailable: %s", e)
        await send(bot, chat_id, e.user_message)
        return
    if reply.strip() == scheduler.SILENT or not reply.strip():
        logger.info("check-in: nothing to say")
        return
    await send(bot, chat_id, reply)


async def checkin_loop(app: Application) -> None:
    while True:
        try:
            await checkin_tick(app.bot)
        except Exception:
            logger.exception("check-in tick failed")
        await asyncio.sleep(CHECK_EVERY_S)


async def post_init(app: Application) -> None:
    app.create_task(checkin_loop(app))  # PTB cancels it on shutdown


def acquire_single_instance_lock() -> socket.socket | None:
    """Two copies polling Telegram fight each other ("Conflict" errors), e.g.
    start_iroas.bat plus a logon task. Holding a localhost port prevents it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        sock.listen(1)
    except OSError:
        sock.close()
        return None
    return sock


def main() -> None:
    setup_logging()
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing from .env — run setup.bat first.")
        raise SystemExit(EXIT_NOT_CONFIGURED)
    lock = acquire_single_instance_lock()
    if lock is None:
        logger.error("Iroas is already running (port %s is held). Not starting a second copy.", LOCK_PORT)
        raise SystemExit(EXIT_ALREADY_RUNNING)
    agent.ensure_data_files()
    s = settings_mod.load()
    if not config.SETTINGS_PATH.exists():
        settings_mod.save(s)
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("checkin", cmd_checkin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, on_other))
    if s.get("owner_telegram_id") is None:
        logger.info("Not paired yet. In Telegram, send your bot:  /start %s", config.PAIRING_CODE)
    logger.info("Iroas is running. Keep this window open (minimize it is fine). Ctrl+C to stop.")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except InvalidToken:
        logger.error("Telegram rejected the bot token. Run setup.bat to enter it again.")
        raise SystemExit(EXIT_NOT_CONFIGURED)


if __name__ == "__main__":
    main()

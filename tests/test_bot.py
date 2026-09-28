import bot
import config
import settings


def test_chunk_respects_limit_and_keeps_text():
    text = ("para one " * 300) + "\n\n" + ("para two " * 300)
    parts = bot.chunk(text, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert " ".join(parts).split() == text.split()


def test_chunk_empty():
    assert bot.chunk("   ") == []


def test_pairing_flow(sandbox, monkeypatch):
    monkeypatch.setattr(config, "PAIRING_CODE", "123456")
    s = settings.load()
    assert bot.try_pair(1, "Dave", "999999", s) == "bad-code"
    assert bot.try_pair(1, "Dave", "", s) == "bad-code"
    assert bot.try_pair(1, "Dave", " 123456 ", s) == "paired"
    s = settings.load()
    assert s["owner_telegram_id"] == 1 and s["owner_name"] == "Dave"
    assert bot.try_pair(1, "Dave", "123456", s) == "already-owner"
    assert bot.try_pair(2, "Mallory", "123456", s) == "taken"
    assert bot.is_owner(1, s) and not bot.is_owner(2, s) and not bot.is_owner(None, s)


def test_no_pairing_without_code_configured(sandbox, monkeypatch):
    monkeypatch.setattr(config, "PAIRING_CODE", "")
    assert bot.try_pair(1, "x", "", settings.load()) == "bad-code"


def test_single_instance_lock():
    first = bot.acquire_single_instance_lock()
    if first is None:  # a real Iroas is running on this machine
        return
    try:
        assert bot.acquire_single_instance_lock() is None
    finally:
        first.close()

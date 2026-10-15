"""Startup helpers: token validation diagnostics and the missing-terminal path.

These are the first things a new user hits, so the *message* matters as much as
the exit code: a bad token and a blocked network need different fixes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import config
import main


def _bot(error: Exception | None = None, username: str = "smartel_bot"):
    bot = MagicMock()
    if error is not None:
        bot.get_me.side_effect = error
    else:
        bot.get_me.return_value = MagicMock(id=42, username=username)
    return bot


def test_validate_bot_returns_identity():
    assert main.validate_bot(_bot()) == {"id": 42, "username": "smartel_bot"}


def test_validate_bot_reports_a_bad_token(monkeypatch, caplog):
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    bot = _bot(Exception("Unauthorized"))
    with pytest.raises(SystemExit) as exc:
        main.validate_bot(bot)
    assert exc.value.code == 2
    assert "rejected the BOT_TOKEN" in caplog.text
    assert bot.get_me.call_count == 1  # no pointless retry for a bad token


def test_validate_bot_reports_a_network_problem(monkeypatch, caplog):
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    bot = _bot(OSError("SSLError: certificate verify failed"))
    with pytest.raises(SystemExit):
        main.validate_bot(bot)
    assert bot.get_me.call_count == 2          # transient -> retried once
    assert "api.telegram.org" in caplog.text
    assert "firewall or proxy" in caplog.text
    assert "check BOT_TOKEN" not in caplog.text


def test_validate_bot_falls_back_to_a_generic_message(monkeypatch, caplog):
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    with pytest.raises(SystemExit):
        main.validate_bot(_bot(RuntimeError("weird failure")))
    assert "weird failure" in caplog.text


def test_allowed_updates_covers_the_business_types():
    # Omitting these is the classic "the bot never sees customer messages" bug.
    for needed in ("business_connection", "business_message", "edited_business_message",
                   "deleted_business_messages", "message", "callback_query"):
        assert needed in main.ALLOWED_UPDATES


def test_wizard_without_a_terminal_explains_what_to_do(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")

    def no_terminal():
        raise EOFError

    monkeypatch.setattr(config, "run_wizard", no_terminal)
    with pytest.raises(SystemExit) as exc:
        config.load_or_run_wizard()
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "cp .env.example .env" in out
    assert "BOT_TOKEN" in out


def test_wizard_keyboard_interrupt_is_also_handled(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")

    def interrupted():
        raise KeyboardInterrupt

    monkeypatch.setattr(config, "run_wizard", interrupted)
    with pytest.raises(SystemExit):
        config.load_or_run_wizard()
    assert "No .env file was found" in capsys.readouterr().out


def test_invalid_env_without_a_terminal_exits_cleanly(monkeypatch, capsys, tmp_path):
    env = tmp_path / ".env"
    env.write_text("BOT_TOKEN=not-a-token\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env)
    with pytest.raises(SystemExit):
        config.load_or_run_wizard()
    out = capsys.readouterr().out
    assert "invalid" in out
    assert ".env.example" in out

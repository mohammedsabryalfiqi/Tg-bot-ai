"""Tests for handlers/owner_tools.py: reply modes, chat listing/transcripts,
manual replies, stats, health report and the backup export."""

from __future__ import annotations

import json

import pytest

from handlers import owner_tools as tools


@pytest.fixture
def env(db, stub_bot, mocker):
    mocker.patch("telegram_api.send_reply")
    db.upsert_business_connection("bc1", 999, True, True)
    return db


# --- reply modes -------------------------------------------------------------
def test_mode_defaults_to_off(db):
    assert tools.current_mode() == "off"


@pytest.mark.parametrize("mode,auto,approval", [
    ("auto", True, False),
    ("draft", True, True),
    ("off", False, True),
])
def test_set_mode_maps_to_the_two_switches(db, mode, auto, approval):
    assert tools.set_mode(mode) == mode
    assert db.get_bool("auto_reply_enabled") is auto
    assert db.get_bool("approval_mode_enabled") is approval
    assert tools.current_mode() == mode


def test_set_mode_rejects_unknown_values(db):
    assert tools.set_mode("banana") == "off"
    assert tools.current_mode() == "off"


def test_cmd_mode_reports_current(env, make_message):
    tools.cmd_mode(make_message())
    sent = env  # noqa: F841 - readability
    text = pytest.importorskip("handlers").bot.send_message.call_args.args[1]
    assert "Current mode" in text


def test_cmd_mode_sets_from_argument(env, make_message):
    import handlers
    tools.cmd_mode(make_message(text="/mode auto"))
    assert tools.current_mode() == "auto"
    assert handlers.bot.send_message.call_args.args[1].count("Auto-reply") >= 1


# --- chat listing / transcripts ---------------------------------------------
def test_cmd_chats_without_history(env, make_message):
    import handlers
    tools.cmd_chats(make_message())
    assert "No customer chats yet" in handlers.bot.send_message.call_args.args[1]


def test_cmd_chats_lists_recent_customers(env, make_message):
    import handlers
    env.upsert_customer("bc1", 5, "Cara", "Doe", "cara")
    env.insert_message("bc1", 5, 1, "in", "user", "hello")
    tools.cmd_chats(make_message())
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    assert any("Cara" in button.text for row in markup.keyboard for button in row)


def test_cmd_chat_renders_transcript(env, make_message):
    import handlers
    env.upsert_customer("bc1", 5, "Cara", None, None)
    env.insert_message("bc1", 5, 1, "in", "user", "how much?")
    env.insert_message("bc1", 5, None, "out", "assistant", "500 EGP")
    tools.cmd_chat(make_message(text="/chat 5"))
    text = handlers.bot.send_message.call_args.args[1]
    assert "how much?" in text
    assert "500 EGP" in text


def test_cmd_chat_unknown_id(env, make_message):
    import handlers
    env.upsert_business_connection("bc2", 999, True, True)  # now 2 connections
    tools.cmd_chat(make_message(text="/chat 42"))
    assert "no messages" in handlers.bot.send_message.call_args.args[1].lower()


def test_cmd_chat_validates_input(env, make_message):
    import handlers
    tools.cmd_chat(make_message(text="/chat abc"))
    assert "Usage" in handlers.bot.send_message.call_args.args[1]


# --- manual reply ------------------------------------------------------------
def test_cmd_reply_sends_and_pauses(env, make_message, mocker):
    import handlers
    send = mocker.patch("telegram_api.send_reply")
    env.upsert_customer("bc1", 5, "Cara", None, None)
    tools.cmd_reply(make_message(text="/reply 5 we will call you back"))
    assert send.call_args.kwargs["business_connection_id"] == "bc1"
    assert send.call_args.args[2] == "we will call you back"
    assert env.get_pause("bc1", 5) is not None          # takeover pause
    assert env.count_messages(direction="out", role="owner") == 1
    assert "Sent from your business account" in handlers.bot.send_message.call_args.args[1]


def test_cmd_reply_requires_arguments(env, make_message):
    import handlers
    tools.cmd_reply(make_message(text="/reply"))
    assert "Usage" in handlers.bot.send_message.call_args.args[1]


def test_takeover_and_handback(env, make_message, mocker):
    import handlers
    mocker.patch("telegram_api.send_reply")
    env.upsert_customer("bc1", 5, "Cara", None, None)
    tools._do_pause_command(make_message(text="/takeover 5"), pause=True)
    assert env.get_pause("bc1", 5) is not None
    tools._do_pause_command(make_message(text="/handback 5"), pause=False)
    assert env.get_pause("bc1", 5) is None
    assert "answering that chat again" in handlers.bot.send_message.call_args.args[1]


# --- stats & health ----------------------------------------------------------
def test_cmd_stats_counts(env, make_message):
    import handlers
    env.upsert_customer("bc1", 5, "Cara", None, None)
    env.insert_message("bc1", 5, 1, "in", "user", "hi")
    env.insert_message("bc1", 5, None, "out", "assistant", "hello")
    tools.cmd_stats(make_message())
    text = handlers.bot.send_message.call_args.args[1]
    assert "Statistics" in text
    assert "AI replies" in text


def test_health_report_flags_missing_connection(db, stub_bot, mocker):
    mocker.patch("telegram_api.send_reply")
    stub_bot.get_me.return_value.username = "mybot"
    report = tools.health_report()
    assert "Telegram API reachable" in report
    assert "AI not configured" in report
    assert "No business connection" in report


def test_health_report_flags_read_only_connection(env, stub_bot):
    stub_bot.get_me.return_value.username = "mybot"
    env.upsert_business_connection("bc-readonly", 999, True, False)
    report = tools.health_report()
    assert "can reply: False" in report
    assert "Allow bot to reply" in report


# --- backup ------------------------------------------------------------------
def test_export_backup_writes_json(env, make_message, mocker):
    sent = mocker.patch("telegram_api.send_document")
    env.set_setting("business_name", "Cairo Bakery")
    from services import faq_service
    faq_service.add("price", "500")
    tools.export_backup(12345)
    path = sent.call_args.args[2]
    assert not path.exists()  # temp file is removed after sending
    assert "settings" in sent.call_args.kwargs["caption"] or "Backup" in sent.call_args.kwargs["caption"]


def test_export_backup_payload_has_no_secrets(env, mocker):
    captured = {}

    def fake_send(bot, chat_id, path, caption="", reply_markup=None):
        captured["payload"] = json.loads(path.read_text(encoding="utf-8"))

    mocker.patch("telegram_api.send_document", side_effect=fake_send)
    from services import ai_service
    ai_service.store_api_key("sk-super-secret-123456", "openai")
    env.set_setting("business_name", "Cairo Bakery")

    tools.export_backup(1)

    payload = captured["payload"]
    assert payload["type"] == "smartel-backup"
    assert payload["settings"]["business_name"] == "Cairo Bakery"
    assert "sk-super-secret-123456" not in json.dumps(payload)
    assert "ai_api_key" not in payload["settings"]

"""Tests for handlers/owner_tools.py: reply modes, chat transcripts, manual
replies, statistics, health checks, backups and the tool callbacks."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import database
import handlers
import keyboards
import telegram_api
from handlers import owner_tools
from services import business_service


@pytest.fixture
def env(db, stub_bot, mocker):
    """A configured business account + one customer chat with history."""
    db.upsert_business_connection("bc1", 999, True, True)
    db.upsert_customer("bc1", 5, "Mona", "Ali", "mona")
    db.insert_message("bc1", 5, 1, "in", "user", "how much?")
    mocker.patch("telegram_api.send_reply", return_value=[{"message_id": 1}])
    return db


# Owner-facing messages go to the owner's DM chat, not to the customer chat.
OWNER_CHAT = 12345


def _sent(chat_id: int = OWNER_CHAT) -> list[str]:
    return [call.args[1] for call in handlers.bot.send_message.call_args_list
            if call.args[0] == chat_id]


def _msg(text: str = "", user_id: int = 12345, chat_id: int = OWNER_CHAT, **kw):
    """A duck-typed owner DM message (the owner chat, not a customer chat)."""
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id, first_name="Owner", last_name=None,
                                  username=None),
        message_id=kw.pop("message_id", 9001),
        text=text,
        caption=None,
        content_type="text",
        business_connection_id=None,
        sender_business_bot=None,
        **kw,
    )


# --- reply modes -------------------------------------------------------------
def test_mode_default_is_off_then_draft(env):
    assert owner_tools.current_mode() == "off"
    assert owner_tools.set_mode("draft") == "draft"
    assert env.get_bool("auto_reply_enabled") is True
    assert env.get_bool("approval_mode_enabled") is True


def test_set_mode_auto_disables_approval(env):
    owner_tools.set_mode("draft")
    assert owner_tools.set_mode("auto") == "auto"
    assert env.get_bool("auto_reply_enabled") is True
    assert env.get_bool("approval_mode_enabled") is False


def test_set_mode_off_keeps_nothing_on(env):
    owner_tools.set_mode("auto")
    assert owner_tools.set_mode("off") == "off"
    assert env.get_bool("auto_reply_enabled") is False
    assert owner_tools.current_mode() == "off"


def test_unknown_mode_argument_is_treated_as_off(env):
    owner_tools.set_mode("auto")
    assert owner_tools.set_mode("banana") == "off"


def test_cmd_mode_reports_and_offers_buttons(env, make_message):
    owner_tools.cmd_mode(_msg(text="/mode"))
    assert "Current mode" in _sent()[0]
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    assert "auto" in [b.callback_data for row in markup.keyboard for b in row][0]


def test_cmd_mode_switches_with_an_argument(env, make_message):
    owner_tools.cmd_mode(_msg(text="/mode draft"))
    assert env.get_bool("approval_mode_enabled") is True
    assert "Draft mode" in _sent()[0]


# --- chats -------------------------------------------------------------------
def test_cmd_chats_lists_customers(env, make_message):
    owner_tools.cmd_chats(_msg())
    text = _sent()[0]
    assert "Recent customer chats" in text
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "tool:chat:5" in data


def test_cmd_chats_without_history(env):
    with database.write_tx() as cur:
        cur.execute("DELETE FROM customers")
    owner_tools.cmd_chats(_msg())
    assert "No customer chats yet" in _sent()[0]


def test_transcript_shows_history_and_pause_state(env, make_message):
    owner_tools.cmd_chat(_msg(text="/chat 5"))
    text = _sent()[0]
    assert "Mona Ali (@mona)" in text
    assert "how much?" in text
    assert "active" in text


def test_chat_command_validates_the_id(env, make_message):
    owner_tools.cmd_chat(_msg(text="/chat abc"))
    assert "Usage" in _sent()[0]


def test_chat_command_for_an_unknown_chat(env):
    # With more than one connection there is no safe fallback for an unknown chat.
    database.upsert_business_connection("bc2", 555, True, True)
    owner_tools.cmd_chat(_msg(text="/chat 999"))
    assert "no messages for that chat" in _sent()[0]


def test_takeover_and_handback(env, make_message):
    owner_tools._do_pause_command(_msg(text="/takeover 5"), pause=True)
    assert business_service.is_chat_paused("bc1", 5) is True
    assert "will not answer" in _sent()[0]

    owner_tools._do_pause_command(_msg(text="/handback 5"), pause=False)
    assert business_service.is_chat_paused("bc1", 5) is False
    assert "answering that chat again" in _sent()[1]


def test_handback_on_a_chat_that_was_not_paused(env, make_message):
    owner_tools._do_pause_command(_msg(text="/handback 5"), pause=False)
    assert "was not paused" in _sent()[0]


def test_pause_commands_need_a_chat_id(env, make_message):
    owner_tools._do_pause_command(_msg(text="/takeover"), pause=True)
    assert "Usage" in _sent()[0]


# --- manual replies ----------------------------------------------------------
def test_cmd_reply_sends_from_the_business_account(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    owner_tools.cmd_reply(_msg(text="/reply 5 I'll check and get back to you"))
    args = telegram_api.send_reply.call_args
    assert args.args[1] == 5
    assert args.args[2] == "I'll check and get back to you"
    # Owner messages are sent verbatim: no markdown rewriting.
    assert args.kwargs.get("business_connection_id") == "bc1"
    # Recorded in the transcript and the chat is paused (takeover).
    rows = database.get_recent_messages("bc1", 5, limit=5)
    assert rows[-1]["role"] == "owner"
    assert business_service.is_chat_paused("bc1", 5) is True
    assert "paused for 30 min" in _sent()[0]


def test_cmd_reply_to_an_unknown_chat(env):
    database.upsert_business_connection("bc2", 555, True, True)
    owner_tools.cmd_reply(_msg(text="/reply 999 hi"))
    assert "Unknown chat id" in _sent()[0]


def test_owner_reply_falls_back_to_the_only_connection(env):
    """`/reply <chat_id>` must work before the customer row exists."""
    import telegram_api as tg
    tg.send_reply.reset_mock()
    owner_tools._send_owner_reply(OWNER_CHAT, 777, "hello")
    assert tg.send_reply.call_args.args[1] == 777


def test_cmd_reply_when_the_connection_cannot_reply(env, make_message):
    env.set_setting("auto_reply_enabled", True)
    database.upsert_business_connection("bc1", 999, True, False)
    owner_tools.cmd_reply(_msg(text="/reply 5 hi"))
    assert "cannot reply" in _sent()[0]


def test_cmd_reply_reports_send_failures(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply", side_effect=RuntimeError("nope"))
    owner_tools.cmd_reply(_msg(text="/reply 5 hi"))
    assert "Could not send" in _sent()[0]


def test_cmd_reply_usage(env, make_message):
    owner_tools.cmd_reply(_msg(text="/reply"))
    assert "Usage" in _sent()[0]


# --- stats / health ----------------------------------------------------------
def test_cmd_stats_counts(env, make_message):
    env.upsert_customer("bc1", 6, "Other", None, None)
    owner_tools.cmd_stats(_msg())
    text = _sent()[0]
    assert "Customers: <b>2</b>" in text
    assert "Mode: <b>off</b>" in text


def test_health_report_mentions_the_unconfigured_pieces(env, mocker):
    handlers.bot.get_me.return_value = mocker.MagicMock(username="smartel_bot")
    report = owner_tools.health_report()
    assert "@smartel_bot" in report
    assert "Business connection" not in report or "Connection" in report
    assert "AI ready" in report or "AI not configured" in report
    assert "Mode:" in report


def test_health_reports_a_missing_business_connection(env, mocker):
    handlers.bot.get_me.return_value = mocker.MagicMock(username="b")
    with database.write_tx() as cur:
        cur.execute("DELETE FROM business_connections")
    assert "No business connection" in owner_tools.health_report()


def test_health_survives_a_dead_telegram_api(env):
    handlers.bot.get_me.side_effect = RuntimeError("boom")
    assert "Telegram API error" in owner_tools.health_report()


# --- backup ------------------------------------------------------------------
def test_export_backup_contains_settings_without_secrets(env, mocker):
    captured = {}
    mocker.patch("telegram_api.send_document",
                 side_effect=lambda bot, chat, path, **kw: captured.update(
                     path=path, payload=json.loads(path.read_text(encoding="utf-8"))))
    env.set_setting("custom_instructions", "Always be brief.")

    owner_tools.export_backup(12345)

    payload = captured["payload"]
    assert payload["type"] == "smartel-backup"
    assert payload["settings"]["custom_instructions"] == "Always be brief."
    assert payload["stats"]["messages_in"] == 1
    assert "ai_api_key" not in payload["settings"]


def test_export_backup_removes_the_temp_file(env, mocker):
    captured = {}
    mocker.patch("telegram_api.send_document",
                 side_effect=lambda bot, chat, path, **kw: captured.update(path=path))
    owner_tools.export_backup(12345)
    assert not captured["path"].exists()


# --- callbacks ---------------------------------------------------------------
def test_callback_close_deletes_the_message(env, make_call):
    owner_tools.on_callback(make_call(data="tool:close"))
    handlers.bot.delete_message.assert_called_once()


def test_callback_health_resends_the_report(env, make_call, mocker):
    mocker.patch("handlers.owner_tools.health_report", return_value="❤️ report")
    owner_tools.on_callback(make_call(data="tool:health"))
    assert "❤️ report" in _sent()[0]


def test_callback_pause_and_resume(env, make_call):
    owner_tools.on_callback(make_call(data="tool:pause:5"))
    assert business_service.is_chat_paused("bc1", 5) is True
    owner_tools.on_callback(make_call(data="tool:resume:5"))
    assert business_service.is_chat_paused("bc1", 5) is False


def test_callback_with_a_bad_chat_id_is_rejected(env, make_call):
    owner_tools.on_callback(make_call(data="tool:chat:abc"))
    assert handlers.bot.answer_callback_query.call_args.kwargs["text"] == "Bad chat id."


def test_callback_setup_opens_the_checklist(env, make_call, mocker):
    checklist = mocker.patch("handlers.setup_guide.send_checklist")
    owner_tools.on_callback(make_call(data="tool:setup"))
    checklist.assert_called_once_with(12345)


def test_callback_setup_step(env, make_call, mocker):
    step = mocker.patch("handlers.setup_guide.send_step")
    owner_tools.on_callback(make_call(data="tool:setup_step:ai"))
    step.assert_called_once_with(12345, "ai")

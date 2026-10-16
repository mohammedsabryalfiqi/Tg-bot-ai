"""Tests for handlers/direct_messages.py — who the direct pipeline answers.

The happy path (reply, draft, welcome, non-text) is covered end-to-end in
``tests/integration/test_wiring.py``; this module pins the *gating* rules, where
a mistake is invisible in production but leaks the bot into conversations it
must not touch (the owner's own chat, group chats, other bots, commands).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import database
import handlers
import i18n
import security
from handlers import direct_messages as dm

OWNER_ID = 12345          # conftest's `stub_bot` claims this owner
CUSTOMER = 777


def _private_message(**kw):
    """A duck-typed private message with the fields the guard reads."""
    user = SimpleNamespace(id=kw.pop("user_id", CUSTOMER), is_bot=kw.pop("is_bot", False),
                           first_name="Mona", last_name=None, username=None)
    chat = SimpleNamespace(id=kw.pop("chat_id", CUSTOMER),
                           type=kw.pop("chat_type", "private"))
    fields = dict(chat=chat, from_user=user, message_id=kw.pop("message_id", 1),
                  text=kw.pop("text", "السلام عليكم"), caption=None,
                  content_type="text", business_connection_id=None,
                  sender_business_bot=None)
    fields.update(kw)
    return SimpleNamespace(**fields)


@pytest.fixture
def direct_env(db, stub_bot):
    """A real (empty) DB with the owner claimed and a usable AI backend.

    ``pollinations`` needs no API key, so ``ai_service.is_ready()`` is true
    without any network access — the guard under test is "is there anything to
    answer with", not the model call itself.
    """
    db.set_setting("ai_provider", "pollinations")
    return SimpleNamespace(db=db, bot=stub_bot)


# --- gating -------------------------------------------------------------------
def test_private_text_is_handled(direct_env):
    assert dm.should_handle(_private_message()) is True


def test_group_chats_are_ignored(direct_env):
    assert dm.should_handle(_private_message(chat_type="group")) is False


def test_other_bots_are_ignored(direct_env):
    assert dm.should_handle(_private_message(is_bot=True)) is False


def test_the_owners_own_messages_are_ignored(direct_env):
    assert dm.should_handle(_private_message(user_id=OWNER_ID, chat_id=OWNER_ID)) is False


def test_slash_commands_keep_their_own_handlers(direct_env):
    assert dm.should_handle(_private_message(text="/start")) is False
    assert dm.should_handle(_private_message(text="/ai")) is False


def test_the_direct_switch_off_stops_everything(direct_env):
    direct_env.db.set_setting("direct_reply_enabled", False)
    assert dm.should_handle(_private_message()) is False


def test_a_bot_without_an_ai_key_leaves_the_message_to_the_notice(direct_env, db):
    """Nothing to answer with -> the pre-existing "managed assistant" notice."""
    db.set_setting("ai_provider", "openai")
    assert dm.should_handle(_private_message()) is False


def test_an_unclaimed_bot_talks_to_nobody(direct_env, monkeypatch):
    monkeypatch.setattr(security, "_owner_id", None)
    assert dm.should_handle(_private_message()) is False


def test_operator_messages_are_left_to_the_owner_flow(direct_env, db):
    """While the owner has a pending reply parked, their message is an answer."""
    db.set_owner_pending_input(OWNER_ID, "edit_approval", {"id": 1}, 15)
    assert dm.should_handle(_private_message(user_id=OWNER_ID, chat_id=OWNER_ID)) is False


# --- helpers ------------------------------------------------------------------
def test_automation_switch_reads_both_modes(direct_env, db):
    db.set_setting("auto_reply_enabled", False)
    db.set_setting("approval_mode_enabled", False)
    assert dm._any_automation_on() is False
    db.set_setting("approval_mode_enabled", True)
    assert dm._any_automation_on() is True


def test_the_registered_handler_survives_a_crash(direct_env, monkeypatch):
    """A failure in the pipeline must never bubble into telebot's polling loop."""
    calls = {"n": 0}

    def boom(_message):
        calls["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(dm, "process_direct_message", boom)
    registered = {}

    class FakeBot:
        def message_handler(self, **kwargs):
            def deco(func):
                registered["func"] = func
                return func
            registered["kwargs"] = kwargs
            return deco

    dm.register(FakeBot(), SimpleNamespace())
    registered["func"](_private_message())      # must not raise

    assert calls["n"] == 1
    assert "text" in registered["kwargs"]["content_types"]

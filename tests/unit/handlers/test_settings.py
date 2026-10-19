"""Tests for handlers/settings.py: the settings root menu.

Focused on the AI rows — the menu must always lead the owner to the provider
screen, and to the free shortlist whenever the current setup cannot work
(no key yet, or a paid provider with no credit behind it).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import database
import handlers
import i18n
import security
from handlers import settings as settings_handler
from services import ai_service

OWNER_CHAT = 5231453921


def _msg():
    return SimpleNamespace(chat=SimpleNamespace(id=OWNER_CHAT),
                           from_user=SimpleNamespace(id=OWNER_CHAT, first_name="Owner",
                                                     last_name=None, username=None),
                           message_id=1, text="/settings", caption=None,
                           content_type="text", business_connection_id=None,
                           sender_business_bot=None)


def _row_labels() -> list[str]:
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    return [btn.text for row in markup.keyboard for btn in row]


def _row_data() -> list[str]:
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    return [btn.callback_data for row in markup.keyboard for btn in row]


@pytest.fixture
def env(db, stub_bot):
    security.init(stub_bot, OWNER_CHAT)
    return db


def test_root_menu_links_to_the_ai_screen(env):
    settings_handler.open_root(_msg())
    data = _row_data()
    assert "ai:root" in data
    assert "ai:models" in data
    assert any("Provider:" in label for label in _row_labels())


def test_root_menu_offers_free_providers_when_not_configured(env):
    settings_handler.open_root(_msg())
    assert "ai:providers_free" in _row_data()
    assert any("Free AI providers" in label for label in _row_labels())


def test_root_menu_offers_free_providers_on_a_paid_provider(env):
    ai_service.set_provider("openai")
    ai_service.store_api_key("sk-test", "openai")
    settings_handler.open_root(_msg())
    assert "ai:providers_free" in _row_data()


def test_root_menu_hides_the_free_shortcut_once_a_free_provider_is_ready(env):
    ai_service.set_provider("groq")
    ai_service.store_api_key("gsk-test", "groq")
    settings_handler.open_root(_msg())
    assert "ai:providers_free" not in _row_data()


def test_root_text_reports_the_active_backend(env):
    ai_service.set_provider("cerebras")
    settings_handler.open_root(_msg())
    assert "Cerebras" in handlers.bot.send_message.call_args.args[1]


# --- registry integrity -------------------------------------------------------
def test_every_group_has_at_least_one_row(env):
    """An empty group would render a section button that leads nowhere."""
    from collections import Counter
    counts = Counter(spec["group"] for spec in settings_handler.SETTINGS)
    assert set(counts) <= set(settings_handler._GROUP_KEYS)
    missing = [group for group in settings_handler._GROUP_KEYS if not counts[group]]
    assert missing == []


def test_every_row_is_a_real_setting_with_a_label(env):
    for spec in settings_handler.SETTINGS:
        assert spec["key"] in database.SETTINGS_SCHEMA, spec["key"]
        assert i18n.t(f"set.opt.{spec['key']}") != f"set.opt.{spec['key']}"
        for key in (spec.get("hint_key"),):
            if key:
                assert i18n.t(key) != key


def test_group_screens_are_reachable_from_the_root(env):
    settings_handler.open_root(_msg())
    data = _row_data()
    for group in settings_handler._GROUP_KEYS:
        assert f"set:group:{group}" in data


def test_limits_screen_edits_the_usage_caps(env, make_call):
    """Group screens are edits of the current message (not new messages)."""
    settings_handler.on_settings_callback(make_call(data="set:group:limits"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [btn.callback_data for row in markup.keyboard for btn in row]
    assert "set:num:max_reply_chars" in data
    assert "set:num:max_messages_per_customer_per_hour" in data
    assert "set:num:owner_takeover_pause_minutes" in data


def test_message_group_offers_welcome_and_payment_edit_buttons(env, make_call):
    settings_handler.on_settings_callback(make_call(data="set:group:messages"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [btn.callback_data for row in markup.keyboard for btn in row]
    assert "set:text:welcome_text" in data
    assert "set:text:payment_message" in data


def test_payment_message_can_be_updated_and_reset(env):
    from types import SimpleNamespace

    message = SimpleNamespace(chat=SimpleNamespace(id=OWNER_CHAT),
                              text="Pay {stars} Stars to continue.", caption=None)
    settings_handler.apply_pending(message, "set_text", {"key": "payment_message"})
    assert env.get_str("payment_message") == "Pay {stars} Stars to continue."

    message.text = "clear"
    settings_handler.apply_pending(message, "set_text", {"key": "payment_message"})
    assert env.get_str("payment_message") == ""

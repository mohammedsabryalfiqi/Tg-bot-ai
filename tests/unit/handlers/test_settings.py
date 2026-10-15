"""Tests for handlers/settings.py: the settings root menu.

Focused on the AI rows — the menu must always lead the owner to the provider
screen, and to the free shortlist whenever the current setup cannot work
(no key yet, or a paid provider with no credit behind it).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import handlers
from handlers import settings as settings_handler
from services import ai_service

OWNER_CHAT = 12345


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

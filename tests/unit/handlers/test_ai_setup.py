"""Tests for handlers/ai_setup.py: the in-Telegram provider setup flow (screens,
provider/model switching, key handling, validation and the connection test)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import database
import handlers
from handlers import ai_setup
from services import ai_service, providers

OWNER_CHAT = 12345


def _msg(text: str = "", message_id: int = 9001, chat_id: int = OWNER_CHAT, **kw):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=OWNER_CHAT, first_name="Owner", last_name=None,
                                  username=None),
        message_id=message_id,
        text=text,
        caption=None,
        content_type="text",
        business_connection_id=None,
        sender_business_bot=None,
        **kw,
    )


def _sent(chat_id: int = OWNER_CHAT) -> list[str]:
    return [call.args[1] for call in handlers.bot.send_message.call_args_list
            if call.args[0] == chat_id]


@pytest.fixture
def env(db, stub_bot):
    return db


# --- root screen -------------------------------------------------------------
def test_root_screen_reports_no_key(env):
    ai_setup.open_root(OWNER_CHAT)
    text = _sent()[0]
    assert "AI provider" in text
    assert "not configured" in text
    assert "API key" in text


def test_root_screen_reports_a_ready_provider(env, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda *a, **k: True)
    monkeypatch.setattr("services.ai_service.has_api_key", lambda *a, **k: True)
    ai_setup.open_root(OWNER_CHAT)
    assert "ready" in _sent()[0]


def test_root_screen_buttons_reflect_state(env):
    ai_setup.open_root(OWNER_CHAT)
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "ai:providers" in data
    assert "ai:key" in data


# --- provider list -----------------------------------------------------------
def test_provider_list_marks_the_active_one(env, make_call):
    ai_setup.on_callback(make_call(data="ai:providers"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "ai:provider:openai" in data
    assert "ai:provider:google" in data
    labels = [b.text for row in markup.keyboard for b in row]
    assert any("✅" in label or "•" in label for label in labels)


def test_selecting_a_provider_switches_and_explains_it(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:groq"))
    assert database.get_str("ai_provider") == "groq"
    text = handlers.bot.edit_message_text.call_args.args[0]
    assert "Groq" in text
    assert "console.groq.com" in text


def test_selecting_an_unknown_provider_is_rejected(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:nope"))
    assert database.get_str("ai_provider") != "nope"
    assert "Unknown provider" in handlers.bot.answer_callback_query.call_args.kwargs["text"]


def test_provider_switch_keeps_the_previous_model_choice(env, make_call):
    ai_service.set_model("gpt-4.1", "openai")
    ai_setup.on_callback(make_call(data="ai:provider:groq"))
    assert ai_service.active_model("openai") == "gpt-4.1"


# --- model picker ------------------------------------------------------------
def test_model_list_for_the_active_provider(env, make_call):
    ai_setup.on_callback(make_call(data="ai:models"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("ai:model:") for entry in data)
    assert "ai:model_custom" in data


def test_choosing_a_model_stores_it(env, make_call):
    ai_service.set_provider("openai")
    ai_setup.on_callback(make_call(data="ai:model:gpt-4.1"))
    assert ai_service.active_model("openai") == "gpt-4.1"


def test_custom_model_prompt_sets_a_pending_input(env, make_call):
    ai_setup.on_callback(make_call(data="ai:model_custom"))
    state = database.get_owner_pending_input(OWNER_CHAT)
    assert state["kind"] == "ai_model"
    assert "model name" in _sent()[0]


def test_codex_provider_asks_for_the_model_directly(env, make_call):
    ai_service.set_provider("codex")
    ai_setup.on_callback(make_call(data="ai:models"))
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "ai_model"


# --- key prompt / validation -------------------------------------------------
def test_key_prompt_explains_that_the_message_is_deleted(env, make_call):
    ai_setup.on_callback(make_call(data="ai:key"))
    state = database.get_owner_pending_input(OWNER_CHAT)
    assert state["kind"] == "ai_key"
    assert state["context"]["provider"] == "openai"
    assert "delete" in _sent()[0].lower()


def test_valid_key_is_stored_and_the_message_deleted(env, mocker):
    mocker.patch("services.ai_service.validate_key", return_value=(True, "Model replied: pong"))
    ai_setup.apply_pending(_msg(text="sk-test-key-123", message_id=77), "ai_key",
                           {"provider": "openai"})
    handlers.bot.delete_message.assert_called_once_with(OWNER_CHAT, 77)
    assert ai_service.has_api_key("openai") is True
    assert database.get_owner_pending_input(OWNER_CHAT) is None
    assert any("connected" in text for text in _sent())


def test_rejected_key_is_reported_and_not_stored(env, mocker):
    mocker.patch("services.ai_service.validate_key", return_value=(False, "Invalid API key"))
    ai_setup.apply_pending(_msg(text="sk-bad"), "ai_key", {"provider": "openai"})
    assert ai_service.has_api_key("openai") is False
    assert any("Invalid API key" in text for text in _sent())


def test_empty_answer_cancels(env):
    ai_setup.apply_pending(_msg(text="   "), "ai_key", {"provider": "openai"})
    assert "Nothing received" in _sent()[0]
    assert database.get_owner_pending_input(OWNER_CHAT) is None


def test_model_answer_is_applied(env):
    ai_setup.apply_pending(_msg(text="my-fine-tuned-model"), "ai_model",
                           {"provider": "openai"})
    assert ai_service.active_model("openai") == "my-fine-tuned-model"
    assert "Model set" in _sent()[0]


def test_base_url_answer_is_applied(env):
    ai_setup.apply_pending(_msg(text="http://localhost:1234/v1"), "ai_base_url", {})
    assert database.get_str("ai_base_url") == "http://localhost:1234/v1"


# --- base URL prompt ---------------------------------------------------------
def test_base_url_prompt(env, make_call):
    ai_setup.on_callback(make_call(data="ai:base_url"))
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "ai_base_url"
    assert "OpenAI-compatible" in _sent()[0]


def test_custom_provider_screen_shows_the_base_url(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:custom"))
    text = handlers.bot.edit_message_text.call_args.args[0]
    assert "Base URL" in text


# --- disconnect --------------------------------------------------------------
def test_disconnect_asks_for_confirmation(env, make_call):
    ai_setup.on_callback(make_call(data="ai:disconnect"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("confirm:") for entry in data)


# --- close -------------------------------------------------------------------
def test_close_deletes_the_message(env, make_call):
    ai_setup.on_callback(make_call(data="ai:close"))
    handlers.bot.delete_message.assert_called_once_with(OWNER_CHAT, 4242)


# --- connection test ---------------------------------------------------------
def test_run_test_reports_success(env, mocker):
    mocker.patch("services.ai_service.test_connection", return_value=(True, "Connected (1.2s)"))
    ai_setup.run_test(OWNER_CHAT)
    assert any("Connected" in text for text in _sent())


def test_run_test_reports_failure(env, mocker):
    mocker.patch("services.ai_service.test_connection",
                 return_value=(False, "The provider rejected the key"))
    ai_setup.run_test(OWNER_CHAT)
    assert any("rejected the key" in text for text in _sent())


# --- /aimodel ----------------------------------------------------------------
def test_aimodel_sets_a_model(env):
    ai_setup._set_model_from_command(_msg(text="/aimodel gemini-2.5-pro"))
    assert ai_service.active_model("openai") == "gemini-2.5-pro"
    assert "Model set" in _sent()[0]


def test_aimodel_without_argument_shows_usage(env):
    ai_setup._set_model_from_command(_msg(text="/aimodel"))
    assert "Usage" in _sent()[0]


# --- provider registry -------------------------------------------------------
def test_every_provider_has_the_fields_the_ui_needs():
    for provider in providers.ordered():
        assert provider.id and provider.label and provider.kind
        assert provider.kind in ("openai_compat", "anthropic", "codex")
        assert provider.key_required in (True, False)
        if provider.kind == "openai_compat":
            assert provider.base_url or provider.id == "custom"


def test_provider_labels_are_unique():
    labels = [provider.label for provider in providers.ordered()]
    assert len(labels) == len(set(labels))


def test_local_providers_need_no_key():
    for provider_id in ("ollama", "lmstudio"):
        provider = providers.get(provider_id)
        assert provider.key_required is False
        assert provider.base_url.startswith("http://")

# --- OmniRoute (keyless self-hosted gateway) ---------------------------------
def test_omniroute_provider_screen_shows_its_endpoint(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:omniroute"))
    assert database.get_str("ai_provider") == "omniroute"
    text = handlers.bot.edit_message_text.call_args.args[0]
    assert "OmniRoute" in text
    assert "http://localhost:20128/v1" in text
    assert "Send the base URL" not in text


def test_omniroute_menu_offers_an_optional_key(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:omniroute"))
    labels = [b.text for row in handlers.bot.edit_message_text.call_args.kwargs
              ["reply_markup"].keyboard for b in row]
    assert any("optional" in label for label in labels)
    assert "🌐 Set base URL" not in labels


def test_ollama_menu_has_no_key_button(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:ollama"))
    labels = [b.text for row in handlers.bot.edit_message_text.call_args.kwargs
              ["reply_markup"].keyboard for b in row]
    assert not any("key" in label.lower() for label in labels)


def test_omniroute_works_out_of_the_box(db):
    """No key anywhere: the provider is ready as soon as it is selected."""
    assert ai_service.is_ready() is False
    ai_service.set_provider("omniroute")
    assert ai_service.is_ready() is True
    assert ai_service.active_model() == "auto"

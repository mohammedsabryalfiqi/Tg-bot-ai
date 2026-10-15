"""Tests for handlers/ai_setup.py: the in-Telegram provider setup flow (screen
rendering, provider/model switching, the key prompt, validation and deletion)."""

from __future__ import annotations

import pytest

from handlers import ai_setup
from services import ai_service, providers


@pytest.fixture
def env(db, stub_bot, mocker):
    db.set_setting("ai_provider", "openai")
    mocker.patch("services.ai_service.validate_key", return_value=(True, "Connection OK — ok"))
    return db


def _last_message(bot):
    import handlers
    return handlers.bot.send_message.call_args.args[1]


# --- screens -----------------------------------------------------------------
def test_root_screen_lists_provider_and_status(env, make_message):
    import handlers
    ai_setup.open_root(12345)
    text = handlers.bot.send_message.call_args.args[1]
    assert "AI provider" in text
    assert "OpenAI" in text
    assert "not configured" in text  # no key yet


def test_provider_picker_marks_the_active_provider(env, make_call):
    import handlers
    ai_setup.on_callback(make_call(data="ai:providers"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.keyboard for button in row]
    assert any(label.startswith("• ") and "OpenAI" in label for label in labels)
    assert any("Groq" in label for label in labels)


def test_selecting_a_provider_switches_and_shows_its_default_model(env, make_call):
    ai_setup.on_callback(make_call(data="ai:provider:groq"))
    assert env.get_str("ai_provider") == "groq"
    assert ai_service.active_model("groq") == "llama-3.3-70b-versatile"


def test_selecting_an_unknown_provider_is_rejected(env, make_call, stub_bot):
    ai_setup.on_callback(make_call(data="ai:provider:nope"))
    assert env.get_str("ai_provider") == "openai"
    assert "Unknown provider" in stub_bot.answer_callback_query.call_args.kwargs["text"]


def test_model_picker_lists_models(env, make_call):
    import handlers
    ai_setup.on_callback(make_call(data="ai:models"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    labels = [b.text for row in markup.keyboard for b in row]
    assert any("gpt-4.1-mini" in label for label in labels)
    assert any("another model name" in label for label in labels)


def test_choosing_a_model_stores_it(env, make_call):
    ai_setup.on_callback(make_call(data="ai:model:gpt-4o"))
    assert ai_service.active_model("openai") == "gpt-4o"


def test_custom_model_prompt_sets_pending_input(env, make_call):
    ai_setup.on_callback(make_call(data="ai:model_custom"))
    state = env.get_owner_pending_input(12345)
    assert state["kind"] == "ai_model"


def test_key_prompt_sets_pending_input_and_deletes_are_mentioned(env, make_call):
    import handlers
    ai_setup.on_callback(make_call(data="ai:key"))
    assert env.get_owner_pending_input(12345)["kind"] == "ai_key"
    assert "delete the message" in _last_message(None)


def test_base_url_prompt_only_for_custom(env, make_call):
    env.set_setting("ai_provider", "custom")
    ai_setup.on_callback(make_call(data="ai:base_url"))
    assert env.get_owner_pending_input(12345)["kind"] == "ai_base_url"


def test_disconnect_asks_for_confirmation(env, make_call):
    import handlers
    ai_setup.on_callback(make_call(data="ai:disconnect"))
    markup = handlers.bot.edit_message_text.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "confirm:yes:aidisconnect" in data


def test_close_deletes_the_message(env, make_call, stub_bot):
    ai_setup.on_callback(make_call(data="ai:close"))
    stub_bot.delete_message.assert_called_once()


# --- applying pending inputs -------------------------------------------------
def test_applying_a_key_validates_then_stores(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    ai_setup.apply_pending(make_message(text="sk-test-1234567890", message_id=77),
                           "ai_key", {"provider": "openai"})
    assert env.get_owner_pending_input(12345) is None
    assert ai_service.has_api_key("openai") is True


def test_applying_a_key_deletes_the_secret_message(env, make_message, mocker):
    import handlers
    ai_setup.apply_pending(make_message(text="sk-test-1234567890", message_id=77),
                           "ai_key", {"provider": "openai"})
    handlers.bot.delete_message.assert_called_once_with(make_message(text="x").chat.id, 77)


def test_rejected_key_is_not_stored(env, make_message, mocker):
    mocker.patch("services.ai_service.validate_key", return_value=(False, "bad key"))
    ai_setup.apply_pending(make_message(text="sk-wrong-000000"), "ai_key", {"provider": "openai"})
    assert ai_service.has_api_key("openai") is False
    assert "accepted" in _last_message(None)


def test_applying_a_model(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    ai_setup.apply_pending(make_message(text="gemini-2.5-pro"), "ai_model", {"provider": "google"})
    assert ai_service.active_model("google") == "gemini-2.5-pro"


def test_applying_a_base_url(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    ai_setup.apply_pending(make_message(text="http://localhost:1234/v1"), "ai_base_url", {})
    assert env.get_str("ai_base_url") == "http://localhost:1234/v1"


def test_empty_answer_cancels(env, make_message):
    ai_setup.apply_pending(make_message(text="   "), "ai_model", {"provider": "openai"})
    assert "Nothing received" in _last_message(None)


def test_aimodel_command_sets_a_model(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    ai_setup._set_model_from_command(make_message(text="/aimodel claude-3-7-sonnet-latest"))
    assert ai_service.active_model() == "claude-3-7-sonnet-latest"


def test_aimodel_without_argument_shows_the_current_model(env, make_message):
    ai_setup._set_model_from_command(make_message(text="/aimodel"))
    assert "Current model" in _last_message(None)


# --- connection test ---------------------------------------------------------
def test_run_test_reports_success(env, mocker):
    mocker.patch("services.ai_service.test_connection", return_value=(True, "Connection OK (0.4s)"))
    ai_setup.run_test(12345)
    import handlers
    assert "Connection OK" in handlers.bot.send_message.call_args.args[1]


def test_run_test_reports_failure(env, mocker):
    mocker.patch("services.ai_service.test_connection",
                 return_value=(False, "The provider rejected the API key."))
    ai_setup.run_test(12345)
    import handlers
    assert "rejected the API key" in handlers.bot.send_message.call_args.args[1]


# --- registry sanity ---------------------------------------------------------
def test_every_registry_entry_has_required_fields():
    for provider in providers.ordered():
        assert provider.id and provider.label and provider.kind
        if provider.kind != "codex":
            assert provider.base_url or provider.id == "custom"

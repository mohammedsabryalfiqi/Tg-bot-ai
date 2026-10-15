"""AI provider setup from inside Telegram (`/ai`).

Everything the bot needs to generate replies can be configured here — no terminal
editing required:

    /ai -> provider list -> (optional API key) -> model -> test connection

The API key is validated with a live call, then stored encrypted in the DB and
the Telegram message containing it is deleted.
"""

from __future__ import annotations

import logging

import database
import handlers
import keyboards
import security
import telegram_api
import utils
from services import ai_service, providers

log = logging.getLogger("smartel.ai_setup")

PENDING_TTL_MINUTES = 10


def register(bot, cfg) -> None:
    @bot.message_handler(commands=["ai", "ai_setup", "connect_ai", "provider"],
                         func=security.is_owner_msg)
    def _ai(message):
        _safe(lambda: open_root(message.chat.id))

    @bot.message_handler(commands=["aimodel"], func=security.is_owner_msg)
    def _aimodel(message):
        _safe(lambda: _set_model_from_command(message))

    @bot.message_handler(commands=["aitest"], func=security.is_owner_msg)
    def _aitest(message):
        _safe(lambda: run_test(message.chat.id))

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("ai:"))
    @security.owner_only_callback
    def _ai_cb(call):
        _safe(lambda: on_callback(call))


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("ai setup handler failed")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Screens
# =============================================================================
def _status_text() -> str:
    provider = ai_service.active_provider()
    ready = ai_service.is_ready()
    lines = [
        "🤖 <b>AI provider</b>",
        "",
        f"Status: <b>{'ready ✅' if ready else 'not configured ⚠️'}</b>",
    ]
    lines.extend(f"{utils.escape(line)}" for line in ai_service.status_lines())
    if not ready and provider.key_required:
        lines.append("")
        lines.append("Send the API key with the button below, or pick another provider.")
    lines.append("")
    lines.append("Providers with 🆓 offer a usable free tier; 💻 runs on your own computer.")
    return "\n".join(lines)


def open_root(chat_id: int) -> None:
    provider = ai_service.active_provider()
    handlers.bot.send_message(
        chat_id,
        _status_text(),
        parse_mode="HTML",
        reply_markup=keyboards.ai_root(
            has_key=ai_service.has_api_key(provider.id),
            is_ready=ai_service.is_ready(),
            provider_label=provider.label,
        ),
    )


def _edit_or_send(call, text: str, reply_markup=None) -> None:
    """Replace the message the button belongs to when possible."""
    try:
        handlers.bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            parse_mode="HTML", reply_markup=reply_markup,
        )
    except Exception:
        handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                                  reply_markup=reply_markup)


def _provider_detail_text(provider: providers.Provider) -> str:
    lines = [f"<b>{utils.escape(provider.label)}</b>", ""]
    if provider.docs:
        lines.append(utils.escape(provider.docs))
    if provider.key_url:
        lines.append("")
        lines.append(f"🔑 Get a key: {utils.escape(provider.key_url)}")
    source = ai_service.key_source(provider.id)
    if source != "none":
        origin = "from .env (terminal)" if source == "env" else "saved in Telegram"
        lines.append("")
        lines.append(f"Current key: {utils.escape(ai_service.masked_active_key(provider.id))} ({origin})")
    if provider.id == "custom":
        base = ai_service.active_base_url(provider.id) or "(not set)"
        lines.append(f"Base URL: <code>{utils.escape(base)}</code>")
        lines.append("Send the base URL, the model name and (optionally) an API key.")
    lines.append("")
    lines.append(f"Model: <code>{utils.escape(ai_service.active_model(provider.id))}</code>")
    return "\n".join(lines)


def _open_providers(call) -> None:
    _edit_or_send(
        call,
        "🔁 <b>Choose an AI provider</b>\n\n"
        "Your customers' messages are answered by this model. "
        "You can switch any time — nothing else in the bot changes.",
        keyboards.ai_providers(ai_service.active_provider_id()),
    )


def _select_provider(call, provider_id: str) -> None:
    provider = providers.get(provider_id)
    if provider is None:
        return telegram_api.answer_callback(handlers.bot, call.id, "Unknown provider.")
    ai_service.set_provider(provider.id)
    if not ai_service.has_explicit_model(provider.id) and provider.default_model:
        ai_service.set_model(provider.default_model, provider.id)
    telegram_api.answer_callback(handlers.bot, call.id, f"Provider: {provider.label}")
    _edit_or_send(call, _provider_detail_text(provider),
                  keyboards.ai_provider_actions(provider.id, provider.key_required))


def _open_models(call, provider_id: str | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    models = providers.models_for(provider.id)
    if not models:
        return _ask_for_model(call, provider.id)
    _edit_or_send(
        call,
        f"🧠 <b>Model for {utils.escape(provider.label)}</b>\n\n"
        f"Current: <code>{utils.escape(ai_service.active_model(provider.id))}</code>\n"
        "Pick one, or type any model name your account supports.",
        keyboards.ai_models(models, ai_service.active_model(provider.id)),
    )


# =============================================================================
# Callback dispatch
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""

    if action == "root":
        _edit_or_send(call, _status_text(), keyboards.ai_root(
            has_key=ai_service.has_api_key(),
            is_ready=ai_service.is_ready(),
            provider_label=ai_service.active_provider().label,
        ))
        return telegram_api.answer_callback(bot, call.id)

    if action == "providers":
        _open_providers(call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "provider":
        _select_provider(call, arg)
        return

    if action == "models":
        _open_models(call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "model":
        ai_service.set_model(arg)
        telegram_api.answer_callback(bot, call.id, f"Model: {arg}")
        _edit_or_send(call, _status_text(), keyboards.ai_root(
            has_key=ai_service.has_api_key(), is_ready=ai_service.is_ready(),
            provider_label=ai_service.active_provider().label,
        ))
        return

    if action == "model_custom":
        _ask_for_model(call)
        return

    if action == "key":
        _ask_for_key(call)
        return

    if action == "base_url":
        _ask_for_base_url(call)
        return

    if action == "test":
        telegram_api.answer_callback(bot, call.id, "Testing…")
        run_test(call.message.chat.id)
        return

    if action == "disconnect":
        provider = ai_service.active_provider()
        _edit_or_send(
            call,
            f"Remove the stored API key for <b>{utils.escape(provider.label)}</b>?\n"
            "The bot will stop generating replies until a key is added again.",
            keyboards.confirm("aidisconnect"),
        )
        return telegram_api.answer_callback(bot, call.id)

    if action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, "Closed.")

    telegram_api.answer_callback(bot, call.id)


# =============================================================================
# Pending-input prompts (answers arrive via approvals.on_owner_pending_input)
# =============================================================================
def _ask_for_key(call) -> None:
    provider = ai_service.active_provider()
    database.set_owner_pending_input(
        security.owner_id(), "ai_key", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    hint = ""
    if provider.key_url:
        hint = f"\nGet one here: {utils.escape(provider.key_url)}"
    telegram_api.answer_callback(handlers.bot, call.id, "Send the key as your next message.")
    handlers.bot.send_message(
        call.message.chat.id,
        f"🔑 Send the <b>{utils.escape(provider.label)}</b> API key as your next message "
        f"(or /cancel).\n\n<i>I delete the message right after reading it.</i>{hint}",
        parse_mode="HTML",
    )


def _ask_for_model(call, provider_id: str | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    database.set_owner_pending_input(
        security.owner_id(), "ai_model", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    telegram_api.answer_callback(handlers.bot, call.id, "Type the model name.")
    handlers.bot.send_message(
        call.message.chat.id,
        f"🧠 Send the model name for <b>{utils.escape(provider.label)}</b> "
        "(e.g. <code>gpt-4.1-mini</code>, <code>gemini-2.5-flash</code>), or /cancel.",
        parse_mode="HTML",
    )


def _ask_for_base_url(call) -> None:
    database.set_owner_pending_input(security.owner_id(), "ai_base_url", {}, PENDING_TTL_MINUTES)
    telegram_api.answer_callback(handlers.bot, call.id, "Send the base URL.")
    handlers.bot.send_message(
        call.message.chat.id,
        "🌐 Send the base URL of your OpenAI-compatible endpoint "
        "(e.g. <code>http://localhost:1234/v1</code>), or /cancel.",
        parse_mode="HTML",
    )


def _set_model_from_command(message) -> None:
    model = _args(message)
    if not model:
        handlers.bot.send_message(
            message.chat.id,
            f"Current model: <code>{utils.escape(ai_service.active_model_label())}</code>\n"
            "Usage: <code>/aimodel &lt;model-name&gt;</code>",
            parse_mode="HTML",
        )
        return
    ai_service.set_model(model)
    handlers.bot.send_message(
        message.chat.id,
        f"✅ Model set to <code>{utils.escape(model)}</code>. Use /aitest to verify it.",
        parse_mode="HTML",
    )


# =============================================================================
# Applying pending inputs (routed from approvals.on_owner_pending_input)
# =============================================================================
def apply_pending(message, kind: str, context: dict) -> None:
    owner = security.owner_id()
    database.clear_owner_pending_input(owner)
    raw = (getattr(message, "text", "") or "").strip()
    chat_id = message.chat.id
    if not raw:
        return handlers.bot.send_message(chat_id, "Nothing received — cancelled. ✖")

    if kind == "ai_key":
        _apply_key(chat_id, raw, context.get("provider"), message_id=message.message_id)
    elif kind == "ai_model":
        ai_service.set_model(raw, context.get("provider"))
        handlers.bot.send_message(
            chat_id, f"✅ Model set to <code>{utils.escape(raw)}</code>.\n"
                     "Use /aitest to verify.", parse_mode="HTML")
    elif kind == "ai_base_url":
        ai_service.set_base_url(raw)
        handlers.bot.send_message(
            chat_id, f"✅ Base URL saved: <code>{utils.escape(raw)}</code>.\n"
                     "Send the model name next with /aimodel, then /aitest.",
            parse_mode="HTML")


def _apply_key(chat_id: int, key: str, provider_id: str | None = None,
               message_id: int | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    # Delete the message containing the raw secret first thing.
    if message_id is not None:
        try:
            handlers.bot.delete_message(chat_id, message_id)
        except Exception:
            log.debug("could not delete the key message", exc_info=True)
    handlers.bot.send_message(chat_id, f"🔎 Checking the key with {provider.label}…")
    ok, detail = ai_service.validate_key(provider.id, key)
    if not ok:
        return handlers.bot.send_message(
            chat_id,
            f"⚠️ The key was <b>not</b> accepted:\n{utils.escape(detail)}\n\n"
            "Check it and send it again with /ai → “Add / update API key”.",
            parse_mode="HTML",
        )
    ai_service.store_api_key(key, provider.id)
    handlers.bot.send_message(
        chat_id,
        f"✅ <b>{utils.escape(provider.label)}</b> connected.\n"
        f"{utils.escape(detail)}\n\n"
        f"Model: <code>{utils.escape(ai_service.active_model(provider.id))}</code>",
        parse_mode="HTML",
    )
    _send_model_picker(chat_id, provider.id)


def _send_model_picker(chat_id: int, provider_id: str) -> None:
    provider = providers.get_or_default(provider_id)
    models = providers.models_for(provider.id)
    if not models:
        return
    handlers.bot.send_message(
        chat_id,
        f"🧠 Choose a model for {utils.escape(provider.label)} "
        f"(current: <code>{utils.escape(ai_service.active_model(provider.id))}</code>):",
        parse_mode="HTML",
        reply_markup=keyboards.ai_models(models, ai_service.active_model(provider.id)),
    )


# =============================================================================
# Connection test
# =============================================================================
def run_test(chat_id: int) -> None:
    handlers.bot.send_message(chat_id, "🧪 Testing the connection (may take a few seconds)…")
    ok, detail = ai_service.test_connection()
    icon = "✅" if ok else "⚠️"
    handlers.bot.send_message(chat_id, f"{icon} {utils.escape(detail)}\n\n" +
                              "\n".join(utils.escape(line) for line in ai_service.status_lines()))

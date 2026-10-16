"""AI provider setup from inside Telegram (`/ai`, `/freeai`).

Everything the bot needs to generate replies can be configured here — no terminal
editing required:

    /ai       -> provider list -> (optional API key) -> model -> test connection
    /freeai   -> only the providers that cost nothing (no credit card, no balance)

The API key is validated with a live call, then stored encrypted in the DB and
the Telegram message containing it is deleted. When validation fails the owner
gets the *reason* (wrong key / no credit / unknown model / rate limit / region)
with the exact fix, plus one-tap buttons that switch to a free provider — the
most common dead end is a paid key with no balance behind it.
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
                         func=security.is_operator_msg)
    def _ai(message):
        security.run_as_operator(message, lambda: _safe(lambda: open_root(message.chat.id)))

    @bot.message_handler(commands=["aimodel"], func=security.is_primary_admin_msg)
    def _aimodel(message):
        security.run_as_operator(message, lambda: _safe(lambda: _set_model_from_command(message)))

    @bot.message_handler(commands=["aitest"], func=security.is_operator_msg)
    def _aitest(message):
        security.run_as_operator(message, lambda: _safe(lambda: run_test(message.chat.id)))

    @bot.message_handler(commands=["freeai", "free_ai", "freeproviders", "free_providers"],
                         func=security.is_primary_admin_msg)
    def _freeai(message):
        security.run_as_operator(message, lambda: _safe(lambda: open_free(message.chat.id)))

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
    primary_admin = security.is_primary_admin(security.operator_id())
    if not ready and provider.key_required:
        lines.append("")
        lines.append("Send your API key with the button below.")
        if primary_admin:
            lines[-1] = "Send the API key with the button below, or choose another provider."
    if not primary_admin:
        lines.append("\nOnly the primary admin can change the AI provider/model.")
    lines.append("")
    if primary_admin:
        lines.append("Providers with 🆓 offer a usable free tier; 💻 runs on your own computer.")
    else:
        lines.append("The primary admin chooses the provider/model; this account manages its own key.")
    if primary_admin and (not ready or providers.needs_credit(provider.id)):
        lines.append("💡 No credit card / no balance? Send /freeai for the providers "
                     "that cost nothing.")
    return "\n".join(lines)


def _root_markup() -> keyboards.types.InlineKeyboardMarkup:
    provider = ai_service.active_provider()
    return keyboards.ai_root(
        has_key=ai_service.has_api_key(provider.id),
        is_ready=ai_service.is_ready(),
        provider_label=provider.label,
        primary_admin=security.is_primary_admin(security.operator_id()),
    )


def open_root(chat_id: int) -> None:
    provider = ai_service.active_provider()
    handlers.bot.send_message(
        chat_id,
        _status_text(),
        parse_mode="HTML",
        reply_markup=_root_markup(),
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
    elif provider.base_url:
        base = ai_service.active_base_url(provider.id) or "(not set)"
        lines.append("")
        lines.append(f"Endpoint: <code>{utils.escape(base)}</code>")
        if provider.local:
            lines.append("<i>Must be reachable from the machine running the bot.</i>")
    lines.append("")
    lines.append(f"Model: <code>{utils.escape(ai_service.active_model(provider.id))}</code>")
    lines.append(f"Cost: {utils.escape(ai_service.cost_label(provider))}")
    if not providers.is_free(provider):
        lines.append("")
        lines.append("💡 This provider needs paid credit. /freeai lists the free ones.")
    return "\n".join(lines)


def _open_providers(call, free_only: bool = False) -> None:
    if free_only:
        text = (
            "🆓 <b>Free AI providers</b>\n\n"
            "No credit card and no balance needed. Tap one and the bot switches to "
            "it, then asks for its key (a couple of these need no key at all)."
        )
    else:
        text = (
            "🔁 <b>Choose an AI provider</b>\n\n"
            "Your customers' messages are answered by this model. "
            "You can switch any time — nothing else in the bot changes."
        )
    _edit_or_send(call, text,
                  keyboards.ai_providers(ai_service.active_provider_id(), free_only=free_only))


def open_free(chat_id: int) -> None:
    """`/freeai` — the zero-cost shortlist, with each provider's real limits."""
    active_id = ai_service.active_provider_id()
    lines = ["🆓 <b>AI providers that cost nothing</b>", "",
             "No credit card, no balance top-up. Pick one, get a key, tap it here:", ""]
    for provider in providers.free():
        tag = "💻" if provider.local else "🆓"
        name = provider.label + ("  ← active now" if provider.id == active_id else "")
        lines.append(f"{tag} <b>{utils.escape(name)}</b>")
        note = provider.free_note or provider.docs
        if note:
            lines.append(f"    {utils.escape(note)}")
        if provider.key_url:
            lines.append(f"    🔑 {utils.escape(provider.key_url)}")
        elif not provider.key_required:
            lines.append("    🔑 No API key needed")
        lines.append("")
    lines += [
        "<b>Which one?</b>",
        "• Easiest + most generous: <b>Google Gemini</b> (a Google account is enough).",
        "• Fastest: <b>Groq</b> or <b>Cerebras</b>.",
        "• Many models with one key: <b>OpenRouter</b> (use a model ending in "
        "<code>:free</code>).",
        "• No signup at all: <b>Pollinations</b> — but it is slow and best effort.",
        "• No internet / total privacy: <b>Ollama</b> or <b>LM Studio</b> on your PC.",
        "",
        "Free tiers are rate limited (per minute / per day) and reset on their own. "
        "After switching, press 🧪 Test connection — and if a model name is refused, "
        "use 🔄 Load models to see what your key can run.",
    ]
    text = "\n".join(lines)
    markup = keyboards.ai_providers(active_id, free_only=True)
    for i, chunk in enumerate(utils.split_message(text)):
        handlers.bot.send_message(chat_id, chunk, parse_mode="HTML",
                                  reply_markup=markup if i == 0 else None)


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
    # Model names may contain ":" (OpenRouter's ":free" suffix), so keep the rest.
    arg = ":".join(parts[2:]) if len(parts) > 2 else ""

    # Delegated admins can configure their own secret for the model selected by
    # the primary admin, but cannot switch providers/models or alter the catalog.
    allowed_for_delegate = {"root", "key", "test", "disconnect", "close"}
    if (not security.is_primary_admin(getattr(getattr(call, "from_user", None), "id", None))
            and action not in allowed_for_delegate):
        return telegram_api.answer_callback(
            bot, call.id, "Only the primary admin can change the AI provider or model.",
            show_alert=True,
        )

    if action == "root":
        _edit_or_send(call, _status_text(), _root_markup())
        return telegram_api.answer_callback(bot, call.id)

    if action == "providers":
        _open_providers(call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "providers_free":
        _open_providers(call, free_only=True)
        return telegram_api.answer_callback(bot, call.id)

    if action == "provider":
        _select_provider(call, arg)
        return

    if action == "freeswitch":
        _free_switch(call, arg)
        return

    if action == "models_live":
        load_live_models(call.message.chat.id, call=call)
        return

    if action == "models":
        _open_models(call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "model":
        ai_service.set_model(arg)
        telegram_api.answer_callback(bot, call.id, f"Model: {arg}")
        _edit_or_send(call, _status_text(), _root_markup())
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
    telegram_api.answer_callback(handlers.bot, call.id, "Send the key as your next message.")
    prompt_for_key(call.message.chat.id, ai_service.active_provider())


def prompt_for_key(chat_id: int, provider: providers.Provider) -> None:
    """Park the conversation and ask for this provider's API key."""
    database.set_owner_pending_input(
        security.operator_id(), "ai_key", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    hint = ""
    if provider.key_url:
        hint = (f"\n\n🔑 Get one here: {utils.escape(provider.key_url)}"
                + ("  (free — no credit card)" if provider.free_tier else ""))
    handlers.bot.send_message(
        chat_id,
        f"🔑 Send the <b>{utils.escape(provider.label)}</b> API key as your next message "
        f"(or /cancel).\n\n<i>I delete the message right after reading it.</i>{hint}",
        parse_mode="HTML",
    )


def _free_switch(call, provider_id: str) -> None:
    """One tap: move to a free provider and immediately ask for its key."""
    provider = providers.get(provider_id)
    if provider is None:
        return telegram_api.answer_callback(handlers.bot, call.id, "Unknown provider.")
    ai_service.set_provider(provider.id)
    if not ai_service.has_explicit_model(provider.id) and provider.default_model:
        ai_service.set_model(provider.default_model, provider.id)
    telegram_api.answer_callback(handlers.bot, call.id, f"Switched to {provider.label}")
    _edit_or_send(call, _provider_detail_text(provider),
                  keyboards.ai_provider_actions(provider.id, provider.key_required))
    chat_id = call.message.chat.id
    if provider.key_required:
        prompt_for_key(chat_id, provider)
    else:
        handlers.bot.send_message(chat_id, f"✅ <b>{utils.escape(provider.label)}</b> needs no "
                                           "API key. Testing it now…", parse_mode="HTML")
        run_test(chat_id)


def _ask_for_model(call, provider_id: str | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    database.set_owner_pending_input(
        security.operator_id(), "ai_model", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    telegram_api.answer_callback(handlers.bot, call.id, "Type the model name.")
    handlers.bot.send_message(
        call.message.chat.id,
        f"🧠 Send the model name for <b>{utils.escape(provider.label)}</b> "
        "(e.g. <code>gpt-4.1-mini</code>, <code>gemini-2.5-flash</code>), or /cancel.",
        parse_mode="HTML",
    )


def _ask_for_base_url(call) -> None:
    database.set_owner_pending_input(security.operator_id(), "ai_base_url", {}, PENDING_TTL_MINUTES)
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
    owner = security.operator_id()
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
    result = ai_service.check_key(provider.id, key)
    if not result.ok:
        handlers.bot.send_message(
            chat_id,
            _failure_text(result, f"⚠️ <b>{utils.escape(provider.label)}</b> did not accept "
                                  "this key"),
            parse_mode="HTML",
            reply_markup=keyboards.ai_free_switch(result.suggestions) if result.suggestions else None,
        )
        return
    ai_service.store_api_key(key, provider.id)
    handlers.bot.send_message(
        chat_id,
        f"✅ <b>{utils.escape(provider.label)}</b> connected.\n"
        f"{utils.escape(result.message)}\n\n"
        f"Model: <code>{utils.escape(ai_service.active_model(provider.id))}</code>",
        parse_mode="HTML",
    )
    _send_model_picker(chat_id, provider.id)


def _failure_text(result, title: str) -> str:
    """Owner-facing failure card: what happened, then how to fix it."""
    lines = [title, "", utils.escape(result.message)]
    if result.hints:
        lines += ["", "<b>How to fix it</b>"]
        lines += [f"• {utils.escape(hint)}" for hint in result.hints]
    if result.suggestions:
        names = ", ".join(p.label for p in result.suggestions)
        lines += ["", f"Or switch to a free provider in one tap 👇 ({utils.escape(names)})"]
    return "\n".join(lines)


def load_live_models(chat_id: int, *, call=None, provider_id: str | None = None) -> None:
    """Fetch the real model catalogue for the stored key (fixes wrong model names)."""
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    if call is not None:
        telegram_api.answer_callback(handlers.bot, call.id, "Loading models…")
    handlers.bot.send_message(
        chat_id, f"🔄 Asking <b>{utils.escape(provider.label)}</b> which models your "
                 "key can use…", parse_mode="HTML")
    try:
        models = ai_service.list_models(provider.id)
    except ai_service.AIServiceError as e:
        lines = [f"⚠️ {utils.escape(e.owner_message)}"]
        lines += [f"• {utils.escape(hint)}" for hint in e.hints]
        lines.append("You can still type a model name: /aimodel &lt;name&gt;")
        return handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    current = ai_service.active_model(provider.id)
    if not models:
        return handlers.bot.send_message(
            chat_id,
            f"{utils.escape(provider.label)} did not return a model list. Type the name "
            "instead: /aimodel &lt;name&gt;", parse_mode="HTML")
    handlers.bot.send_message(
        chat_id,
        f"🧠 <b>{len(models)} models</b> your key can run on "
        f"{utils.escape(provider.label)}\nCurrent: <code>{utils.escape(current)}</code>\n"
        "Tap one to use it:",
        parse_mode="HTML",
        reply_markup=keyboards.ai_models(models, current, can_refresh=False),
    )


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
    result = ai_service.check_connection()
    if result.ok:
        handlers.bot.send_message(
            chat_id,
            f"✅ {utils.escape(result.message)}\n\n" +
            "\n".join(utils.escape(line) for line in ai_service.status_lines()),
            parse_mode="HTML",
        )
        return
    handlers.bot.send_message(
        chat_id,
        _failure_text(result, "⚠️ <b>The test failed</b>") + "\n\n" +
        "\n".join(utils.escape(line) for line in ai_service.status_lines()),
        parse_mode="HTML",
        reply_markup=keyboards.ai_free_switch(result.suggestions) if result.suggestions else None,
    )

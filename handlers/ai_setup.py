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
import i18n
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
        i18n.t("ai.title"),
        "",
        i18n.t("ai.status", state=i18n.t("own.ai.ready") if ready
               else i18n.t("own.ai.not_ready_short")),
    ]
    lines.extend(f"{utils.escape(line)}" for line in ai_service.status_lines())
    primary_admin = security.is_primary_admin(security.operator_id())
    if not ready and provider.key_required:
        lines.append("")
        lines.append(i18n.t("ai.send_key_hint") if not primary_admin
                     else i18n.t("ai.send_key_hint_or_pick"))
    if not primary_admin:
        lines.append(i18n.t("ai.primary_only_note"))
    lines.append("")
    if primary_admin:
        lines.append(i18n.t("ai.legend"))
    else:
        lines.append(i18n.t("ai.delegate_note"))
    if primary_admin and (not ready or providers.needs_credit(provider.id)):
        lines.append(i18n.t("ai.freeai_hint"))
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
        lines.append(i18n.t("ai.get_key", url=utils.escape(provider.key_url)))
    source = ai_service.key_source(provider.id)
    if source != "none":
        origin = (i18n.t("ai.key_source.shared") if source == "shared" else
                  i18n.t("ai.key_source.env") if source == "env" else
                  i18n.t("ai.key_source.telegram"))
        lines.append("")
        lines.append(i18n.t("ai.current_key",
                            masked=utils.escape(ai_service.masked_active_key(provider.id)),
                            origin=origin))
    if provider.id == "custom":
        base = ai_service.active_base_url(provider.id) or i18n.t("ai.not_set")
        lines.append(i18n.t("ai.base_url", base=utils.escape(base)))
        lines.append(i18n.t("ai.custom_hint"))
    elif provider.base_url:
        base = ai_service.active_base_url(provider.id) or i18n.t("ai.not_set")
        lines.append("")
        lines.append(i18n.t("ai.endpoint", base=utils.escape(base)))
        if provider.local:
            lines.append(i18n.t("ai.local_note"))
    lines.append("")
    lines.append(i18n.t("ai.model_line",
                        model=utils.escape(ai_service.active_model(provider.id))))
    lines.append(i18n.t("ai.cost_line", cost=utils.escape(ai_service.cost_label(provider))))
    if not providers.is_free(provider):
        lines.append("")
        lines.append(i18n.t("ai.needs_credit"))
    return "\n".join(lines)


def _open_providers(call, free_only: bool = False) -> None:
    text = i18n.t("ai.providers.free_title") if free_only \
        else i18n.t("ai.providers.title")
    _edit_or_send(call, text,
                  keyboards.ai_providers(ai_service.active_provider_id(), free_only=free_only))


def open_free(chat_id: int) -> None:
    """`/freeai` — the zero-cost shortlist, with each provider's real limits."""
    active_id = ai_service.active_provider_id()
    lines = [i18n.t("ai.free.title"), "", i18n.t("ai.free.intro"), ""]
    for provider in providers.free():
        tag = "💻" if provider.local else "🆓"
        name = provider.label + (i18n.t("ai.free.active") if provider.id == active_id else "")
        lines.append(f"{tag} <b>{utils.escape(name)}</b>")
        note = provider.free_note or provider.docs
        if note:
            lines.append(f"    {utils.escape(note)}")
        if provider.key_url:
            lines.append(f"    🔑 {utils.escape(provider.key_url)}")
        elif not provider.key_required:
            lines.append(i18n.t("ai.free.no_key_needed"))
        lines.append("")
    lines.append(i18n.t("ai.free.which"))
    text = "\n".join(lines)
    markup = keyboards.ai_providers(active_id, free_only=True)
    for i, chunk in enumerate(utils.split_message(text)):
        handlers.bot.send_message(chat_id, chunk, parse_mode="HTML",
                                  reply_markup=markup if i == 0 else None)


def _select_provider(call, provider_id: str) -> None:
    provider = providers.get(provider_id)
    if provider is None:
        return telegram_api.answer_callback(handlers.bot, call.id, i18n.t("ai.unknown_provider"))
    ai_service.set_provider(provider.id)
    if not ai_service.has_explicit_model(provider.id) and provider.default_model:
        ai_service.set_model(provider.default_model, provider.id)
    telegram_api.answer_callback(handlers.bot, call.id,
                                 i18n.t("ai.provider_set", label=provider.label))
    _edit_or_send(call, _provider_detail_text(provider),
                  keyboards.ai_provider_actions(provider.id, provider.key_required))


def _open_models(call, provider_id: str | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    models = providers.models_for(provider.id)
    if not models:
        return _ask_for_model(call, provider.id)
    _edit_or_send(
        call,
        i18n.t("ai.models.title", label=utils.escape(provider.label),
               current=utils.escape(ai_service.active_model(provider.id))),
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
            bot, call.id, i18n.t("ai.primary_only_cb"), show_alert=True,
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
        telegram_api.answer_callback(bot, call.id, i18n.t("ai.model_set_cb", model=arg))
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
        telegram_api.answer_callback(bot, call.id, i18n.t("ai.testing"))
        run_test(call.message.chat.id)
        return

    if action == "disconnect":
        provider = ai_service.active_provider()
        _edit_or_send(
            call,
            i18n.t("ai.remove_key_ask", label=utils.escape(provider.label)),
            keyboards.confirm("aidisconnect"),
        )
        return telegram_api.answer_callback(bot, call.id)

    if action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


# =============================================================================
# Pending-input prompts (answers arrive via approvals.on_owner_pending_input)
# =============================================================================
def _ask_for_key(call) -> None:
    telegram_api.answer_callback(handlers.bot, call.id, i18n.t("ai.ask_key_cb"))
    prompt_for_key(call.message.chat.id, ai_service.active_provider())


def prompt_for_key(chat_id: int, provider: providers.Provider) -> None:
    """Park the conversation and ask for this provider's API key."""
    database.set_owner_pending_input(
        security.operator_id(), "ai_key", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    hint = ""
    if provider.key_url:
        hint = (i18n.t("ai.key_url_hint", url=utils.escape(provider.key_url))
                + (i18n.t("ai.key_url_free") if provider.free_tier else ""))
    handlers.bot.send_message(
        chat_id,
        i18n.t("ai.ask_key", label=utils.escape(provider.label), hint=hint),
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
    telegram_api.answer_callback(handlers.bot, call.id,
                                 i18n.t("ai.switched", label=provider.label))
    _edit_or_send(call, _provider_detail_text(provider),
                  keyboards.ai_provider_actions(provider.id, provider.key_required))
    chat_id = call.message.chat.id
    if provider.key_required:
        prompt_for_key(chat_id, provider)
    else:
        handlers.bot.send_message(
            chat_id, i18n.t("ai.no_key_needed_test", label=utils.escape(provider.label)),
            parse_mode="HTML")
        run_test(chat_id)


def _ask_for_model(call, provider_id: str | None = None) -> None:
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    database.set_owner_pending_input(
        security.operator_id(), "ai_model", {"provider": provider.id}, PENDING_TTL_MINUTES
    )
    telegram_api.answer_callback(handlers.bot, call.id, i18n.t("ai.ask_model_cb"))
    handlers.bot.send_message(
        call.message.chat.id, i18n.t("ai.ask_model", label=utils.escape(provider.label)),
        parse_mode="HTML",
    )


def _ask_for_base_url(call) -> None:
    database.set_owner_pending_input(security.operator_id(), "ai_base_url", {}, PENDING_TTL_MINUTES)
    telegram_api.answer_callback(handlers.bot, call.id, i18n.t("ai.ask_base_url_cb"))
    handlers.bot.send_message(call.message.chat.id, i18n.t("ai.ask_base_url"),
                              parse_mode="HTML")


def _set_model_from_command(message) -> None:
    model = _args(message)
    if not model:
        handlers.bot.send_message(
            message.chat.id,
            i18n.t("ai.aimodel.usage", model=utils.escape(ai_service.active_model_label())),
            parse_mode="HTML",
        )
        return
    ai_service.set_model(model)
    handlers.bot.send_message(
        message.chat.id, i18n.t("ai.aimodel.set", model=utils.escape(model)),
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
        return handlers.bot.send_message(chat_id, i18n.t("ai.pending.nothing"))

    if kind == "ai_key":
        _apply_key(chat_id, raw, context.get("provider"), message_id=message.message_id)
    elif kind == "ai_model":
        ai_service.set_model(raw, context.get("provider"))
        handlers.bot.send_message(
            chat_id, i18n.t("ai.pending.model_set", model=utils.escape(raw)),
            parse_mode="HTML")
    elif kind == "ai_base_url":
        ai_service.set_base_url(raw)
        handlers.bot.send_message(
            chat_id, i18n.t("ai.pending.base_url_set", url=utils.escape(raw)),
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
    handlers.bot.send_message(chat_id, i18n.t("ai.checking_key", label=provider.label))
    result = ai_service.check_key(provider.id, key)
    if not result.ok:
        handlers.bot.send_message(
            chat_id,
            _failure_text(result, i18n.t("ai.key_rejected",
                                         label=utils.escape(provider.label))),
            parse_mode="HTML",
            reply_markup=keyboards.ai_free_switch(result.suggestions) if result.suggestions else None,
        )
        return
    ai_service.store_api_key(key, provider.id)
    handlers.bot.send_message(
        chat_id,
        i18n.t("ai.connected", label=utils.escape(provider.label),
               message=utils.escape(result.message),
               model=utils.escape(ai_service.active_model(provider.id))),
        parse_mode="HTML",
    )
    _send_model_picker(chat_id, provider.id)


def _failure_text(result, title: str) -> str:
    """Owner-facing failure card: what happened, then how to fix it."""
    lines = [title, "", utils.escape(result.message)]
    if result.hints:
        lines += ["", i18n.t("ai.how_to_fix")]
        lines += [f"• {utils.escape(hint)}" for hint in result.hints]
    if result.suggestions:
        names = ", ".join(p.label for p in result.suggestions)
        lines += ["", i18n.t("ai.switch_hint", names=utils.escape(names))]
    return "\n".join(lines)


def load_live_models(chat_id: int, *, call=None, provider_id: str | None = None) -> None:
    """Fetch the real model catalogue for the stored key (fixes wrong model names)."""
    provider = providers.get_or_default(provider_id or ai_service.active_provider_id())
    if call is not None:
        telegram_api.answer_callback(handlers.bot, call.id, i18n.t("ai.loading_models"))
    handlers.bot.send_message(
        chat_id, i18n.t("ai.asking_models", label=utils.escape(provider.label)),
        parse_mode="HTML")
    try:
        models = ai_service.list_models(provider.id)
    except ai_service.AIServiceError as e:
        lines = [f"⚠️ {utils.escape(e.owner_message)}"]
        lines += [f"• {utils.escape(hint)}" for hint in e.hints]
        lines.append(i18n.t("ai.still_type_model"))
        return handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    current = ai_service.active_model(provider.id)
    if not models:
        return handlers.bot.send_message(
            chat_id, i18n.t("ai.no_model_list", label=utils.escape(provider.label)),
            parse_mode="HTML")
    handlers.bot.send_message(
        chat_id,
        i18n.t("ai.models_found", count=len(models),
               label=utils.escape(provider.label), current=utils.escape(current)),
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
        i18n.t("ai.choose_model", label=utils.escape(provider.label),
               current=utils.escape(ai_service.active_model(provider.id))),
        parse_mode="HTML",
        reply_markup=keyboards.ai_models(models, ai_service.active_model(provider.id)),
    )


# =============================================================================
# Connection test
# =============================================================================
def run_test(chat_id: int) -> None:
    handlers.bot.send_message(chat_id, i18n.t("ai.testing_msg"))
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
        _failure_text(result, i18n.t("ai.test_failed")) + "\n\n" +
        "\n".join(utils.escape(line) for line in ai_service.status_lines()),
        parse_mode="HTML",
        reply_markup=keyboards.ai_free_switch(result.suggestions) if result.suggestions else None,
    )

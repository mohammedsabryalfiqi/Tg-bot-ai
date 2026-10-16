"""Owner commands, the /start control panel, status/help, toggles, pause/resume,
confirmations and the catch-all fallback handler.

Only the configured owner can use these (``func=security.is_owner_msg``). Until
an owner is claimed (see ``security.py``) the bot answers only the claim code
printed by the terminal at startup.
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
from handlers import approvals
from services import ai_service, business_service, faq_service, memory_service, providers

log = logging.getLogger("smartel.owner")

_FALLBACK_CONTENT = ["text", "document", "photo", "voice", "audio", "video", "sticker"]


def register(bot, cfg) -> None:
    def cmd(commands):
        def deco(fn):
            bot.message_handler(commands=commands, func=security.is_operator_msg)(
                lambda message, _fn=fn: security.run_as_operator(
                    message, lambda: _safe(lambda: _fn(message)))
            )
            return fn
        return deco

    cmd(["start"])(cmd_start)
    cmd(["help"])(cmd_help)
    cmd(["status"])(cmd_status)
    cmd(["settings"])(cmd_settings)
    # Legacy OpenAI-era commands now route to the provider-agnostic /ai screen.
    cmd(["connect_openai"])(cmd_connect_openai)
    cmd(["disconnect_openai"])(cmd_disconnect_openai)
    cmd(["auto_on"])(lambda m: _set_toggle(m, "auto_reply_enabled", True,
                                           i18n.t("own.label.auto")))
    cmd(["auto_off"])(lambda m: _set_toggle(m, "auto_reply_enabled", False,
                                            i18n.t("own.label.auto")))
    cmd(["approval_on"])(lambda m: _set_toggle(m, "approval_mode_enabled", True,
                                               i18n.t("own.label.approval")))
    cmd(["approval_off"])(lambda m: _set_toggle(m, "approval_mode_enabled", False,
                                                i18n.t("own.label.approval")))
    cmd(["memory_clear"])(cmd_memory_clear)
    cmd(["pause_chat"])(cmd_pause_chat)
    cmd(["resume_chat"])(cmd_resume_chat)
    cmd(["reset"])(cmd_reset)
    cmd(["cancel"])(cmd_cancel)
    cmd(["instructions"])(cmd_instructions)
    cmd(["setup"])(cmd_setup)
    cmd(["connections"])(cmd_connections)
    cmd(["direct"])(cmd_direct)
    cmd(["language", "lang"])(cmd_language)

    # The primary owner alone controls delegated administrator accounts.
    bot.message_handler(commands=["admin"], func=security.is_primary_admin_msg)(
        lambda message: _safe(lambda: cmd_admin(message))
    )

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("panel:"))
    @security.owner_only_callback
    def _panel(call):
        _safe(lambda: on_panel_callback(call))

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("confirm:"))
    @security.owner_only_callback
    def _confirm(call):
        _safe(lambda: on_confirm_callback(call))


def register_fallback(bot, cfg) -> None:
    """The catch-all message handler. MUST be registered last."""
    @bot.message_handler(func=lambda m: True, content_types=_FALLBACK_CONTENT)
    def _fallback(message):
        if security.is_operator_msg(message):
            security.run_as_operator(message, lambda: _safe(lambda: on_fallback(message)))
        else:
            _safe(lambda: on_fallback(message))


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("owner command failed")


def _args(message) -> str:
    text = getattr(message, "text", "") or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def cmd_admin(message) -> None:
    """Primary-owner management of delegated admin identities.

    /admin <user_id> adds an administrator; /admin remove <user_id> removes
    one; /admin list lists delegates. Tenant access is activated separately
    only after the user links a Telegram Business account with the same ID.
    """
    parts = _args(message).split()
    if not parts:
        handlers.bot.send_message(message.chat.id, i18n.t("own.admin.usage"))
        return
    if parts[0].lower() == "list" and len(parts) == 1:
        admins = database.list_assistant_admins()
        body = ("\n".join(f"• <code>{uid}</code>" for uid in admins)
                or i18n.t("own.admin.list_none"))
        handlers.bot.send_message(
            message.chat.id, i18n.t("own.admin.list_title") + "\n" + body
        )
        return
    remove = parts[0].lower() == "remove"
    raw_id = parts[1] if remove and len(parts) == 2 else (parts[0] if len(parts) == 1 else "")
    try:
        user_id = int(raw_id)
        if user_id <= 0:
            raise ValueError
    except ValueError:
        handlers.bot.send_message(message.chat.id, i18n.t("own.admin.bad_id"))
        return
    if remove and (security.is_owner(user_id) or security.is_primary_admin(user_id)):
        handlers.bot.send_message(message.chat.id, i18n.t("own.admin.primary_kept"))
        return
    changed = (database.remove_assistant_admin(user_id) if remove
               else database.add_assistant_admin(user_id))
    verb = i18n.t("own.admin.removed") if remove else i18n.t("own.admin.added")
    if not changed:
        handlers.bot.send_message(
            message.chat.id, i18n.t("own.admin.not_changed", user_id=user_id, verb=verb)
        )
        return
    handlers.bot.send_message(
        message.chat.id, i18n.t("own.admin.changed", user_id=user_id, verb=verb)
    )


def _current_mode() -> str:
    if not database.get_bool("auto_reply_enabled"):
        return "off"
    return "draft" if database.get_bool("approval_mode_enabled") else "auto"


# =============================================================================
# Commands
# =============================================================================
def cmd_start(message) -> None:
    handlers.bot.send_message(
        message.chat.id,
        i18n.t(
            "own.start",
            mode=_current_mode(),
            backend=utils.escape(ai_service.backend_label()),
            ai_state=i18n.t("own.ai.ready") if ai_service.is_ready()
            else i18n.t("own.ai.not_ready"),
        ),
        parse_mode="HTML",
        reply_markup=keyboards.control_panel(
            database.get_bool("auto_reply_enabled"),
            database.get_bool("approval_mode_enabled"),
            _current_mode(),
        ),
    )


def help_text() -> str:
    """The full usage guide (localised)."""
    return i18n.t("own.help")


def cmd_help(message) -> None:
    handlers.bot.send_message(message.chat.id, help_text(), parse_mode="HTML")


def cmd_status(message) -> None:
    handlers.bot.send_message(message.chat.id, _status_text(), parse_mode="HTML")


def _status_text() -> str:
    st = business_service.get_status()
    mode = _current_mode()
    provider = ai_service.active_provider()
    lines = [i18n.t("own.status.title"), ""]
    lines.append(i18n.t("own.status.reply_mode", mode=mode))
    lines.append(i18n.t(
        "own.status.switches",
        auto="ON" if st["auto_reply_enabled"] else "OFF",
        approval="ON" if st["approval_mode_enabled"] else "OFF",
    ))
    lines.append(i18n.t(
        "own.status.ai",
        state=i18n.t("own.ai.ready") if ai_service.is_ready()
        else i18n.t("own.ai.not_ready_short"),
    ))
    for line in ai_service.status_lines():
        lines.append(f"   {utils.escape(line)}")
    if provider.key_url and not ai_service.has_api_key(provider.id) and provider.key_required:
        lines.append(i18n.t("own.status.key_url", url=utils.escape(provider.key_url)))
    if not ai_service.is_ready() or providers.needs_credit(provider.id):
        lines.append(i18n.t("own.status.freeai_hint"))
    lines.append("")
    lines.append(i18n.t(
        "own.status.direct",
        state=i18n.t("own.status.direct_on") if st["direct_reply_enabled"]
        else i18n.t("own.status.direct_off"),
    ))
    lines.append(i18n.t("own.status.direct_hint"))
    lines.append("")
    conns = st["connections"]
    if not conns:
        lines.append(i18n.t("own.status.conn_none"))
    else:
        lines.append(i18n.t("own.status.conn_count", count=len(conns)))
        for c in conns:
            lines.append(i18n.t(
                "own.status.conn_row",
                owner=utils.escape(c["business_user_id"]),
                state=i18n.t("own.status.conn_enabled") if c["is_enabled"]
                else i18n.t("own.status.conn_disabled"),
                reply=i18n.t("own.status.conn_can_reply") if c["can_reply"]
                else i18n.t("own.status.conn_read_only"),
            ))
    lines.append("")
    lines.append(i18n.t("own.status.paused", count=st["paused_count"]))
    lines.append(i18n.t("own.status.pending", count=st["pending_approvals"]))
    lines.append(i18n.t("own.status.kb", items=st["kb"]["items"], chunks=st["kb"]["chunks"]))
    lines.append(i18n.t("own.status.faq", count=faq_service.count()))
    lines.append("")
    lines.append(i18n.t("own.status.health_hint"))
    return "\n".join(lines)


def cmd_settings(message) -> None:
    from handlers import settings as settings_handler
    settings_handler.open_root(message)


def cmd_setup(message) -> None:
    from handlers import setup_guide
    setup_guide.send_checklist(message.chat.id)


def cmd_direct(message) -> None:
    """Toggle answering the private messages people send to the bot itself."""
    from handlers import owner_tools
    arg = _args(message).lower()
    if arg in ("on", "off"):
        database.set_setting("direct_reply_enabled", arg == "on")
    elif arg not in ("", "status"):
        state = i18n.t("own.direct.on_word") if database.get_bool("direct_reply_enabled") \
            else i18n.t("own.direct.off_word")
        return handlers.bot.send_message(
            message.chat.id, i18n.t("own.direct.usage", state=state), parse_mode="HTML")

    enabled = database.get_bool("direct_reply_enabled")
    text = i18n.t("own.direct.on" if enabled else "own.direct.off")
    text += i18n.t("own.direct.now", mode=owner_tools.current_mode())
    text += i18n.t("own.direct.hint",
                   opposite=i18n.t("own.direct.off_word") if enabled
                   else i18n.t("own.direct.on_word"),
                   command="off" if enabled else "on")
    handlers.bot.send_message(message.chat.id, text, parse_mode="HTML")


def cmd_language(message) -> None:
    """Show/switch the interface language (Arabic by default)."""
    arg = _args(message).lower()
    if arg in i18n.LANGUAGES:
        code = i18n.set_language(arg)
        _republish_commands()
        return handlers.bot.send_message(
            message.chat.id, i18n.t("own.language.title",
                                    label=i18n.LANGUAGES[code]),
            parse_mode="HTML", reply_markup=keyboards.language_menu(code))
    current = i18n.language()
    handlers.bot.send_message(
        message.chat.id, i18n.t("own.language.title", label=i18n.LANGUAGES[current]),
        parse_mode="HTML", reply_markup=keyboards.language_menu(current))


def _republish_commands() -> None:
    """Re-publish the Telegram command menu after a language change."""
    try:
        import main
        main.set_bot_commands(handlers.bot)
    except Exception:
        log.debug("could not re-publish bot commands", exc_info=True)


def cmd_connections(message) -> None:
    conns = database.list_business_connections()
    if not conns:
        return handlers.bot.send_message(message.chat.id, i18n.t("own.connections.none"))
    lines = [i18n.t("own.connections.title"), ""]
    for c in conns:
        lines.append(i18n.t("own.connections.row_id",
                            id=utils.escape(c["business_connection_id"])))
        lines.append(i18n.t("own.connections.row_owner",
                            owner=utils.escape(c["business_user_id"])))
        lines.append(i18n.t("own.connections.row_state",
                            enabled=bool(c["is_enabled"]), can_reply=bool(c["can_reply"])))
        lines.append(i18n.t("own.connections.row_updated",
                            updated=utils.escape(c["updated_at"])))
    handlers.bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")


def cmd_connect_openai(message) -> None:
    """Legacy command: add a key for the active provider (previously OpenAI only)."""
    key = _args(message)
    if key:
        return _do_connect_key(message.chat.id, key, message_id=message.message_id)
    from handlers import ai_setup
    return ai_setup.open_root(message.chat.id)


def cmd_disconnect_openai(message) -> None:
    provider = ai_service.active_provider()
    ai_service.disconnect_api_key(provider.id)
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("own.key_removed", provider=utils.escape(provider.label)),
        parse_mode="HTML",
    )


def _set_toggle(message, key: str, value: bool, label: str) -> None:
    database.set_setting(key, value)
    mode = _current_mode()
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("own.toggle", label=label, state="ON" if value else "OFF", mode=mode),
        parse_mode="HTML",
    )


def cmd_memory_clear(message) -> None:
    handlers.bot.send_message(message.chat.id, i18n.t("own.mem_clear_ask"),
                              parse_mode="HTML", reply_markup=keyboards.confirm("memclear"))


def cmd_pause_chat(message) -> None:
    raw = _args(message)
    if not raw:
        database.set_owner_pending_input(security.operator_id(), "pause_chat", {}, 10)
        return handlers.bot.send_message(message.chat.id, i18n.t("own.pause.ask"))
    _do_pause(message.chat.id, raw, pause=True)


def cmd_resume_chat(message) -> None:
    raw = _args(message)
    if not raw:
        database.set_owner_pending_input(security.operator_id(), "resume_chat", {}, 10)
        return handlers.bot.send_message(message.chat.id, i18n.t("own.resume.ask"))
    _do_pause(message.chat.id, raw, pause=False)


def cmd_reset(message) -> None:
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("own.reset_ask"),
        parse_mode="HTML", reply_markup=keyboards.confirm("reset"),
    )


def cmd_cancel(message) -> None:
    database.clear_owner_pending_input(security.operator_id())
    handlers.bot.send_message(message.chat.id, i18n.t("own.cancelled"))


def cmd_instructions(message) -> None:
    """Show / set / clear the standing instruction added to every AI reply.

    This is the right place for behavior like language, tone or persona — unlike
    the knowledge base, it always applies (it is not retrieval-dependent)."""
    arg = _args(message)
    if not arg:
        current = database.get_str("custom_instructions")
        shown = utils.escape(current) if current else i18n.t("own.instructions.none")
        return handlers.bot.send_message(
            message.chat.id,
            i18n.t("own.instructions.title", current=shown),
            parse_mode="HTML")
    if arg.strip().lower() == "clear":
        database.set_setting("custom_instructions", "")
        return handlers.bot.send_message(message.chat.id, i18n.t("own.instructions.cleared"))
    database.set_setting("custom_instructions", arg)
    handlers.bot.send_message(message.chat.id, i18n.t("own.instructions.updated"))


# =============================================================================
# Pause/resume helper
# =============================================================================
def _do_pause(chat_id: int, raw: str, pause: bool) -> None:
    try:
        customer_chat_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(chat_id, i18n.t("own.pause.bad_id", raw=raw))
    bcid = business_service.find_bcid_for_chat(customer_chat_id)
    if bcid is None:
        return handlers.bot.send_message(chat_id, i18n.t("own.pause.no_connection"))
    if pause:
        business_service.pause_chat(bcid, customer_chat_id, reason="manual_pause", minutes=None)
        handlers.bot.send_message(chat_id, i18n.t("own.pause.paused", chat_id=customer_chat_id),
                                  parse_mode="HTML")
    else:
        ok = business_service.resume_chat(bcid, customer_chat_id)
        msg = i18n.t("own.pause.resumed") if ok else i18n.t("own.pause.not_paused")
        handlers.bot.send_message(chat_id, f"{msg} <code>{customer_chat_id}</code>.", parse_mode="HTML")


# =============================================================================
# Callbacks: control panel
# =============================================================================
def on_panel_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "status":
        bot.send_message(call.message.chat.id, _status_text(), parse_mode="HTML")
        return telegram_api.answer_callback(bot, call.id)
    if action == "help":
        bot.send_message(call.message.chat.id, help_text(), parse_mode="HTML")
        return telegram_api.answer_callback(bot, call.id)
    if action == "pending":
        bot.send_message(call.message.chat.id, approvals.render_pending_list(), parse_mode="HTML")
        return telegram_api.answer_callback(bot, call.id)
    if action == "mem_clear":
        bot.send_message(call.message.chat.id, i18n.t("own.mem_clear_ask_plain"),
                         reply_markup=keyboards.confirm("memclear"))
        return telegram_api.answer_callback(bot, call.id)
    if action == "mode":
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=keyboards.mode_keyboard(_current_mode()),
            )
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("own.panel.choose_mode"))
    if action == "mode_set":
        from handlers import owner_tools
        new_mode = owner_tools.set_mode(parts[2] if len(parts) > 2 else "off")
        _refresh_panel(call)
        return telegram_api.answer_callback(
            bot, call.id, i18n.t("own.panel.mode_set", mode=new_mode))
    if action == "home":
        try:
            bot.edit_message_text(
                i18n.t("own.panel.home"), call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=keyboards.control_panel(
                    database.get_bool("auto_reply_enabled"),
                    database.get_bool("approval_mode_enabled"),
                    _current_mode()),
            )
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id)
    if action in ("auto_toggle", "appr_toggle"):
        key = "auto_reply_enabled" if action == "auto_toggle" else "approval_mode_enabled"
        new_value = not database.get_bool(key)
        database.set_setting(key, new_value)
        _refresh_panel(call)
        label = i18n.t("own.label.auto") if action == "auto_toggle" \
            else i18n.t("own.label.approval")
        return telegram_api.answer_callback(
            bot, call.id,
            i18n.t("own.panel.toggle", label=label, state="ON" if new_value else "OFF"))
    telegram_api.answer_callback(bot, call.id)


def _refresh_panel(call) -> None:
    try:
        handlers.bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id,
            reply_markup=keyboards.control_panel(
                database.get_bool("auto_reply_enabled"),
                database.get_bool("approval_mode_enabled"),
                _current_mode(),
            ),
        )
    except Exception:
        pass


# =============================================================================
# Callbacks: confirmations
# =============================================================================
def on_confirm_callback(call) -> None:
    bot = handlers.bot
    parts = call.data.split(":")
    decision = parts[1] if len(parts) > 1 else "no"
    token = parts[2] if len(parts) > 2 else ""

    if decision != "yes":
        _strip(call)
        return telegram_api.answer_callback(bot, call.id, i18n.t("own.confirm.cancelled"))

    if token == "kbclear":
        from services import kb_service
        kb_service.clear_all()
        result = i18n.t("own.confirm.kb_cleared")
    elif token == "faqclear":
        removed = faq_service.clear()
        result = i18n.t("own.confirm.faq_cleared", count=removed)
    elif token == "aidisconnect":
        provider = ai_service.active_provider()
        ai_service.disconnect_api_key(provider.id)
        result = i18n.t("own.confirm.key_removed", provider=provider.label)
    elif token == "memclear":
        n = memory_service.clear_all()
        result = i18n.t("own.confirm.mem_cleared", count=n)
    elif token == "reset":
        result = _do_reset_transient()
    elif token == "rulesclear":
        removed = database.clear_topic_rules()
        result = i18n.t("rule.clear.done", count=removed)
    elif token == "resclear":
        removed = database.clear_resources()
        result = i18n.t("res.clear.done", count=removed)
    elif token == "unansclear":
        removed = database.clear_unanswered("open")
        result = i18n.t("unans.clear.done", count=removed)
    else:
        result = i18n.t("own.confirm.done")

    _strip(call, result)
    telegram_api.answer_callback(bot, call.id, i18n.t("own.confirm.done_ok"))


def _do_reset_transient() -> str:
    cancelled = database.cancel_all_pending_approvals()
    paused = database.clear_all_pauses()
    if security.operator_id() is not None:
        database.clear_owner_pending_input(security.operator_id())
    from services import batching
    batching.batcher.reset()
    return i18n.t("own.confirm.reset", cancelled=cancelled, paused=paused)


def _strip(call, new_text: str | None = None) -> None:
    try:
        if new_text:
            handlers.bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id)
        else:
            handlers.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                   reply_markup=None)
    except Exception:
        pass


# =============================================================================
# Pending-input application (routed from approvals.on_owner_pending_input)
# =============================================================================
def apply_pending_connect_openai(message, context: dict) -> None:
    """Legacy pending kind (kept for compatibility)."""
    database.clear_owner_pending_input(security.operator_id())
    key = (getattr(message, "text", "") or "").strip()
    _do_connect_key(message.chat.id, key, message_id=message.message_id)


def _do_connect_key(chat_id: int, key: str, message_id: int | None = None) -> None:
    from handlers import ai_setup
    ai_setup._apply_key(chat_id, key, ai_service.active_provider_id(), message_id)


def apply_pending_pause(message, kind: str, context: dict) -> None:
    database.clear_owner_pending_input(security.operator_id())
    raw = (getattr(message, "text", "") or "").strip()
    _do_pause(message.chat.id, raw, pause=(kind == "pause_chat"))


# =============================================================================
# Fallback (registered last)
# =============================================================================
def on_fallback(message) -> None:
    if security.is_operator_msg(message):
        handlers.bot.send_message(message.chat.id, i18n.t("own.fallback"))
    else:
        security.handle_non_owner_dm(message)

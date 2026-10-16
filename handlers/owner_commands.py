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
    cmd(["auto_on"])(lambda m: _set_toggle(m, "auto_reply_enabled", True, "Automatic replies"))
    cmd(["auto_off"])(lambda m: _set_toggle(m, "auto_reply_enabled", False, "Automatic replies"))
    cmd(["approval_on"])(lambda m: _set_toggle(m, "approval_mode_enabled", True, "Approval mode"))
    cmd(["approval_off"])(lambda m: _set_toggle(m, "approval_mode_enabled", False, "Approval mode"))
    cmd(["memory_clear"])(cmd_memory_clear)
    cmd(["pause_chat"])(cmd_pause_chat)
    cmd(["resume_chat"])(cmd_resume_chat)
    cmd(["reset"])(cmd_reset)
    cmd(["cancel"])(cmd_cancel)
    cmd(["instructions"])(cmd_instructions)
    cmd(["setup"])(cmd_setup)
    cmd(["connections"])(cmd_connections)

    # The primary owner alone controls delegated administrator accounts.
    bot.message_handler(commands=["admin"], func=security.is_owner_msg)(
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
        handlers.bot.send_message(
            message.chat.id,
            "Usage: <code>/admin &lt;user_id&gt;</code> to add, "
            "<code>/admin remove &lt;user_id&gt;</code> to remove, or "
            "<code>/admin list</code>.",
        )
        return
    if parts[0].lower() == "list" and len(parts) == 1:
        admins = database.list_assistant_admins()
        body = "\n".join(f"• <code>{uid}</code>" for uid in admins) or "(none)"
        handlers.bot.send_message(message.chat.id, "Delegated admins:\n" + body)
        return
    remove = parts[0].lower() == "remove"
    raw_id = parts[1] if remove and len(parts) == 2 else (parts[0] if len(parts) == 1 else "")
    try:
        user_id = int(raw_id)
        if user_id <= 0:
            raise ValueError
    except ValueError:
        handlers.bot.send_message(message.chat.id, "Send a positive numeric Telegram user ID.")
        return
    if remove and security.is_owner(user_id):
        handlers.bot.send_message(message.chat.id, "The primary owner cannot be removed as a delegated admin.")
        return
    changed = (database.remove_assistant_admin(user_id) if remove
               else database.add_assistant_admin(user_id))
    verb = "removed" if remove else "added"
    if not changed:
        handlers.bot.send_message(message.chat.id, f"Admin <code>{user_id}</code> was not {verb}.")
        return
    handlers.bot.send_message(
        message.chat.id,
        f"✅ Admin <code>{user_id}</code> {verb}. They must connect their own "
        "Telegram Business account before managing its assistant.",
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
        "👋 <b>Your Telegram Business assistant</b>\n\n"
        f"Mode: <b>{_current_mode()}</b> · AI: <b>{utils.escape(ai_service.backend_label())}</b> "
        f"({'ready ✅' if ai_service.is_ready() else 'not configured ⚠️ — open /ai'})\n\n"
        "Setup in three taps: /setup · /ai · /faq",
        parse_mode="HTML",
        reply_markup=keyboards.control_panel(
            database.get_bool("auto_reply_enabled"),
            database.get_bool("approval_mode_enabled"),
            _current_mode(),
        ),
    )


HELP_TEXT = (
    "🤖 <b>Your Telegram Business assistant</b>\n\n"
    "The bot answers your customers from your own Telegram Business account. "
    "Customers never talk to it directly — they message you, it replies as you.\n\n"
    "<b>First-time setup</b>\n"
    "1. @BotFather → /mybots → your bot → Bot Settings → <b>Business Mode</b> "
    "(some versions: Secretary Mode) → Turn on.\n"
    "2. Telegram → <b>Settings → Telegram Business → Chatbots</b> → paste the bot's "
    "@username → allow it <b>to reply to messages</b> → choose chats → save.\n"
    "3. Here: /ai to choose the AI, /faq to add answers, /mode to switch mode.\n"
    "Guided version of all this: /setup\n\n"
    "<b>Everyday commands</b>\n"
    "/mode — auto-reply · draft (approve first) · off\n"
    "/status — full status\n"
    "/health — run checks (token, AI, connection, storage)\n"
    "/chats — recent customer chats · /chat &lt;id&gt; — transcript\n"
    "/reply &lt;chat_id&gt; &lt;text&gt; — send a message yourself\n"
    "/takeover &lt;id&gt; · /handback &lt;id&gt; — stop / resume the AI for one chat\n"
    "/pause_chat &lt;id&gt; · /resume_chat &lt;id&gt; — the same for any paused chat\n"
    "/stats — customers, messages, AI replies\n"
    "/export — backup file (settings + quick answers)\n\n"
    "<b>AI setup</b>\n"
    "/ai — provider, API key, model, test · /aitest — quick test\n"
    "/freeai — providers that cost nothing (no credit card, no balance)\n"
    "/aimodel &lt;name&gt; — set a model · /instructions — standing instructions\n\n"
    "<b>Answers</b>\n"
    "/faq — quick answers menu (exact replies, sent instantly)\n"
    "/faq_add trigger1, trigger2 :: the exact reply\n"
    "/kb — knowledge base menu · /kb_add · /kb_upload · /kb_search · /kb_list\n\n"
    "<b>Panel & housekeeping</b>\n"
    "/start — control panel · /settings — all settings\n"
    "/approval_on · /approval_off · /auto_on · /auto_off\n"
    "/memory_clear — forget conversations · /reset — cancel approvals & pauses\n"
    "/cancel — abort a pending prompt\n\n"
    "<i>Owner takeover:</i> whenever you reply to a customer yourself (from the app "
    "or with /reply), the bot pauses that chat automatically for a while."
)


def cmd_help(message) -> None:
    handlers.bot.send_message(message.chat.id, HELP_TEXT, parse_mode="HTML")


def cmd_status(message) -> None:
    handlers.bot.send_message(message.chat.id, _status_text(), parse_mode="HTML")


def _status_text() -> str:
    st = business_service.get_status()
    mode = _current_mode()
    provider = ai_service.active_provider()
    lines = ["📊 <b>Status</b>", ""]
    lines.append(f"Reply mode: <b>{mode}</b>")
    lines.append(f"Auto-reply switch: <b>{'ON' if st['auto_reply_enabled'] else 'OFF'}</b> · "
                 f"Approval: <b>{'ON' if st['approval_mode_enabled'] else 'OFF'}</b>")
    lines.append(f"AI: <b>{'ready ✅' if ai_service.is_ready() else 'not configured ⚠️'}</b>")
    for line in ai_service.status_lines():
        lines.append(f"   {utils.escape(line)}")
    if provider.key_url and not ai_service.has_api_key(provider.id) and provider.key_required:
        lines.append(f"   Get a key: {utils.escape(provider.key_url)}")
    if not ai_service.is_ready() or providers.needs_credit(provider.id):
        lines.append("   💡 /freeai — AI providers that need no credit card or balance.")
    lines.append("")
    conns = st["connections"]
    if not conns:
        lines.append("Business connections: <b>none</b> — connect the bot in "
                     "Telegram → Settings → Business → Chatbots.")
    else:
        lines.append(f"Business connections: <b>{len(conns)}</b>")
        for c in conns:
            lines.append(
                f"  • owner <code>{utils.escape(c['business_user_id'])}</code> · "
                f"{'enabled' if c['is_enabled'] else 'disabled'} · "
                f"{'can reply' if c['can_reply'] else 'read-only ⚠️'}"
            )
    lines.append("")
    lines.append(f"Paused chats: <b>{st['paused_count']}</b>")
    lines.append(f"Pending approvals: <b>{st['pending_approvals']}</b>")
    lines.append(f"Knowledge base: <b>{st['kb']['items']}</b> items / {st['kb']['chunks']} chunks")
    lines.append(f"Quick answers: <b>{faq_service.count()}</b>")
    lines.append("")
    lines.append("<i>Run /health for a full check.</i>")
    return "\n".join(lines)


def cmd_settings(message) -> None:
    from handlers import settings as settings_handler
    settings_handler.open_root(message)


def cmd_setup(message) -> None:
    from handlers import setup_guide
    setup_guide.send_checklist(message.chat.id)


def cmd_connections(message) -> None:
    conns = database.list_business_connections()
    if not conns:
        return handlers.bot.send_message(
            message.chat.id,
            "No business connection yet.\n\n"
            "Telegram → Settings → Telegram Business → Chatbots → add this bot → "
            "allow it to reply. Full guide: /setup",
        )
    lines = ["🔗 <b>Business connections</b>", ""]
    for c in conns:
        lines.append(f"• ID <code>{utils.escape(c['business_connection_id'])}</code>")
        lines.append(f"  owner: <code>{utils.escape(c['business_user_id'])}</code>")
        lines.append(f"  enabled: <b>{bool(c['is_enabled'])}</b> · "
                     f"can reply: <b>{bool(c['can_reply'])}</b>")
        lines.append(f"  updated: {utils.escape(c['updated_at'])}")
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
        f"{utils.escape(provider.label)} key removed. AI replies are off until you add "
        "a key again with /ai.",
        parse_mode="HTML",
    )


def _set_toggle(message, key: str, value: bool, label: str) -> None:
    database.set_setting(key, value)
    mode = _current_mode()
    handlers.bot.send_message(
        message.chat.id,
        f"{label}: <b>{'ON' if value else 'OFF'}</b>\nReply mode: <b>{mode}</b>",
        parse_mode="HTML",
    )


def cmd_memory_clear(message) -> None:
    handlers.bot.send_message(message.chat.id, "Clear <b>all</b> conversation memory?",
                              parse_mode="HTML", reply_markup=keyboards.confirm("memclear"))


def cmd_pause_chat(message) -> None:
    raw = _args(message)
    if not raw:
        database.set_owner_pending_input(security.operator_id(), "pause_chat", {}, 10)
        return handlers.bot.send_message(message.chat.id, "Send the customer chat ID to pause, or /cancel.")
    _do_pause(message.chat.id, raw, pause=True)


def cmd_resume_chat(message) -> None:
    raw = _args(message)
    if not raw:
        database.set_owner_pending_input(security.operator_id(), "resume_chat", {}, 10)
        return handlers.bot.send_message(message.chat.id, "Send the customer chat ID to resume, or /cancel.")
    _do_pause(message.chat.id, raw, pause=False)


def cmd_reset(message) -> None:
    handlers.bot.send_message(
        message.chat.id,
        "Reset transient state? This cancels all <b>pending approvals</b>, clears "
        "<b>pauses</b>, and clears any pending input. Settings, KB and history are kept.",
        parse_mode="HTML", reply_markup=keyboards.confirm("reset"),
    )


def cmd_cancel(message) -> None:
    database.clear_owner_pending_input(security.operator_id())
    handlers.bot.send_message(message.chat.id, "Cancelled. ✖")


def cmd_instructions(message) -> None:
    """Show / set / clear the standing instruction added to every AI reply.

    This is the right place for behavior like language, tone or persona — unlike
    the knowledge base, it always applies (it is not retrieval-dependent)."""
    arg = _args(message)
    if not arg:
        current = database.get_str("custom_instructions")
        shown = utils.escape(current) if current else "<i>(none)</i>"
        return handlers.bot.send_message(
            message.chat.id,
            "📝 <b>Custom instructions</b> — always added to the AI's system prompt "
            "(applies to every reply, on every provider):\n\n"
            f"{shown}\n\n"
            "Set:   <code>/instructions &lt;text&gt;</code>\n"
            "Example: <code>/instructions Always reply in Egyptian Arabic, keep it short.</code>\n"
            "Clear: <code>/instructions clear</code>\n\n"
            "<i>Tip: language, tone and persona also have their own rows in /settings → "
            "Persona.</i>",
            parse_mode="HTML")
    if arg.strip().lower() == "clear":
        database.set_setting("custom_instructions", "")
        return handlers.bot.send_message(message.chat.id, "Custom instructions cleared. ✖")
    database.set_setting("custom_instructions", arg)
    handlers.bot.send_message(
        message.chat.id,
        "✅ Custom instructions updated. They'll be applied to every reply from now on.")


# =============================================================================
# Pause/resume helper
# =============================================================================
def _do_pause(chat_id: int, raw: str, pause: bool) -> None:
    try:
        customer_chat_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(chat_id, f"'{raw}' is not a valid chat ID.")
    bcid = business_service.find_bcid_for_chat(customer_chat_id)
    if bcid is None:
        return handlers.bot.send_message(
            chat_id, "Couldn't determine the business connection for that chat "
                     "(no messages seen yet, or multiple connections).")
    if pause:
        business_service.pause_chat(bcid, customer_chat_id, reason="manual_pause", minutes=None)
        handlers.bot.send_message(chat_id, f"⏸ Paused chat <code>{customer_chat_id}</code>.",
                                  parse_mode="HTML")
    else:
        ok = business_service.resume_chat(bcid, customer_chat_id)
        msg = "▶️ Resumed" if ok else "Chat was not paused"
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
        bot.send_message(call.message.chat.id, HELP_TEXT, parse_mode="HTML")
        return telegram_api.answer_callback(bot, call.id)
    if action == "pending":
        bot.send_message(call.message.chat.id, approvals.render_pending_list(), parse_mode="HTML")
        return telegram_api.answer_callback(bot, call.id)
    if action == "mem_clear":
        bot.send_message(call.message.chat.id, "Clear all conversation memory?",
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
        return telegram_api.answer_callback(bot, call.id, "Choose the reply mode")
    if action == "mode_set":
        from handlers import owner_tools
        new_mode = owner_tools.set_mode(parts[2] if len(parts) > 2 else "off")
        _refresh_panel(call)
        return telegram_api.answer_callback(bot, call.id, f"Mode: {new_mode}")
    if action == "home":
        try:
            bot.edit_message_text(
                "👋 <b>Control panel</b>", call.message.chat.id, call.message.message_id,
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
        label = "Auto-reply" if action == "auto_toggle" else "Approval mode"
        return telegram_api.answer_callback(bot, call.id, f"{label} {'ON' if new_value else 'OFF'}")
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
        return telegram_api.answer_callback(bot, call.id, "Cancelled.")

    if token == "kbclear":
        from services import kb_service
        kb_service.clear_all()
        result = "Knowledge base cleared."
    elif token == "faqclear":
        removed = faq_service.clear()
        result = f"Quick answers cleared ({removed} entries)."
    elif token == "aidisconnect":
        provider = ai_service.active_provider()
        ai_service.disconnect_api_key(provider.id)
        result = f"{provider.label} key removed."
    elif token == "memclear":
        n = memory_service.clear_all()
        result = f"Cleared conversation memory ({n} rows)."
    elif token == "reset":
        result = _do_reset_transient()
    else:
        result = "Done."

    _strip(call, result)
    telegram_api.answer_callback(bot, call.id, "Done ✅")


def _do_reset_transient() -> str:
    cancelled = database.cancel_all_pending_approvals()
    paused = database.clear_all_pauses()
    if security.operator_id() is not None:
        database.clear_owner_pending_input(security.operator_id())
    from services import batching
    batching.batcher.reset()
    return f"Reset done: {cancelled} approval(s) cancelled, {paused} pause(s) cleared."


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
        handlers.bot.send_message(message.chat.id,
                                  "I didn't recognise that. Use /start for the control panel "
                                  "or /help for commands.")
    else:
        security.handle_non_owner_dm(message)

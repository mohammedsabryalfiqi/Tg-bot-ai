"""Incoming Telegram Business updates: connection changes and the customer-
message decision pipeline, plus edited/deleted message handlers.

Every handler is wrapped so a single bad update can never crash polling.

Pipeline (one customer message):
    decode -> guards (bot echo / owner takeover) -> record -> dedupe ->
    automation switches -> rate limit -> batch burst -> build prompt ->
    FAQ short-circuit or AI -> approval (draft) or auto-send.
"""

from __future__ import annotations

import logging

import database
import handlers
import keyboards
import telegram_api
import utils
from handlers import approvals
from services import (
    batching,
    business_service,
    memory_service,
    prompt_service,
    providers,
    rate_limit_service,
)
from services import ai_service
from services.ai_service import AIServiceError

log = logging.getLogger("smartel.business")

# Content types we ask Telegram to deliver. Non-text are gated inside the
# pipeline (captions are processed; pure media is skipped/monitored).
_CONTENT_TYPES = [
    "text", "photo", "document", "voice", "audio", "video",
    "video_note", "sticker", "location", "contact", "animation",
]

DEFAULT_WELCOME_TEXT = (
    "👋 Hello! Thanks for messaging us — how can we help you today?"
)


def _tenant_for_connection_id(bcid: str | None) -> int | None:
    import security
    if not bcid:
        return None
    conn = business_service.get_connection(bcid)
    if conn is None or conn["business_user_id"] is None:
        return None
    uid = int(conn["business_user_id"])
    if (database.is_assistant_admin(uid) and not security.is_owner(uid)
            and not security.is_primary_admin(uid)):
        return uid
    if (database.multi_admin_enabled() and not security.is_owner(uid)
            and not security.is_primary_admin(uid)):
        return None
    return 0


def register(bot, cfg) -> None:
    @bot.business_connection_handler()
    def _on_business_connection(bc):
        try:
            on_business_connection(bc)
        except Exception:
            log.exception("business_connection handler failed")

    @bot.business_message_handler(content_types=_CONTENT_TYPES)
    def _on_business_message(message):
        try:
            process_business_message(message)
        except Exception:
            log.exception("business_message pipeline crashed (swallowed)")

    @bot.edited_business_message_handler(content_types=_CONTENT_TYPES)
    def _on_edited_business_message(message):
        try:
            tenant = _tenant_for_connection_id(getattr(message, "business_connection_id", None))
            if tenant is not None:
                with database.tenant_scope(tenant):
                    on_edited_business_message(message)
        except Exception:
            log.exception("edited_business_message handler failed")

    @bot.deleted_business_messages_handler()
    def _on_deleted_business_messages(deleted):
        try:
            tenant = _tenant_for_connection_id(getattr(deleted, "business_connection_id", None))
            if tenant is not None:
                with database.tenant_scope(tenant):
                    on_deleted_business_messages(deleted)
        except Exception:
            log.exception("deleted_business_messages handler failed")


# =============================================================================
# Connection updates
# =============================================================================
def on_business_connection(bc) -> None:
    import security
    user_id = getattr(getattr(bc, "user", None), "id", None)
    if user_id is None:
        log.warning("Business connection update without account user id")
        return
    if (bool(getattr(bc, "is_enabled", True)) and database.multi_admin_enabled()
            and not security.is_owner(user_id)
            and not security.is_primary_admin(user_id)
            and not database.is_assistant_admin(user_id)):
        log.warning("rejecting unassigned account while multi-admin mode is active")
        return
    business_service.upsert_connection(bc)
    is_enabled = bool(getattr(bc, "is_enabled", True))
    can_reply = business_service.resolve_can_reply(bc)
    notify = ((lambda text: handlers.bot.send_message(user_id, text))
              if database.is_assistant_admin(user_id) or security.is_primary_admin(user_id)
              else handlers.notify_owner)
    if is_enabled:
        notify(
            "🔗 <b>Business connection enabled.</b>\n"
            f"Owner account ID: <code>{utils.escape(getattr(getattr(bc, 'user', None), 'id', '?'))}</code>\n"
            f"Bot can reply: <b>{'yes' if can_reply else 'no'}</b>\n\n"
            "The bot will now receive this account's customer messages. "
            "Use /status any time."
        )
        if not can_reply:
            notify(
                "⚠️ This connection does <b>not</b> grant reply permission, so the "
                "bot can read but not send. Enable replies for the bot in your "
                "Telegram Business → Chatbots settings."
            )
    else:
        notify("🔌 <b>Business connection disabled or removed.</b>")


# =============================================================================
# Customer message pipeline
# =============================================================================
def process_business_message(message) -> None:
    """Route each accepted Business update into its owner's isolated tenant."""
    import security
    bcid = getattr(message, "business_connection_id", None)
    conn = business_service.get_connection(bcid) if bcid else None
    if conn is None:
        return
    account_id = conn["business_user_id"]
    if account_id is None:
        return
    if (database.multi_admin_enabled() and not security.is_owner(account_id)
            and not security.is_primary_admin(account_id)
            and not database.is_assistant_admin(account_id)):
        log.warning("message from unassigned account ignored while multi-admin mode is active")
        return
    # Existing primary-owner connections keep their legacy profile. Delegated
    # admins always get a separate database and cannot inherit the owner's data.
    tenant = (account_id if database.is_assistant_admin(account_id)
              and not security.is_owner(account_id)
              and not security.is_primary_admin(account_id) else 0)
    with database.tenant_scope(tenant):
        _process_business_message_scoped(message)


def _process_business_message_scoped(message) -> None:
    bcid = getattr(message, "business_connection_id", None)
    if not bcid:
        log.warning("business_message without business_connection_id; ignoring")
        return

    conn = business_service.get_connection(bcid)
    if conn is None:
        conn = business_service.fetch_and_store_via_raw(bcid)
        if conn is None:
            log.warning("unknown business_connection_id=%s; ignoring", utils.mask_connection(bcid))
            return

    customer_chat_id = message.chat.id
    sender = getattr(message, "from_user", None)
    sender_id = sender.id if sender else None

    # Guard 1: the bot's own outgoing business message echoed back.
    if getattr(message, "sender_business_bot", None) is not None:
        log.debug("ignoring sender_business_bot echo")
        return

    # Guard 2: the OWNER typed manually in this chat -> takeover, pause, never reply.
    owner_user_id = conn["business_user_id"]
    if sender_id is not None and owner_user_id is not None and sender_id == owner_user_id:
        minutes = database.get_int("owner_takeover_pause_minutes")
        business_service.pause_chat(bcid, customer_chat_id, reason="owner_takeover", minutes=minutes)
        log.info("owner takeover chat=%s -> paused %d min",
                 utils.mask_id(customer_chat_id), minutes)
        return

    # It's a genuine customer message — record the customer (keep names fresh).
    business_service.upsert_customer_from_message(bcid, message)

    # Extract text: plain text, or a media caption when caption processing is
    # enabled. Pure media (or captions while disabled) is skipped/monitored.
    text = (getattr(message, "text", None) or "").strip()
    if not text:
        caption = (getattr(message, "caption", None) or "").strip()
        if caption and database.get_bool("process_nontext_enabled"):
            text = caption
    if not text:
        _handle_non_text(conn, message)
        return

    # Dedupe: Telegram can redeliver updates (restart mid-poll / retries) and a
    # redelivered message must not produce a second reply.
    message_id = getattr(message, "message_id", None)
    if database.message_exists(bcid, customer_chat_id, message_id, "in"):
        log.info("duplicate inbound message %s ignored", message_id)
        return

    # Record the inbound message (history + rate-limit window).
    database.insert_message(bcid, customer_chat_id, message_id, "in", "user", text)

    # Global automation switch.
    if not _any_automation_on():
        if database.get_bool("monitoring_mode"):
            _notify_incoming(bcid, customer_chat_id, text)
        return

    # Paused (owner takeover / manual pause / rate-limit pause).
    if business_service.is_chat_paused(bcid, customer_chat_id):
        log.debug("chat paused; skipping auto-reply")
        return

    # Rate limit.
    decision = rate_limit_service.enforce(bcid, customer_chat_id)
    if not decision.allowed:
        name = business_service.customer_display_name(bcid, customer_chat_id)
        handlers.notify_owner(
            f"🚦 <b>{utils.escape(name)}</b> hit the message limit "
            f"({decision.used}/{decision.limit} in the last hour). "
            "Auto-replies for this chat are paused for 1 hour."
        )
        return

    # Welcome a brand-new customer (its first message is the one just recorded).
    if database.get_bool("greet_new_customers") and _is_first_inbound(bcid, customer_chat_id):
        _send_welcome(conn, customer_chat_id)

    # Batch rapid-fire messages from the same customer into one reply.
    key = (bcid, customer_chat_id)
    batch = batching.batcher.process(key, message_id, text)
    if batch is None:
        log.debug("message %s folded into an in-flight batch", message_id)
        return
    combined_text = "\n".join(part for _, part in batch if part).strip()
    if not combined_text:
        return
    first_message_id = batch[0][0] if batch else message_id

    # Typing indicator while we think (keeps "typing…" alive for slow models).
    with telegram_api.typing_keepalive(
        handlers.bot, customer_chat_id,
        business_connection_id=bcid,
        enabled=database.get_bool("typing_indicator"),
    ):
        reply_text = _generate_reply(conn, customer_chat_id, combined_text)
    if not reply_text:
        return
    reply_text = prompt_service.apply_signature(reply_text)

    # Sensitive handling + dispatch.
    sensitive = prompt_service.is_sensitive(combined_text)
    force_approval = sensitive and database.get_bool("sensitive_requires_approval")

    if database.get_bool("approval_mode_enabled") or force_approval:
        approvals.create_request(conn, message, combined_text, reply_text, sensitive=sensitive)
    else:
        _deliver_auto(conn, customer_chat_id, first_message_id, combined_text, reply_text)


def _generate_reply(conn, customer_chat_id: int, customer_text: str) -> str | None:
    """Build the prompt and generate the reply (or a canned short-circuit)."""
    bcid = conn["business_connection_id"]
    messages, short = prompt_service.build_messages(bcid, customer_chat_id, customer_text)
    if short is not None:
        return short
    try:
        return ai_service.chat(messages)
    except AIServiceError as e:
        name = business_service.customer_display_name(bcid, customer_chat_id)
        lines = [
            f"⚠️ Could not generate a reply for <b>{utils.escape(name)}</b> "
            f"(chat <code>{customer_chat_id}</code>): {utils.escape(e.owner_message)}",
            "",
            "No message was sent to the customer.",
        ]
        if e.hints:
            lines.append("")
            lines += [f"• {utils.escape(hint)}" for hint in e.hints[:3]]
        markup = None
        suggestions = providers.switch_suggestions(ai_service.active_provider_id()) \
            if e.kind in ai_service.SWITCHABLE_KINDS else []
        if suggestions:
            markup = keyboards.ai_free_switch(suggestions)
        handlers.notify_owner("\n".join(lines), reply_markup=markup)
        log.warning("AI generation failed kind=%s chat=%s",
                    e.kind, utils.mask_id(customer_chat_id))
        return None


def _any_automation_on() -> bool:
    """True when either auto-send or draft (approval) mode is enabled."""
    return database.get_bool("auto_reply_enabled") or database.get_bool("approval_mode_enabled")


def _is_first_inbound(bcid: str, customer_chat_id: int) -> bool:
    """True when the message just recorded is this customer's first one ever."""
    try:
        return database.count_messages_in_window(
            bcid, customer_chat_id, utils.future_iso(-60 * 24 * 365 * 20), direction="in"
        ) == 1
    except Exception:
        return False


def _send_welcome(conn, customer_chat_id: int) -> None:
    text = (database.get_str("welcome_text") or "").strip() or DEFAULT_WELCOME_TEXT
    bcid = conn["business_connection_id"]
    if not (conn["is_enabled"] and conn["can_reply"]):
        return
    try:
        telegram_api.send_reply(handlers.bot, customer_chat_id, text,
                                business_connection_id=bcid)
        database.insert_message(bcid, customer_chat_id, None, "out", "assistant", text)
        log.info("welcomed new customer chat=%s", utils.mask_id(customer_chat_id))
    except Exception:
        log.warning("could not send the welcome message", exc_info=True)


def _handle_non_text(conn, message) -> None:
    """Media/voice/etc: never auto-answer (unless an acknowledgement is set)."""
    bcid = conn["business_connection_id"]
    chat_id = message.chat.id
    content_type = getattr(message, "content_type", "unknown")
    ack = (database.get_str("nontext_ack_message") or "").strip()
    if database.get_bool("monitoring_mode"):
        name = business_service.customer_display_name(bcid, chat_id)
        suffix = "" if not ack else " Sent the configured acknowledgement."
        handlers.notify_owner(
            f"📎 <b>{utils.escape(name)}</b> sent a non-text "
            f"<i>{utils.escape(content_type)}</i> message "
            f"(chat <code>{chat_id}</code>).{suffix}"
        )
    if not ack or database.message_exists(bcid, chat_id, getattr(message, "message_id", None), "in"):
        return
    if business_service.is_chat_paused(bcid, chat_id) or not _any_automation_on():
        return
    database.insert_message(bcid, chat_id, getattr(message, "message_id", None), "in", "user",
                            f"[{content_type}]")
    if database.get_bool("approval_mode_enabled") or not (conn["is_enabled"] and conn["can_reply"]):
        approvals.create_request(conn, message, f"[{content_type}]", ack, sensitive=False)
    else:
        _deliver_auto(conn, chat_id, getattr(message, "message_id", None), f"[{content_type}]", ack)


def _deliver_auto(conn, customer_chat_id: int, customer_message_id, customer_text: str,
                  reply_text: str) -> None:
    bcid = conn["business_connection_id"]
    if not (conn["is_enabled"] and conn["can_reply"]):
        handlers.notify_owner(
            "⚠️ Cannot auto-reply: the business connection is disabled or lacks "
            "reply permission. Check Telegram Business → Chatbots."
        )
        return
    try:
        telegram_api.send_reply(
            handlers.bot,
            customer_chat_id,
            reply_text,
            business_connection_id=bcid,
            reply_to_message_id=customer_message_id,
        )
    except telegram_api.TelegramPartialSendError as exc:
        log.error(
            "auto-reply partially delivered chat=%s chunks=%d/%d",
            utils.mask_id(customer_chat_id),
            exc.sent_count,
            exc.total_count,
        )
        name = business_service.customer_display_name(bcid, customer_chat_id)
        handlers.notify_owner(
            f"⚠️ An automatic reply to <b>{utils.escape(name)}</b> was only "
            f"partially delivered ({exc.sent_count}/{exc.total_count} parts). "
            "Check the customer chat before sending anything else."
        )
        return
    except Exception as exc:
        log.warning(
            "auto-reply delivery unconfirmed chat=%s error=%s",
            utils.mask_id(customer_chat_id),
            type(exc).__name__,
        )
        name = business_service.customer_display_name(bcid, customer_chat_id)
        handlers.notify_owner(
            f"⚠️ Delivery of an automatic reply to <b>{utils.escape(name)}</b> "
            "could not be confirmed. No outbound history was recorded; check "
            "the customer chat before retrying."
        )
        return
    database.insert_message(bcid, customer_chat_id, None, "out", "assistant", reply_text)
    memory_service.append_exchange(bcid, customer_chat_id, customer_text, reply_text)
    log.info("auto-replied chat=%s len=%d", utils.mask_id(customer_chat_id), len(reply_text))
    if database.get_bool("monitoring_mode"):
        name = business_service.customer_display_name(bcid, customer_chat_id)
        handlers.notify_owner(
            f"🤖 Auto-replied to <b>{utils.escape(name)}</b>:\n"
            f"<i>“{utils.escape(customer_text[:200])}”</i>\n"
            f"➡️ {utils.escape(reply_text[:500])}"
        )


def _notify_incoming(bcid: str, customer_chat_id: int, text: str) -> None:
    name = business_service.customer_display_name(bcid, customer_chat_id)
    handlers.notify_owner(
        f"📥 <b>{utils.escape(name)}</b> (chat <code>{customer_chat_id}</code>):\n"
        f"<i>{utils.escape(text[:500])}</i>\n\n"
        "<i>Auto-reply is OFF — reply yourself or enable it with /auto_on.</i>"
    )


# =============================================================================
# Edited / deleted
# =============================================================================
def on_edited_business_message(message) -> None:
    # Informational only: do NOT generate a new reply (prevents edit loops).
    bcid = getattr(message, "business_connection_id", None)
    if not bcid:
        return
    conn = business_service.get_connection(bcid)
    owner_user_id = conn["business_user_id"] if conn else None
    sender = getattr(message, "from_user", None)
    if sender and owner_user_id and sender.id == owner_user_id:
        return  # owner edited their own message
    invalidated = database.invalidate_approvals_for_messages(
        bcid, message.chat.id, [message.message_id]
    )
    log.info(
        "customer edited message chat=%s (invalidated %d approvals)",
        utils.mask_id(message.chat.id), invalidated,
    )
    if not database.get_bool("monitoring_mode"):
        return
    name = business_service.customer_display_name(bcid, message.chat.id)
    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    cancellation = (
        "\nThe pending approval for the earlier version was cancelled."
        if invalidated else ""
    )
    handlers.notify_owner(
        f"✏️ <b>{utils.escape(name)}</b> edited a message: "
        f"<i>{utils.escape(text[:300])}</i>{cancellation}"
    )


def on_deleted_business_messages(deleted) -> None:
    bcid = getattr(deleted, "business_connection_id", None)
    chat = getattr(deleted, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_ids = list(getattr(deleted, "message_ids", []) or [])
    if not bcid or chat_id is None:
        return
    invalidated = database.invalidate_approvals_for_messages(bcid, chat_id, message_ids)
    log.info("customer deleted %d msgs chat=%s (invalidated %d approvals)",
             len(message_ids), utils.mask_id(chat_id), invalidated)
    if invalidated and database.get_bool("monitoring_mode"):
        handlers.notify_owner(
            "🗑 A customer deleted a message that had a pending approval; "
            "that approval was cancelled."
        )

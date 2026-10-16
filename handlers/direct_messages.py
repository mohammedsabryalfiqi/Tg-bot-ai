"""Private conversations: people writing to the **bot's own** chat.

Why this exists
---------------
Telegram Business mode answers the messages that arrive at a *business account*
that linked the bot. Plenty of owners do not have (or do not want) Telegram
Business — they simply want the bot to reply to whoever messages it privately.

How it works
------------
A direct chat is stored under the reserved connection id ``direct`` (see
``telegram_api.DIRECT_CONNECTION_ID``), so it reuses the entire existing
pipeline instead of duplicating it: customers, message history, per-chat memory,
FAQ / knowledge-base grounding, rate limiting, message batching, approval
(draft) mode, pause / takeover, owner notifications and statistics all work
unchanged.

The only real difference is on the wire: a direct reply must be sent *without*
``business_connection_id`` (Telegram rejects an id that was never granted) —
``telegram_api`` strips the sentinel automatically.

Switches
--------
* ``direct_reply_enabled`` — /direct, or /settings → Replies. Off = the bot only
  sends the "managed assistant" notice (the pre-existing behaviour).
* ``auto_reply_enabled`` / ``approval_mode_enabled`` — the same reply mode as the
  business pipeline: 🟢 auto · 📝 draft · 🔴 off.
"""

from __future__ import annotations

import logging

import database
import handlers
import i18n
import security
import keyboards
import telegram_api
import utils
from handlers import approvals
from services import (
    ai_service,
    batching,
    business_service,
    memory_service,
    prompt_service,
    providers,
    rate_limit_service,
)
from services.ai_service import AIServiceError

log = logging.getLogger("smartel.direct")

# Text plus the media types we acknowledge/monitor (captions are gated by
# process_nontext_enabled, exactly like the business pipeline).
_CONTENT_TYPES = [
    "text", "photo", "document", "voice", "audio", "video",
    "video_note", "sticker", "location", "contact", "animation",
]


def register(bot, cfg) -> None:
    """Register the direct-message pipeline (call it before the fallback)."""
    @bot.message_handler(func=should_handle, content_types=_CONTENT_TYPES)
    def _on_direct_message(message):
        try:
            process_direct_message(message)
        except Exception:
            log.exception("direct message pipeline crashed (swallowed)")


def should_handle(message) -> bool:
    """True when this private message belongs to the direct-message pipeline.

    Owner/admin messages, slash-commands, non-private chats and bots are left to
    their own handlers (commands keep working exactly as before).
    """
    import security
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    if chat is None or getattr(chat, "type", None) != "private":
        return False
    if user is None or getattr(user, "is_bot", False):
        return False
    if security.owner_id() is None:            # still waiting for the claim code
        return False
    if security.is_operator_msg(message):      # the owner talks to their bot
        return False
    if (getattr(message, "text", "") or "").startswith("/"):
        return False                           # unknown command -> fallback notice
    try:
        if not database.get_bool("direct_reply_enabled"):
            return False
    except Exception:
        return False
    # With no working AI backend there is nothing to answer with: leave the
    # message to the fallback, which sends the "managed assistant" notice.
    return ai_service.is_ready()


# =============================================================================
# Pipeline
# =============================================================================
def process_direct_message(message) -> None:
    """Handle one private message sent to the bot itself."""
    with database.tenant_scope(0):
        _process_scoped(message)


def _process_scoped(message) -> None:
    bcid = business_service.ensure_direct_connection()
    conn = business_service.get_connection(bcid)
    if conn is None or not conn["is_enabled"]:
        return

    chat_id = message.chat.id
    sender = getattr(message, "from_user", None)
    sender_id = getattr(sender, "id", None)
    if sender_id is not None and security.owner_id() == sender_id:
        return                                  # the owner's own chat with the bot

    business_service.upsert_customer_from_message(bcid, message)

    if not ai_service.is_ready():
        # The bot is not configured (yet): keep the pre-existing behaviour of
        # telling strangers what this account is, instead of staying silent.
        security.handle_non_owner_dm(message)
        return

    text = (getattr(message, "text", None) or "").strip()
    if not text:
        caption = (getattr(message, "caption", None) or "").strip()
        if caption and database.get_bool("process_nontext_enabled"):
            text = caption
    if not text:
        _handle_non_text(conn, message)
        return

    message_id = getattr(message, "message_id", None)
    if database.message_exists(bcid, chat_id, message_id, "in"):
        log.info("duplicate direct message %s ignored", message_id)
        return
    database.insert_message(bcid, chat_id, message_id, "in", "user", text)

    if not _any_automation_on():
        if database.get_bool("monitoring_mode"):
            _notify_incoming(bcid, chat_id, text)
        return

    if business_service.is_chat_paused(bcid, chat_id):
        log.debug("direct chat paused; skipping auto-reply")
        return

    decision = rate_limit_service.enforce(bcid, chat_id)
    if not decision.allowed:
        name = business_service.customer_display_name(bcid, chat_id)
        handlers.notify_owner(i18n.t(
            "biz.notify.rate_limit", name=utils.escape(name),
            used=decision.used, limit=decision.limit,
        ))
        return

    if database.get_bool("greet_new_customers") and _is_first_inbound(bcid, chat_id):
        _send_welcome(conn, chat_id)
        return

    batch = batching.batcher.process((bcid, chat_id), message_id, text)
    if batch is None:                           # covered by an in-flight batch
        return
    combined_text = "\n".join(t for _mid, t in batch).strip()
    if not combined_text:
        return
    first_message_id = batch[0][0] if batch else message_id

    with telegram_api.typing_keepalive(
        handlers.bot, chat_id,
        business_connection_id=bcid,
        enabled=database.get_bool("typing_indicator"),
    ):
        reply_text = _generate_reply(conn, chat_id, combined_text)
    if not reply_text:
        return
    reply_text = prompt_service.apply_signature(reply_text)

    sensitive = prompt_service.is_sensitive(combined_text)
    force_approval = sensitive and database.get_bool("sensitive_requires_approval")

    if database.get_bool("approval_mode_enabled") or force_approval:
        approvals.create_request(conn, message, combined_text, reply_text, sensitive=sensitive)
    else:
        _deliver_auto(conn, chat_id, first_message_id, combined_text, reply_text)


def _generate_reply(conn, chat_id: int, customer_text: str) -> str | None:
    bcid = conn["business_connection_id"]
    messages, short = prompt_service.build_messages(bcid, chat_id, customer_text, direct=True)
    if short is not None:
        return short
    try:
        return ai_service.chat(messages)
    except AIServiceError as e:
        name = business_service.customer_display_name(bcid, chat_id)
        lines = [
            i18n.t("biz.notify.ai_failed", name=utils.escape(name), chat_id=chat_id,
                   error=utils.escape(e.owner_message)),
            "",
            i18n.t("biz.notify.ai_failed_tail"),
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
        log.warning("AI generation failed kind=%s direct chat=%s",
                    e.kind, utils.mask_id(chat_id))
        return None


def _deliver_auto(conn, chat_id: int, customer_message_id, customer_text: str,
                  reply_text: str) -> None:
    bcid = conn["business_connection_id"]
    if not (conn["is_enabled"] and conn["can_reply"]):
        handlers.notify_owner(i18n.t("biz.notify.cannot_reply"))
        return
    try:
        telegram_api.send_reply(
            handlers.bot, chat_id, reply_text,
            business_connection_id=bcid,
            reply_to_message_id=customer_message_id,
        )
    except telegram_api.TelegramPartialSendError as exc:
        log.error("direct reply partially delivered chat=%s chunks=%d/%d",
                  utils.mask_id(chat_id), exc.sent_count, exc.total_count)
        name = business_service.customer_display_name(bcid, chat_id)
        handlers.notify_owner(i18n.t(
            "biz.notify.delivery_partial", name=utils.escape(name),
            sent=exc.sent_count, total=exc.total_count,
        ))
        return
    except Exception as exc:
        log.warning("direct reply delivery unconfirmed chat=%s error=%s",
                    utils.mask_id(chat_id), type(exc).__name__)
        name = business_service.customer_display_name(bcid, chat_id)
        handlers.notify_owner(i18n.t("biz.notify.delivery_unknown", name=utils.escape(name)))
        return
    database.insert_message(bcid, chat_id, None, "out", "assistant", reply_text)
    memory_service.append_exchange(bcid, chat_id, customer_text, reply_text)
    log.info("direct auto-reply chat=%s len=%d", utils.mask_id(chat_id), len(reply_text))
    if database.get_bool("monitoring_mode"):
        handlers.notify_owner(i18n.t(
            "biz.notify.auto_replied",
            name=utils.escape(business_service.customer_display_name(bcid, chat_id)),
            text=utils.escape(customer_text[:200]),
            reply=utils.escape(reply_text[:500]),
        ))


def _notify_incoming(bcid: str, chat_id: int, text: str) -> None:
    handlers.notify_owner(i18n.t(
        "biz.notify.incoming",
        name=utils.escape(business_service.customer_display_name(bcid, chat_id)),
        chat_id=chat_id,
        text=utils.escape(text[:500]),
    ))


def _handle_non_text(conn, message) -> None:
    """Media/voice in a direct chat: never auto-answer (unless an ack is set)."""
    bcid = conn["business_connection_id"]
    chat_id = message.chat.id
    content_type = getattr(message, "content_type", "unknown")
    ack = (database.get_str("nontext_ack_message") or "").strip()
    if database.get_bool("monitoring_mode"):
        name = business_service.customer_display_name(bcid, chat_id)
        handlers.notify_owner(i18n.t(
            "biz.notify.nontext",
            name=utils.escape(name), type=utils.escape(content_type), chat_id=chat_id,
            suffix=i18n.t("biz.notify.nontext_ack") if ack else "",
        ))
    message_id = getattr(message, "message_id", None)
    if not ack or database.message_exists(bcid, chat_id, message_id, "in"):
        return
    if business_service.is_chat_paused(bcid, chat_id) or not _any_automation_on():
        return
    database.insert_message(bcid, chat_id, message_id, "in", "user", f"[{content_type}]")
    if database.get_bool("approval_mode_enabled") or not (conn["is_enabled"] and conn["can_reply"]):
        approvals.create_request(conn, message, f"[{content_type}]", ack, sensitive=False)
    else:
        _deliver_auto(conn, chat_id, message_id, f"[{content_type}]", ack)


def _send_welcome(conn, chat_id: int) -> None:
    bcid = conn["business_connection_id"]
    text = (database.get_str("welcome_text") or "").strip() or i18n.t("biz.welcome_default")
    if not (conn["is_enabled"] and conn["can_reply"]):
        return
    try:
        telegram_api.send_reply(handlers.bot, chat_id, text, business_connection_id=bcid)
        database.insert_message(bcid, chat_id, None, "out", "assistant", text)
        log.info("welcomed new direct chat=%s", utils.mask_id(chat_id))
    except Exception:
        log.warning("could not send the welcome message", exc_info=True)


def _any_automation_on() -> bool:
    return database.get_bool("auto_reply_enabled") or database.get_bool("approval_mode_enabled")


def _is_first_inbound(bcid: str, chat_id: int) -> bool:
    try:
        return database.count_messages_in_window(
            bcid, chat_id, utils.future_iso(-60 * 24 * 365 * 20), direction="in"
        ) == 1
    except Exception:
        return False

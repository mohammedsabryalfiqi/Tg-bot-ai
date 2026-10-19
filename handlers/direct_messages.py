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
from handlers import approvals, gates as gate_handler
from services import (
    ai_service,
    batching,
    business_service,
    gate_service,
    memory_service,
    prompt_service,
    providers,
    rate_limit_service,
    rules_service,
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
        # In OFF mode, do not emit even a subscription/payment prompt or media
        # acknowledgement to the customer.
        if not _any_automation_on():
            _handle_non_text(conn, message)
            return
        # Media must not bypass entry gates (a paid media-only message is not
        # supported by the text invoice pipeline).
        if gate_service.subscription_enabled():
            if not gate_service.channels():
                handlers.bot.send_message(chat_id, i18n.t("gate.user.unavailable"))
                return
            missing = gate_service.missing_channels(sender_id)
            if missing:
                _ask_to_subscribe(chat_id, missing)
                return
        if gate_service.payments_enabled():
            handlers.bot.send_message(chat_id, i18n.t("gate.user.text_required"))
            return
        _handle_non_text(conn, message)
        return

    message_id = getattr(message, "message_id", None)
    if database.message_exists(bcid, chat_id, message_id, "in"):
        log.info("duplicate direct message %s ignored", message_id)
        return

    # OFF mode is a hard stop: retain the inbound/monitoring record, but do not
    # run entry gates (which would still send a customer-facing prompt).
    if not _any_automation_on():
        database.insert_message(bcid, chat_id, message_id, "in", "user", text)
        if database.get_bool("monitoring_mode"):
            _notify_incoming(bcid, chat_id, text)
        return

    # Entry gates run *before* the message is stored or answered: until the
    # person has joined the channels (or paid), the message never reaches the
    # account owner. Business chats never come through here.
    was_gated = _entry_gates(bcid, chat_id, sender_id, message, text)
    if was_gated is False:                      # held at a gate
        return
    gated = was_gated or None

    database.insert_message(bcid, chat_id, message_id, "in", "user", text)

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
        # Greet, then keep going: the message that opened the chat still
        # deserves an answer (same behaviour as the business pipeline).
        _send_welcome(conn, chat_id)

    batch = batching.batcher.process((bcid, chat_id), message_id, text)
    if batch is None:                           # covered by an in-flight batch
        return
    combined_text = "\n".join(t for _mid, t in batch).strip()
    if not combined_text:
        return
    first_message_id = batch[0][0] if batch else message_id
    _answer(conn, message, chat_id, first_message_id, combined_text, gated=gated)


def _answer(conn, message, chat_id: int, customer_message_id, customer_text: str,
            *, gated: dict | None = None) -> None:
    """Generate (or draft) the reply for one customer message."""
    bcid = conn["business_connection_id"]
    with telegram_api.typing_keepalive(
        handlers.bot, chat_id,
        business_connection_id=bcid,
        enabled=database.get_bool("typing_indicator"),
    ):
        reply_text = _generate_reply(conn, chat_id, customer_text)
    if not reply_text:
        return

    # "I don't know": answer nothing but ask the team, and file the question so
    # the owner can answer it once and have it learned (see handlers/unanswered).
    if rules_service.is_no_answer(reply_text):
        _handle_unknown(bcid, chat_id, customer_text)
        return

    reply_text = prompt_service.apply_signature(reply_text)
    sensitive = prompt_service.is_sensitive(customer_text)
    force_approval = sensitive and database.get_bool("sensitive_requires_approval")

    if database.get_bool("approval_mode_enabled") or force_approval:
        approvals.create_request(conn, message, customer_text, reply_text, sensitive=sensitive)
    else:
        _deliver_auto(conn, chat_id, customer_message_id, customer_text, reply_text)

    if gated:
        _copy_gated_to_owner(bcid, chat_id, customer_text, reply_text, gated)


# =============================================================================
# Entry gates (private messages only)
# =============================================================================
def _entry_gates(bcid: str, chat_id: int, user_id, message, text: str):
    """Run both gates before the message is answered.

    Returns ``False`` when the message was held back (the person must join the
    channels or pay first), ``None`` when no gate applies, otherwise a dict
    describing the gate that let the message through (used for the owner copy).
    """
    if not user_id:
        return False if (gate_service.subscription_enabled()
                         or gate_service.payments_enabled()) else None

    subscription_fresh = False
    if gate_service.subscription_enabled():
        if not gate_service.channels():
            handlers.bot.send_message(chat_id, i18n.t("gate.user.unavailable"))
            return False
        verified = gate_service.was_verified_before(user_id)
        missing = gate_service.missing_channels(user_id)
        if missing:
            _ask_to_subscribe(chat_id, missing)
            return False
        # Just joined: this is the first message that got through the gate, so
        # it is the one the owner gets a copy of.
        subscription_fresh = not verified

    if gate_service.payments_enabled():
        free = gate_service.park_message(user_id, chat_id, text, free=True)
        if free is not None:
            left = gate_service.free_left(user_id)
            if left == 0:
                try:
                    handlers.bot.send_message(chat_id, gate_service.free_last_notice())
                except Exception:
                    log.debug("could not send the last-free-message notice", exc_info=True)
            return {"kind": "free", "stars": 0, "left": left}
        # An enabled gate without a valid price is closed, not free.
        if gate_service.stars_price() <= 0:
            handlers.bot.send_message(chat_id, i18n.t("gate.user.payment_unavailable"))
            return False
        if not gate_handler.request_payment(chat_id, user_id, text):
            log.warning("could not ask chat=%s for the star payment", utils.mask_id(chat_id))
        return False

    if subscription_fresh:
        return {"kind": "subscription", "stars": 0}
    return None


def _ask_to_subscribe(chat_id: int, missing: list) -> None:
    names = "\n".join(f"• {utils.escape(row['title'] or row['chat_ref'])}" for row in missing)
    markup = keyboards.subscription_gate()
    try:
        handlers.bot.send_message(chat_id, i18n.t("gate.user.sub", list=names),
                                  parse_mode="HTML", reply_markup=markup)
    except Exception:
        log.warning("could not send the subscription prompt chat=%s",
                    utils.mask_id(chat_id), exc_info=True)


def _handle_unknown(bcid: str, chat_id: int, customer_text: str) -> None:
    """The assistant had no answer: say so politely and file the question."""
    if not database.get_bool("unanswered_enabled"):
        return
    try:
        telegram_api.send_reply(handlers.bot, chat_id,
                               i18n.t("unans.auto_reply"),
                               business_connection_id=bcid)
        database.insert_message(bcid, chat_id, None, "out", "assistant",
                                i18n.t("unans.auto_reply"))
    except Exception:
        log.warning("could not send the no-answer notice chat=%s",
                    utils.mask_id(chat_id), exc_info=True)
    question_id = rules_service.record_unanswered(bcid, chat_id, customer_text)
    if question_id:
        from handlers import unanswered as unanswered_handler
        unanswered_handler.notify_owner(question_id, bcid, chat_id, customer_text)


def _copy_gated_to_owner(bcid: str, chat_id: int, customer_text: str, reply_text: str,
                         gated: dict) -> None:
    """Copy a gated conversation to the owner (switchable in /settings)."""
    if not database.get_bool("gate_copy_to_owner"):
        return
    name = business_service.customer_display_name(bcid, chat_id)
    markup = None
    if gated.get("paid_message_id"):
        markup = keyboards.paid_message_actions(gated["paid_message_id"])
    handlers.notify_owner(i18n.t(
        "gate.owner.copy",
        stars=gated.get("stars", 0),
        name=utils.escape(name),
        chat_id=chat_id,
        text=utils.escape(customer_text[:1200]),
        reply=utils.escape(reply_text[:1200]),
    ), reply_markup=markup)


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


def process_paid_message(row: dict) -> bool:
    """Deliver a message whose Telegram Stars payment just landed.

    Same pipeline as any other message (history, memory, drafting,
    signature), minus batching and rate limiting: the person already paid, so
    the message is answered now. Works for both direct messages and linked
    Telegram Business account chats.
    """
    tenant = row.get("tenant_id", 0) if isinstance(row, dict) else 0
    with database.tenant_scope(tenant):
        try:
            return _process_paid_scoped(row)
        except Exception:
            log.exception("paid-message delivery crashed (swallowed)")
            return False


def _process_paid_scoped(row: dict) -> bool:
    chat_id = int(row["customer_chat_id"] or 0)
    text = (row["message_text"] or "").strip()
    if not chat_id or not text:
        return False

    bcid = row.get("business_connection_id")
    is_biz = bool(bcid)
    if not is_biz:
        bcid = business_service.ensure_direct_connection()

    conn = business_service.get_connection(bcid)
    if conn is None or not conn["is_enabled"]:
        return False
    if not _any_automation_on():
        handlers.notify_owner(i18n.t(
            "gate.pay.off", chat_id=chat_id, text=utils.escape(text[:800])
        ))
        return False
    if not ai_service.is_ready():
        handlers.notify_owner(i18n.t("gate.pay.failed"))
        return False

    try:
        telegram_api.send_reply(handlers.bot, chat_id, i18n.t("gate.pay.done"),
                                business_connection_id=bcid if is_biz else None)
    except Exception:
        log.debug("could not send the payment confirmation", exc_info=True)

    database.insert_message(bcid, chat_id, None, "in", "user", text)
    gated = {"kind": "paid", "stars": int(row["stars"] or 0),
             "paid_message_id": int(row["id"])}
    with telegram_api.typing_keepalive(
        handlers.bot, chat_id,
        business_connection_id=bcid,
        enabled=database.get_bool("typing_indicator"),
    ):
        reply_text = _generate_reply(conn, chat_id, text)
    if not reply_text:
        return False
    if rules_service.is_no_answer(reply_text):
        _handle_unknown(bcid, chat_id, text)
        return True
    reply_text = prompt_service.apply_signature(reply_text)
    if database.get_bool("approval_mode_enabled"):
        message = _synthetic_message(chat_id, text)
        approvals.create_request(conn, message, text, reply_text, sensitive=False)
    else:
        _deliver_auto(conn, chat_id, None, text, reply_text)
    _copy_gated_to_owner(bcid, chat_id, text, reply_text, gated)
    return True


def _synthetic_message(chat_id: int, text: str):
    """A minimal Message so draft-mode approvals still get a chat/message id."""
    from telebot import types

    chat = types.Chat(chat_id, "private")
    user = types.User(chat_id, False, "customer")
    return types.Message(0, user, 0, chat, "text", {"text": text})


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
    """The auto-reply switch is the master; approval only selects draft mode."""
    return database.get_bool("auto_reply_enabled")


def _is_first_inbound(bcid: str, chat_id: int) -> bool:
    try:
        return database.count_messages_in_window(
            bcid, chat_id, utils.future_iso(-60 * 24 * 365 * 20), direction="in"
        ) == 1
    except Exception:
        return False

"""Entry gates: forced subscription and Telegram Stars paid messages (`/gate`).

Both gates are **off by default** and only ever applied to the direct-message
pipeline — a Telegram Business customer chat keeps working exactly as before.

Screens
-------
* `/gate` — the menu: subscription, Stars price, what is required right now.
* ``gate:sub`` — toggle the join-check, list/add/remove the required channels.
* ``gate:stars`` — toggle paid messages, type the price (the admin types the
  number), set how many free messages a person gets first.

Payments
--------
Telegram Stars needs three things wired together, all handled here:

1. ``sendInvoice`` (``telegram_api.send_star_invoice``) when a gated message
   arrives — the invoice carries our payload so the payment can be matched back;
2. ``pre_checkout_query`` — answer *ok* within 10 seconds or the star refunds;
3. ``successful_payment`` — deliver the parked message and copy it to the owner.
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
from services import gate_service

log = logging.getLogger("smartel.gate_handler")

PENDING_TTL_MINUTES = 15
CHANNEL_KIND = "gate_channel"
PRICE_KIND = "gate_price"
FREE_KIND = "gate_free"


def register(bot, cfg) -> None:
    def cmd(commands, function):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=function):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["gate", "gates", "subscribe"], cmd_menu)

    # Owner-facing screens. `gate:verify` is pressed by *visitors* and is
    # handled below — TeleBot runs only the first matching handler, so it must
    # not match here (the owner check would swallow it).
    @bot.callback_query_handler(
        func=lambda c: bool(c.data) and c.data.startswith("gate:")
        and c.data != "gate:verify")
    @security.owner_only_callback
    def _gate_cb(call):
        _safe(lambda: on_callback(call))

    # Visitors press this one (no owner check): re-check their membership.
    @bot.callback_query_handler(func=lambda c: c.data == "gate:verify")
    def _verify_cb(call):
        _safe(lambda: on_verify(call))

    # Visitors press this one to reopen their Stars invoice.
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("pay:"))
    def _pay_cb(call):
        _safe(lambda: on_pay_callback(call))

    @bot.pre_checkout_query_handler(func=lambda q: True)
    def _pre_checkout(query):
        _safe(lambda: on_pre_checkout(query))

    @bot.message_handler(content_types=["successful_payment"])
    def _paid(message):
        _safe(lambda: on_successful_payment(message))


def _safe(action) -> None:
    try:
        action()
    except Exception:
        log.exception("gate handler failed (swallowed)")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Menu
# =============================================================================
def menu_text() -> str:
    lines = [i18n.t("gate.title"), "", i18n.t("gate.body"), ""]
    lines += gate_service.summary_lines()
    lines += ["", i18n.t("gate.hint")]
    return "\n".join(lines)


def cmd_menu(message) -> None:
    handlers.bot.send_message(message.chat.id, menu_text(), parse_mode="HTML",
                              reply_markup=keyboards.gate_menu(gate_service.summary()))


def sub_text() -> str:
    lines = [i18n.t("gate.sub.title"), "", i18n.t("gate.sub.body"), ""]
    rows = database.list_required_channels()
    if rows:
        for row in rows:
            icon = "✅" if row["enabled"] else "⏸"
            kind = i18n.t("gate.sub.group") if row["kind"] == "group" else i18n.t("gate.sub.channel")
            lines.append(f"{icon} #{row['id']} {utils.escape(row['title'] or row['chat_ref'])}"
                         f" — {kind} · <code>{utils.escape(row['chat_ref'])}</code>")
    else:
        lines.append(i18n.t("gate.sub.empty"))
    lines += ["", i18n.t("gate.sub.add_hint", state=i18n.t("set.value.on")
                         if gate_service.subscription_enabled()
                         else i18n.t("set.value.off"))]
    return "\n".join(lines)


def stars_text() -> str:
    lines = [i18n.t("gate.stars.title"), "", i18n.t("gate.stars.body"), ""]
    lines.append(i18n.t("gate.stars.enabled",
                        state=i18n.t("set.value.on") if gate_service.payments_enabled()
                        else i18n.t("set.value.off")))
    lines.append(i18n.t("gate.stars.price", stars=gate_service.stars_price()))
    lines.append(i18n.t("gate.stars.free", count=gate_service.free_quota()))
    lines.append(i18n.t("gate.stars.earned", count=database.count_paid_messages(status="paid"),
                        stars=database.sum_stars_earned()))
    if database.get_bool("paid_messages_enabled") and gate_service.stars_price() <= 0:
        lines += ["", i18n.t("gate.stars.need_price")]
    lines += ["", i18n.t("gate.stars.hint")]
    return "\n".join(lines)


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    argument = parts[2] if len(parts) > 2 else ""

    if action == "root":
        _edit_or_send(call, menu_text(), keyboards.gate_menu(gate_service.summary()))
        return telegram_api.answer_callback(bot, call.id)

    if action == "sub":
        _edit_or_send(call, sub_text(), keyboards.required_channels(
            database.list_required_channels()))
        return telegram_api.answer_callback(bot, call.id)

    if action == "stars":
        _edit_or_send(call, stars_text(), _stars_markup())
        return telegram_api.answer_callback(bot, call.id)

    if action == "list":
        _edit_or_send(call, list_text(), keyboards.gate_menu(gate_service.summary()))
        return telegram_api.answer_callback(bot, call.id)

    if action == "toggle_sub":
        state = not database.get_bool("require_subscription_enabled")
        database.set_setting("require_subscription_enabled", state)
        database.clear_gate_checks()
        telegram_api.answer_callback(
            bot, call.id,
            i18n.t("gate.sub.on_alert") if state else i18n.t("gate.sub.off_alert"))
        return _edit_or_send(call, sub_text(),
                             keyboards.required_channels(database.list_required_channels()))

    if action == "toggle_stars":
        state = not database.get_bool("paid_messages_enabled")
        database.set_setting("paid_messages_enabled", state)
        alert = i18n.t("gate.stars.on_alert") if state else i18n.t("gate.stars.off_alert")
        if state and gate_service.stars_price() <= 0:
            alert = i18n.t("gate.stars.need_price")
        telegram_api.answer_callback(bot, call.id, alert)
        return _edit_or_send(call, stars_text(), _stars_markup())

    if action == "price":
        _ask(call, PRICE_KIND, i18n.t("gate.price.ask"))
        return

    if action == "free":
        _ask(call, FREE_KIND, i18n.t("gate.free.ask"))
        return

    if action == "add_channel":
        _ask(call, CHANNEL_KIND, i18n.t("gate.sub.ask"))
        return

    if action == "toggle_channel" and argument.isdigit():
        enabled = gate_service.toggle_channel(int(argument))
        telegram_api.answer_callback(
            bot, call.id,
            i18n.t("gate.sub.row_on") if enabled else i18n.t("gate.sub.row_off"))
        return _edit_or_send(call, sub_text(),
                             keyboards.required_channels(database.list_required_channels()))

    if action == "refund" and argument.isdigit():
        row = database.get_paid_message(int(argument))
        if row is None:
            return telegram_api.answer_callback(bot, call.id, i18n.t("gate.refund_missing"),
                                                show_alert=True)
        sent = telegram_api.refund_star_payment(row["user_id"] or row["customer_chat_id"],
                                               row["charge_id"] or "")
        database.set_paid_message_status(int(argument), "refunded")
        telegram_api.answer_callback(
            bot, call.id,
            i18n.t("gate.refunded") if sent else i18n.t("gate.refunded_local"),
            show_alert=not sent)
        return

    if action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


def _stars_markup():
    from telebot import types

    from keyboards import cb
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(
        i18n.t("kbd.gate.stars_toggle"), callback_data=cb("gate", "toggle_stars")))
    kb.add(types.InlineKeyboardButton(
        i18n.t("kbd.gate.price"), callback_data=cb("gate", "price")))
    kb.add(types.InlineKeyboardButton(
        i18n.t("kbd.gate.free"), callback_data=cb("gate", "free")))
    kb.add(types.InlineKeyboardButton(
        i18n.t("kbd.back"), callback_data=cb("gate", "root")))
    kb.add(types.InlineKeyboardButton(
        i18n.t("kbd.close"), callback_data=cb("gate", "close")))
    return kb


def list_text() -> str:
    lines = [i18n.t("gate.list.title"), ""]
    lines += gate_service.summary_lines()
    rows = database.list_paid_messages(limit=5)
    if rows:
        lines += ["", i18n.t("gate.list.payments")]
        for row in rows:
            lines.append(i18n.t("gate.list.payment_row", id=row["id"],
                                chat_id=row["customer_chat_id"], stars=row["stars"],
                                status=row["status"]))
    return "\n".join(lines)


def _ask(call, kind: str, text: str) -> None:
    database.set_owner_pending_input(security.operator_id(), kind, {}, PENDING_TTL_MINUTES)
    telegram_api.answer_callback(handlers.bot, call.id, i18n.t("gate.cb.type"))
    handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML")


# =============================================================================
# Asking a visitor to pay (shared gate: public callback above)
# =============================================================================
def on_pay_callback(call) -> None:
    """Re-open the invoice for a message that is still waiting for payment."""
    bot = handlers.bot
    parts = (call.data or "").split(":", 2)
    payload = parts[2] if len(parts) > 2 else ""
    row = database.get_paid_message_by_payload(payload)
    if row is None or row["status"] != "pending":
        return telegram_api.answer_callback(bot, call.id, i18n.t("gate.pay.expired"),
                                           show_alert=True)
    stars = int(row["stars"] or 0)
    sent = telegram_api.send_star_invoice(
        row["customer_chat_id"],
        title=i18n.t("gate.invoice.title", name=(database.get_str("business_name") or "").strip()
                     or i18n.t("gate.invoice.default_title")),
        description=i18n.t("gate.invoice.desc", stars=stars),
        payload=payload, stars=stars, label=i18n.t("gate.invoice.label"),
    )
    if sent is None:
        return telegram_api.answer_callback(bot, call.id, i18n.t("gate.pay.failed"),
                                            show_alert=True)
    telegram_api.answer_callback(bot, call.id)


def on_verify(call) -> None:
    """The visitor says they joined: re-check (bypassing the cache) and answer."""
    user_id = getattr(getattr(call, "from_user", None), "id", None)
    bot = handlers.bot
    if not user_id:
        return telegram_api.answer_callback(bot, call.id)
    if not gate_service.subscription_enabled():
        # Nothing to check (the gate was switched off meanwhile): say it is fine
        # rather than leaving the visitor staring at a dead button.
        return telegram_api.answer_callback(bot, call.id, i18n.t("gate.user.sub_ok"))
    missing = gate_service.missing_channels(user_id, force=True)
    if not missing:
        telegram_api.answer_callback(bot, call.id, i18n.t("gate.user.sub_ok"))
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=None)
        except Exception:
            log.debug("could not drop the verify buttons", exc_info=True)
        return
    names = "\n".join(f"• {utils.escape(row['title'] or row['chat_ref'])}" for row in missing)
    try:
        bot.send_message(call.message.chat.id,
                         i18n.t("gate.user.still_missing", list=names),
                         parse_mode="HTML", reply_markup=keyboards.subscription_gate())
    except Exception:
        log.debug("could not send the still-missing notice", exc_info=True)
    telegram_api.answer_callback(bot, call.id, i18n.t("gate.user.still_missing_alert"))


def request_payment(chat_id: int, user_id: int, text: str) -> bool:
    """Park the message and invoice the person for it (Stars).

    Returns True when the invoice was sent — the caller then stops: the message
    is only delivered by :func:`on_successful_payment`, once Telegram confirms.
    """
    stars = gate_service.stars_price()
    if stars <= 0:
        return False
    row = gate_service.park_message(user_id, chat_id, text, stars=stars)
    if row is None:
        return False
    prompt = i18n.t("gate.user.pay", stars=stars)
    markup = keyboards.pay_button(stars, row["payload"])
    sent = telegram_api.send_star_invoice(
        chat_id,
        title=i18n.t("gate.invoice.title", name=(database.get_str("business_name") or "").strip()
                     or i18n.t("gate.invoice.default_title")),
        description=i18n.t("gate.invoice.desc", stars=stars),
        payload=row["payload"],
        stars=stars,
        label=i18n.t("gate.invoice.label"),
    )
    if sent is None:
        # No invoice -> do not keep the message parked forever.
        database.set_paid_message_status(row["id"], "failed")
        return False
    try:
        handlers.bot.send_message(chat_id, prompt, parse_mode="HTML", reply_markup=markup)
    except Exception:
        log.debug("could not send the payment prompt", exc_info=True)
    log.info("stars invoice sent to chat=%s (%s stars)", utils.mask_id(chat_id), stars)
    return True


# =============================================================================
# Pending inputs (the admin types the value)
# =============================================================================
def apply_pending(message, kind: str, context: dict) -> None:
    text = (getattr(message, "text", "") or "").strip()
    chat_id = message.chat.id

    if kind == PRICE_KIND:
        if not text.isdigit():
            return handlers.bot.send_message(chat_id, i18n.t("gate.price.bad"))
        price = int(text)
        if price <= 0 or price > gate_service.MAX_STARS:
            return handlers.bot.send_message(
                chat_id, i18n.t("gate.price.range", max=gate_service.MAX_STARS))
        database.set_setting("paid_message_stars", price)
        database.set_setting("paid_messages_enabled", True)
        return handlers.bot.send_message(
            chat_id, i18n.t("gate.price.saved", stars=price), parse_mode="HTML")

    if kind == FREE_KIND:
        if not text.isdigit():
            return handlers.bot.send_message(chat_id, i18n.t("gate.free.bad"))
        database.set_setting("paid_message_free_count", int(text))
        return handlers.bot.send_message(chat_id, i18n.t("gate.free.saved", count=text))

    if kind == CHANNEL_KIND:
        return _save_channel(chat_id, text)


def _save_channel(chat_id: int, text: str) -> None:
    """``@username`` or ``-100…`` — the title/kind are fetched when possible."""
    if not text:
        return handlers.bot.send_message(chat_id, i18n.t("gate.sub.ask"))
    parts = [part.strip() for part in text.split("|")]
    ref = parts[0]
    title = parts[1] if len(parts) > 1 else ""
    link = parts[2] if len(parts) > 2 else ""
    lookup = ref if ref.startswith("@") or ref.lstrip("-").isdigit() else f"@{ref}"
    info = telegram_api.get_chat(lookup) or {}
    title = title or info.get("title") or ref
    link = link or info.get("invite_link") or ""
    kind = "group" if str(info.get("type", "")).lower() in ("group", "supergroup") else "channel"
    channel_id = gate_service.add_channel(lookup, title=title, invite_link=link, kind=kind)
    handlers.bot.send_message(
        chat_id,
        i18n.t("gate.sub.saved", id=channel_id, title=utils.escape(title),
               ref=utils.escape(lookup)),
        parse_mode="HTML",
        reply_markup=keyboards.required_channels(database.list_required_channels()),
    )


# =============================================================================
# Payments
# =============================================================================
def on_pre_checkout(query) -> None:
    """Approve a Stars payment; Telegram refunds it if we answer ``ok=False``."""
    payload = getattr(query, "invoice_payload", "") or ""
    row = database.get_paid_message_by_payload(payload)
    if row is None or row["status"] != "pending":
        return telegram_api.answer_pre_checkout_query(query.id, False,
                                                      i18n.t("gate.pay.expired"))
    telegram_api.answer_pre_checkout_query(query.id, True)


def on_successful_payment(message) -> None:
    payment = getattr(message, "successful_payment", None)
    payload = getattr(payment, "invoice_payload", "") or ""
    charge_id = getattr(payment, "telegram_payment_charge_id", "") or ""
    row = gate_service.confirm_payment(payload, charge_id)
    if row is None:
        log.info("payment for an unknown payload ignored")
        return
    deliver_paid_message(row)


def deliver_paid_message(row: dict) -> bool:
    """Run the parked message through the pipeline and copy it to the owner."""
    from handlers import direct_messages

    delivered = direct_messages.process_paid_message(row)
    if delivered:
        gate_service.mark_delivered(row["id"])
    return delivered


def _edit_or_send(call, text: str, markup=None) -> None:
    try:
        handlers.bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                       parse_mode="HTML", reply_markup=markup)
        return
    except Exception:
        log.debug("could not edit the gate message; sending a new one", exc_info=True)
    handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                              reply_markup=markup)


PENDING_KINDS = {PRICE_KIND: apply_pending, FREE_KIND: apply_pending,
                 CHANNEL_KIND: apply_pending}

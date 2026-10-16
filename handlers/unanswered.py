"""Unanswered questions — the assistant's homework.

When the model cannot answer, it replies with ``NO_ANSWER`` (see
``services/rules_service``). The pipeline then:

1. tells the person "I passed it to the team" (localised),
2. stores the question,
3. notifies the owner with the question and a button.

The owner's answer is sent to the person who asked **and** stored as a quick
answer (FAQ), so the next identical question never needs the AI again. This
module owns that flow: `/unanswered`, the ``unans:*`` buttons and the parked
"answer this question" input.
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
from services import rules_service

log = logging.getLogger("smartel.unanswered_handler")

PER_PAGE = 5
PENDING_TTL_MINUTES = 30
ANSWER_KIND = "unans_answer"


def register(bot, cfg) -> None:
    def cmd(commands, function):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=function):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["unanswered", "questions"], cmd_menu)
    cmd(["unanswered_clear"], cmd_clear)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("unans:"))
    @security.owner_only_callback
    def _unans_cb(call):
        _safe(lambda: on_callback(call))


def _safe(action) -> None:
    try:
        action()
    except Exception:
        log.exception("unanswered handler failed (swallowed)")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Screens
# =============================================================================
def cmd_menu(message) -> None:
    send_list(message.chat.id)


def send_list(chat_id: int, page: int = 0, call=None) -> None:
    rows = rules_service.open_questions(limit=50)
    if not rows:
        text = i18n.t("unans.menu.title") + "\n\n" + i18n.t("unans.menu.none")
        if call is None:
            return handlers.bot.send_message(chat_id, text, parse_mode="HTML")
        telegram_api.answer_callback(handlers.bot, call.id, i18n.t("unans.menu.none"))
        return _edit_or_send(call, text, None)

    lines = [i18n.t("unans.menu.title"), "",
             i18n.t("unans.menu.count", count=len(rows)), ""]
    for row in rows[page * PER_PAGE:page * PER_PAGE + PER_PAGE]:
        question = utils.escape((row["question"] or "")[:120])
        lines.append(i18n.t("unans.row", id=row["id"], question=question))
    lines += ["", i18n.t("unans.menu.hint")]
    markup = keyboards.unanswered_list(rows, page, PER_PAGE)
    if call is None:
        handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML",
                                  reply_markup=markup)
    else:
        _edit_or_send(call, "\n".join(lines), markup)


def cmd_clear(message) -> None:
    count = database.count_unanswered("open")
    if not count:
        return handlers.bot.send_message(message.chat.id, i18n.t("unans.menu.none"))
    handlers.bot.send_message(message.chat.id, i18n.t("unans.clear.ask", count=count),
                              parse_mode="HTML", reply_markup=keyboards.confirm("unansclear"))


# =============================================================================
# Owner notification + answering
# =============================================================================
def notify_owner(question_id: int, business_connection_id: str, customer_chat_id: int,
                 question: str) -> None:
    """Tell the owner about a question the assistant could not answer."""
    from services import business_service

    name = business_service.customer_display_name(business_connection_id, customer_chat_id)
    handlers.notify_owner(
        i18n.t("unans.notify", name=utils.escape(name), chat_id=customer_chat_id,
               question=utils.escape(question[:400])),
        reply_markup=keyboards.unanswered_card(question_id),
    )


def ask_for_answer(chat_id: int, question_id: int) -> None:
    database.set_owner_pending_input(security.operator_id(), ANSWER_KIND,
                                     {"id": question_id}, PENDING_TTL_MINUTES)
    handlers.bot.send_message(chat_id, i18n.t("unans.ask", id=question_id),
                              parse_mode="HTML")


def apply_pending(message, kind: str, context: dict) -> None:
    """The owner's reply to a question: deliver it, learn it, close it."""
    if kind != ANSWER_KIND:
        return
    chat_id = message.chat.id
    question_id = int(context.get("id") or 0)
    answer = (getattr(message, "text", "") or "").strip()
    if not answer:
        return handlers.bot.send_message(chat_id, i18n.t("unans.empty_answer"))

    row = database.get_unanswered(question_id)
    if row is None or row["status"] != "open":
        return handlers.bot.send_message(chat_id, i18n.t("unans.gone"))

    result = rules_service.answer_question(question_id, answer)
    if result is None:
        return handlers.bot.send_message(chat_id, i18n.t("unans.gone"))

    delivered = _deliver(row, answer)
    faq_id = result.get("faq_id")
    if delivered and faq_id:
        text = i18n.t("unans.answered_learned", faq=str(faq_id))
    elif delivered:
        text = i18n.t("unans.answered", id=question_id)
    else:
        text = i18n.t("unans.answered_not_sent")
    handlers.bot.send_message(chat_id, text)


def _deliver(row, answer: str) -> bool:
    """Send the owner's answer to whoever asked the question."""
    target = row["customer_chat_id"]
    if not target:
        return False
    try:
        telegram_api.send_reply(
            handlers.bot, target, answer,
            business_connection_id=row["business_connection_id"],
        )
    except Exception:
        log.warning("could not deliver the learned answer to chat=%s",
                    utils.mask_id(target), exc_info=True)
        return False
    try:
        database.insert_message(row["business_connection_id"], target, None, "out",
                                "assistant", answer)
    except Exception:                      # pragma: no cover - history is best effort
        log.debug("could not store the learned answer in the history", exc_info=True)
    return True


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    argument = parts[2] if len(parts) > 2 else ""
    chat_id = call.message.chat.id

    if action == "list":
        page = int(argument) if argument.isdigit() else 0
        send_list(chat_id, page=page, call=call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "open" and argument.isdigit():
        row = database.get_unanswered(int(argument))
        if row is None:
            return telegram_api.answer_callback(bot, call.id, i18n.t("unans.gone"))
        from services import business_service
        name = business_service.customer_display_name(row["business_connection_id"] or "",
                                                      row["customer_chat_id"] or 0)
        _edit_or_send(
            call,
            i18n.t("unans.card", id=row["id"], name=utils.escape(name),
                   chat_id=row["customer_chat_id"], when=utils.fmt_dt(row["created_at"]),
                   question=utils.escape(row["question"] or "")),
            keyboards.unanswered_card(row["id"]),
        )
        return telegram_api.answer_callback(bot, call.id)

    if action == "answer" and argument.isdigit():
        ask_for_answer(chat_id, int(argument))
        return telegram_api.answer_callback(bot, call.id, i18n.t("unans.asked"))

    if action == "ignore" and argument.isdigit():
        rules_service.ignore_question(int(argument))
        telegram_api.answer_callback(bot, call.id, i18n.t("unans.ignored"))
        return send_list(chat_id, page=0, call=call)

    if action == "close":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


def _edit_or_send(call, text: str, markup=None) -> None:
    try:
        handlers.bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                       parse_mode="HTML", reply_markup=markup)
        return
    except Exception:
        log.debug("could not edit the unanswered message; sending a new one", exc_info=True)
    handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                              reply_markup=markup)


PENDING_KINDS = {ANSWER_KIND: apply_pending}

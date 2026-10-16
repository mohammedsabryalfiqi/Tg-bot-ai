"""Resources — websites, platforms, Telegram groups and channels the bot uses.

`/resources` opens the menu; sending a link (or plain text) adds it:
the page is fetched into the knowledge base and the link is kept as a reference
the assistant may hand out. `/resources_list` shows the toggles, so a resource
can be paused without deleting it.
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
from services import resource_service

log = logging.getLogger("smartel.resources_handler")

PENDING_TTL_MINUTES = 15


def register(bot, cfg) -> None:
    def cmd(commands, function):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=function):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["resources", "res"], cmd_menu)
    cmd(["resources_add", "res_add"], cmd_add)
    cmd(["resources_list", "res_list"], cmd_list)
    cmd(["resources_del", "res_del"], cmd_delete)
    cmd(["resources_clear", "res_clear"], cmd_clear)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("res:"))
    @security.owner_only_callback
    def _res_cb(call):
        _safe(lambda: on_callback(call))


def _safe(action) -> None:
    try:
        action()
    except Exception:
        log.exception("resources handler failed (swallowed)")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Screens
# =============================================================================
def menu_text() -> str:
    rows = database.list_resources()
    lines = [i18n.t("res.menu.title"), "", i18n.t("res.menu.body"), ""]
    if rows:
        counts = {kind: len([r for r in rows if r["kind"] == kind])
                  for kind in ("link", "telegram", "text")}
        lines.append(i18n.t("res.menu.count", count=len(rows),
                            telegram=counts["telegram"], links=counts["link"]))
    else:
        lines.append(i18n.t("res.menu.empty"))
    if not database.get_bool("resources_enabled"):
        lines += ["", i18n.t("res.disabled")]
    lines += ["", i18n.t("res.menu.hint")]
    return "\n".join(lines)


def cmd_menu(message) -> None:
    handlers.bot.send_message(message.chat.id, menu_text(), parse_mode="HTML",
                              reply_markup=keyboards.resources_menu())


def cmd_add(message) -> None:
    argument = _args(message)
    if argument:
        return add_and_report(message.chat.id, argument)
    database.set_owner_pending_input(security.operator_id(), "res_text", {},
                                     PENDING_TTL_MINUTES)
    handlers.bot.send_message(message.chat.id, i18n.t("res.ask"), parse_mode="HTML")


def cmd_list(message) -> None:
    send_list(message.chat.id)


def send_list(chat_id: int, call=None) -> None:
    rows = database.list_resources()
    if not rows:
        text = i18n.t("res.list.empty")
        if call is None:
            return handlers.bot.send_message(chat_id, text)
        return telegram_api.answer_callback(handlers.bot, call.id, text)
    lines = [i18n.t("res.list.title", count=len(rows)), ""]
    for row in rows:
        lines.append(resource_service.describe(row))
    markup = keyboards.resources_list(rows)
    if call is None:
        handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML",
                                  reply_markup=markup)
    else:
        _edit_or_send(call, "\n".join(lines), markup)


def cmd_delete(message) -> None:
    argument = _args(message)
    if not argument.isdigit():
        return handlers.bot.send_message(message.chat.id, i18n.t("res.usage"))
    resource_id = int(argument)
    if database.delete_resource(resource_id):
        handlers.bot.send_message(message.chat.id, i18n.t("res.deleted", id=resource_id))
    else:
        handlers.bot.send_message(message.chat.id,
                                  i18n.t("res.delete.missing", id=resource_id))


def cmd_clear(message) -> None:
    count = len(database.list_resources())
    if not count:
        return handlers.bot.send_message(message.chat.id, i18n.t("res.list.empty"))
    handlers.bot.send_message(message.chat.id, i18n.t("res.clear.ask", count=count),
                              parse_mode="HTML", reply_markup=keyboards.confirm("resclear"))


# =============================================================================
# Adding
# =============================================================================
def add_and_report(chat_id: int, text: str) -> None:
    added = resource_service.add(text)
    if added is None:
        return handlers.bot.send_message(chat_id, i18n.t("res.empty_input"))

    if added.kind == "telegram":
        body = i18n.t("res.added.telegram", title=utils.escape(added.title),
                      url=utils.escape(added.url))
    elif added.kind == "text":
        body = i18n.t("res.added.text", title=utils.escape(added.title),
                      chars=added.chars)
    else:
        read = (i18n.t("res.added.read", chars=added.chars) if added.fetched
                else i18n.t("res.added.unread"))
        body = i18n.t("res.added.link", title=utils.escape(added.title),
                      url=utils.escape(added.url), read=read)
    handlers.bot.send_message(chat_id, body, parse_mode="HTML",
                              reply_markup=keyboards.resources_menu())


def apply_pending(message, kind: str, context: dict) -> None:
    if kind != "res_text":
        return
    text = (getattr(message, "text", "") or "").strip()
    if not text:
        return handlers.bot.send_message(message.chat.id, i18n.t("res.empty_input"))
    add_and_report(message.chat.id, text)


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    argument = parts[2] if len(parts) > 2 else ""
    chat_id = call.message.chat.id

    if action == "root":
        _edit_or_send(call, menu_text(), keyboards.resources_menu())
        return telegram_api.answer_callback(bot, call.id)

    if action == "add":
        database.set_owner_pending_input(security.operator_id(), "res_text", {},
                                         PENDING_TTL_MINUTES)
        telegram_api.answer_callback(bot, call.id, i18n.t("res.cb.ask"))
        return bot.send_message(chat_id, i18n.t("res.ask"), parse_mode="HTML")

    if action == "list":
        send_list(chat_id, call=call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "toggle" and argument.isdigit():
        enabled = resource_service.toggle(int(argument))
        if enabled is None:
            return telegram_api.answer_callback(bot, call.id, i18n.t("res.delete.missing",
                                                                   id=argument))
        telegram_api.answer_callback(
            bot, call.id,
            i18n.t("res.toggled.on") if enabled else i18n.t("res.toggled.off"))
        return send_list(chat_id, call=call)

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
        log.debug("could not edit the resource message; sending a new one", exc_info=True)
    handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                              reply_markup=markup)


PENDING_KINDS = {"res_text": apply_pending}

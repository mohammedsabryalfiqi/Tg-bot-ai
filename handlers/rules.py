"""Owner instructions as reviewable topic rules — `/rules`.

Flow
----
1. The owner types (or forwards) their instructions: tone, what to say, what
   never to say, prices, delivery, working hours — in their own words.
2. ``rules_service.organize`` asks the AI to split that into small topic rules
   and to list anything it needs clarified. The draft is stored **disabled**.
3. The owner gets the draft with ✅ Approve / ✏️ Edit / 🗑 Discard. Only ✅ makes
   the rules live (``rule:*`` callbacks, or the ``rule_edit`` pending input).

Everything an approved rule says is injected into every system prompt by
``services/prompt_service`` — so the assistant really does follow it.
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

log = logging.getLogger("smartel.rules_handler")

PENDING_TTL_MINUTES = 15
EDIT_INSTRUCTION = "rule_edit"


def register(bot, cfg) -> None:
    def cmd(commands, function):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=function):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["rules", "topics"], cmd_rules)
    cmd(["rules_add"], cmd_rules_add)
    cmd(["rules_list"], cmd_rules_list)
    cmd(["rules_del"], cmd_rules_del)
    cmd(["rules_clear"], cmd_rules_clear)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("rule:"))
    @security.owner_only_callback
    def _rules_cb(call):
        _safe(lambda: on_callback(call))


def _safe(action) -> None:
    """Never let one bad callback/screen kill the polling loop."""
    try:
        action()
    except Exception:
        log.exception("rules handler failed (swallowed)")


def _args(message) -> str:
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Screens
# =============================================================================
def _draft_summary() -> dict:
    drafts = [row for row in database.list_topic_rules(enabled_only=False)
              if not row["enabled"]]
    batches = sorted({row["batch"] for row in drafts if row["batch"]})
    return {"drafts": len(batches)}


def menu_text() -> str:
    data = rules_service.summary()
    counts = _draft_summary()
    lines = [
        i18n.t("rule.menu.title"),
        "",
        i18n.t("rule.menu.body"),
        "",
        i18n.t("rule.menu.stats", rules=data["rules"], drafts=counts["drafts"]),
    ]
    if not database.get_bool("rules_enabled"):
        lines += ["", i18n.t("rule.disabled")]
    lines += ["", i18n.t("rule.menu.hint", unanswered=data["unanswered"])]
    return "\n".join(lines)


def cmd_rules(message) -> None:
    handlers.bot.send_message(message.chat.id, menu_text(), parse_mode="HTML",
                              reply_markup=keyboards.rules_menu())


def cmd_rules_add(message) -> None:
    argument = _args(message)
    if argument:
        return _organize_and_send(message.chat.id, argument)
    database.set_owner_pending_input(security.operator_id(), "rules_text", {}, PENDING_TTL_MINUTES)
    handlers.bot.send_message(message.chat.id, i18n.t("rule.ask"), parse_mode="HTML")


def cmd_rules_list(message) -> None:
    rows = database.list_topic_rules()
    if not rows:
        return handlers.bot.send_message(message.chat.id, i18n.t("rule.empty"))
    lines = [i18n.t("rule.list.title", count=len(rows))]
    for row in rows:
        icon = "✅" if row["enabled"] else "⏸"
        lines.append(i18n.t("rule.list.row", icon=icon, id=row["id"],
                            topic=utils.escape(row["topic"] or "")))
        lines.append(i18n.t("rule.list.row_body", rule=utils.escape(row["rule"] or "")))
    handlers.bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML",
                              reply_markup=keyboards.rules_list(rows))


def cmd_rules_del(message) -> None:
    argument = _args(message)
    if not argument.isdigit():
        return handlers.bot.send_message(message.chat.id, i18n.t("rule.usage"))
    rule_id = int(argument)
    if database.delete_topic_rule(rule_id):
        handlers.bot.send_message(message.chat.id, i18n.t("rule.deleted", id=rule_id))
    else:
        handlers.bot.send_message(message.chat.id, i18n.t("rule.delete.missing", id=rule_id))


def cmd_rules_clear(message) -> None:
    count = database.count_topic_rules(enabled_only=False)
    if not count:
        return handlers.bot.send_message(message.chat.id, i18n.t("rule.empty"))
    handlers.bot.send_message(message.chat.id, i18n.t("rule.clear.ask", count=count),
                              parse_mode="HTML", reply_markup=keyboards.confirm("rulesclear"))


# =============================================================================
# Drafting
# =============================================================================
def _organize_and_send(chat_id: int, text: str) -> None:
    existing = [{"topic": row["topic"], "rule": row["rule"]}
                for row in rules_service.active_rules()]
    draft = rules_service.organize(text, previous=existing)
    if draft.empty:
        return handlers.bot.send_message(chat_id, i18n.t("rule.pending.empty"))

    lines = [i18n.t("rule.draft.title"), "",
             i18n.t("rule.draft.count",
                    count=len(draft.rules),
                    ai=i18n.t("rule.draft.ai") if draft.used_ai
                    else i18n.t("rule.draft.plain")), ""]
    for index, item in enumerate(draft.rules, start=1):
        lines.append(f"{index}. <b>{utils.escape(item['topic'])}</b>")
        lines.append(f"   {utils.escape(item['rule'])}")
    if draft.questions:
        lines += ["", i18n.t("rule.draft.questions")]
        lines += [f"• {utils.escape(question)}" for question in draft.questions]
    lines += ["", i18n.t("rule.draft.hint")]
    handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML",
                              reply_markup=keyboards.rules_draft(draft.batch))


def apply_pending(message, kind: str, context: dict) -> None:
    """Answer to "send your instructions" (called by the approvals router)."""
    if kind != "rules_text":
        return
    text = (getattr(message, "text", "") or "").strip()
    if not text:
        return handlers.bot.send_message(message.chat.id, i18n.t("rule.pending.empty"))
    _organize_and_send(message.chat.id, text)


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
        _edit_or_send(call, menu_text(), keyboards.rules_menu())
        return telegram_api.answer_callback(bot, call.id)

    if action == "add":
        database.set_owner_pending_input(security.operator_id(), "rules_text", {},
                                         PENDING_TTL_MINUTES)
        telegram_api.answer_callback(bot, call.id, i18n.t("rule.cb.send"))
        return bot.send_message(chat_id, i18n.t("rule.cb.step"), parse_mode="HTML")

    if action == "list":
        rows = database.list_topic_rules()
        if not rows:
            return telegram_api.answer_callback(bot, call.id, i18n.t("rule.empty"))
        lines = [i18n.t("rule.list.title", count=len(rows))]
        for row in rows:
            icon = "✅" if row["enabled"] else "⏸"
            lines.append(i18n.t("rule.list.row", icon=icon, id=row["id"],
                                topic=utils.escape(row["topic"] or "")))
        _edit_or_send(call, "\n".join(lines), keyboards.rules_list(rows))
        return telegram_api.answer_callback(bot, call.id)

    if action == "ok":
        count = rules_service.approve(argument)
        telegram_api.answer_callback(bot, call.id, i18n.t("rule.cb.approved"))
        return _edit_or_send(call, i18n.t("rule.draft.approved", count=count),
                             keyboards.rules_menu())

    if action == "no":
        count = rules_service.reject(argument)
        telegram_api.answer_callback(bot, call.id, i18n.t("rule.cb.rejected"))
        return _edit_or_send(call, i18n.t("rule.draft.rejected", count=count),
                             keyboards.rules_menu())

    if action == "edit":
        database.set_owner_pending_input(security.operator_id(), EDIT_INSTRUCTION,
                                         {"batch": argument}, PENDING_TTL_MINUTES)
        telegram_api.answer_callback(bot, call.id, i18n.t("rule.cb.send"))
        return bot.send_message(chat_id, i18n.t("rule.ask"), parse_mode="HTML")

    if action == "toggle" and argument.isdigit():
        enabled = rules_service.toggle(int(argument))
        if enabled is None:
            return telegram_api.answer_callback(bot, call.id, i18n.t("rule.cb.not_found"))
        telegram_api.answer_callback(
            bot, call.id,
            i18n.t("rule.toggled.on") if enabled else i18n.t("rule.toggled.off"))
        rows = database.list_topic_rules()
        lines = [i18n.t("rule.list.title", count=len(rows))]
        for row in rows:
            icon = "✅" if row["enabled"] else "⏸"
            lines.append(i18n.t("rule.list.row", icon=icon, id=row["id"],
                                topic=utils.escape(row["topic"] or "")))
        return _edit_or_send(call, "\n".join(lines), keyboards.rules_list(rows))

    if action == "close":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


def edit_pending(message, kind: str, context: dict) -> None:
    """The ✏️ button: the owner re-sends the text, the old draft is discarded."""
    if kind != EDIT_INSTRUCTION:
        return
    text = (getattr(message, "text", "") or "").strip()
    if not text:
        return handlers.bot.send_message(message.chat.id, i18n.t("rule.pending.empty"))
    if context.get("batch"):
        rules_service.reject(context["batch"])
    _organize_and_send(message.chat.id, text)


def _edit_or_send(call, text: str, markup=None) -> None:
    try:
        handlers.bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                       parse_mode="HTML", reply_markup=markup)
        return
    except Exception:
        log.debug("could not edit the rule message; sending a new one", exc_info=True)
    handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                              reply_markup=markup)


# Re-exported for the approvals router (keeps its route table short).
PENDING_KINDS = {"rules_text": apply_pending, EDIT_INSTRUCTION: edit_pending}

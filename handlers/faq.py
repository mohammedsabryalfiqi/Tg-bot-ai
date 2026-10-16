"""Quick answers (FAQ) management: `/faq`.

A quick answer is a set of trigger words plus the exact reply to send. If a
customer's message matches a trigger exactly, that reply is sent verbatim
(instant, no AI, no risk of the model changing a price); near matches are given
to the AI as authoritative context.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import database
import handlers
import i18n
import keyboards
import security
import telegram_api
import utils
from services import faq_service

log = logging.getLogger("smartel.faq_handler")

PENDING_TTL_MINUTES = 15
ONE_LINER_SEP = "::"
PER_PAGE = 5


def register(bot, cfg) -> None:
    def cmd(commands, fn):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=fn):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["faq", "qa"], cmd_menu)
    cmd(["faq_add", "qa_add"], cmd_add)
    cmd(["faq_list", "qa_list"], lambda m: _safe(lambda: send_list(m.chat.id, 0)))
    cmd(["faq_del", "qa_del"], cmd_delete)
    cmd(["faq_search", "qa_search"], cmd_search)
    cmd(["faq_clear", "qa_clear"], cmd_clear)
    cmd(["faq_export", "qa_export"], lambda m: _safe(lambda: export_to_chat(m.chat.id)))
    cmd(["faq_import", "qa_import"], cmd_import)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("faq:"))
    @security.owner_only_callback
    def _faq_cb(call):
        _safe(lambda: on_callback(call))


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("faq handler failed")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Menu / commands
# =============================================================================
def _stats_text() -> str:
    entries = faq_service.list_entries()
    enabled = [e for e in entries if e["enabled"]]
    direct = database.get_bool("faq_direct_reply")
    lines = [
        i18n.t("faq.menu.title"),
        "",
        i18n.t("faq.menu.entries", total=len(entries), active=len(enabled)),
        i18n.t("faq.menu.direct", state=i18n.t("set.value.on") if direct
               else i18n.t("set.value.off")),
        i18n.t("faq.menu.fuzzy",
               state=i18n.t("set.value.on") if database.get_bool("faq_enabled")
               else i18n.t("set.value.off")),
        "",
        i18n.t("faq.menu.example"),
    ]
    lines.append("")
    lines.append(i18n.t("faq.menu.add", sep=ONE_LINER_SEP))
    return "\n".join(lines)


def cmd_menu(message) -> None:
    handlers.bot.send_message(message.chat.id, _stats_text(), parse_mode="HTML",
                              reply_markup=keyboards.faq_menu())


def cmd_add(message) -> None:
    raw = _args(message)
    if raw and ONE_LINER_SEP in raw:
        triggers, answer = raw.split(ONE_LINER_SEP, 1)
        return _create(message.chat.id, triggers, answer)
    database.set_owner_pending_input(security.operator_id(), "faq_keywords", {}, PENDING_TTL_MINUTES)
    handlers.bot.send_message(message.chat.id, i18n.t("faq.add.step1"), parse_mode="HTML")


def cmd_delete(message) -> None:
    raw = _args(message)
    try:
        entry_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(message.chat.id, i18n.t("faq.delete.usage"))
    ok = faq_service.delete(entry_id)
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("faq.delete.done", id=entry_id) if ok
        else i18n.t("faq.delete.missing", id=entry_id))


def cmd_search(message) -> None:
    query = _args(message)
    if not query:
        database.set_owner_pending_input(security.operator_id(), "faq_search", {}, PENDING_TTL_MINUTES)
        return handlers.bot.send_message(message.chat.id, i18n.t("faq.search.ask"))
    _do_search(message.chat.id, query)


def cmd_clear(message) -> None:
    handlers.bot.send_message(message.chat.id, i18n.t("faq.clear.ask"),
                              parse_mode="HTML", reply_markup=keyboards.confirm("faqclear"))


def cmd_import(message) -> None:
    database.set_owner_pending_input(security.operator_id(), "faq_import", {}, PENDING_TTL_MINUTES)
    handlers.bot.send_message(message.chat.id, i18n.t("faq.import.ask"), parse_mode="HTML")


# =============================================================================
# Rendering
# =============================================================================
def send_list(chat_id: int, page: int = 0) -> None:
    entries = faq_service.list_entries()
    if not entries:
        return handlers.bot.send_message(chat_id, i18n.t("faq.list.empty"), parse_mode="HTML")
    start = page * PER_PAGE
    shown = entries[start:start + PER_PAGE]
    lines = [i18n.t("faq.list.title", count=len(entries))]
    for entry in shown:
        lines.append("")
        lines.append(faq_service.format_entry(entry))
    if start + PER_PAGE < len(entries):
        lines.append("")
        lines.append(i18n.t("faq.list.next_page"))
    handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML",
                              reply_markup=keyboards.faq_list(entries, page, PER_PAGE))


def _do_search(chat_id: int, query: str) -> None:
    matches = faq_service.search(query, limit=5, min_score=0.0)
    if not matches:
        return handlers.bot.send_message(
            chat_id, i18n.t("faq.search.none", query=utils.escape(query)),
            parse_mode="HTML",
        )
    lines = [i18n.t("faq.search.title", query=utils.escape(query))]
    for match in matches:
        if match.is_direct():
            mode = i18n.t("faq.search.mode_instant")
        elif match.exact:
            mode = i18n.t("faq.search.mode_exact")
        else:
            mode = i18n.t("faq.search.mode_fuzzy", score=f"{match.score:.0%}")
        lines.append("")
        lines.append(f"{faq_service.format_entry(match.row)}\n   ↳ {mode}")
    handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")


def _create(chat_id: int, keywords: str, answer: str) -> None:
    keywords = (keywords or "").strip()
    answer = (answer or "").strip()
    if not faq_service.parse_triggers(keywords):
        return handlers.bot.send_message(chat_id, i18n.t("faq.create.short_trigger"))
    if not answer:
        return handlers.bot.send_message(chat_id, i18n.t("faq.create.empty_answer"))
    entry_id = faq_service.add(keywords, answer)
    handlers.bot.send_message(
        chat_id,
        i18n.t("faq.create.saved", id=entry_id, triggers=utils.escape(keywords),
               answer=utils.escape(answer)),
        parse_mode="HTML",
    )


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    chat_id = call.message.chat.id

    if action == "menu":
        _replace(call, _stats_text(), keyboards.faq_menu())
        return telegram_api.answer_callback(bot, call.id)

    if action == "add":
        database.set_owner_pending_input(security.operator_id(), "faq_keywords", {},
                                        PENDING_TTL_MINUTES)
        telegram_api.answer_callback(bot, call.id, i18n.t("faq.cb.send_triggers"))
        bot.send_message(chat_id, i18n.t("faq.cb.step1"), parse_mode="HTML")
        return

    if action == "list":
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        entries = faq_service.list_entries()
        if not entries:
            return telegram_api.answer_callback(bot, call.id, i18n.t("faq.list.none"))
        lines = [i18n.t("faq.list.title", count=len(entries))]
        for entry in entries[page * PER_PAGE:(page + 1) * PER_PAGE]:
            lines.append("")
            lines.append(faq_service.format_entry(entry))
        _replace(call, "\n".join(lines), keyboards.faq_list(entries, page, PER_PAGE))
        return telegram_api.answer_callback(bot, call.id)

    if action == "del":
        entry_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        ok = faq_service.delete(entry_id)
        entries = faq_service.list_entries()
        lines = [i18n.t("faq.list.title", count=len(entries))]
        for entry in entries[page * PER_PAGE:(page + 1) * PER_PAGE]:
            lines.append("")
            lines.append(faq_service.format_entry(entry))
        _replace(call, "\n".join(lines),
                 keyboards.faq_list(entries, page, PER_PAGE) if entries else None)
        return telegram_api.answer_callback(
            bot, call.id,
            i18n.t("faq.cb.deleted") if ok else i18n.t("faq.cb.not_found"))

    if action == "search":
        database.set_owner_pending_input(security.operator_id(), "faq_search", {},
                                        PENDING_TTL_MINUTES)
        telegram_api.answer_callback(bot, call.id, i18n.t("faq.cb.send_test"))
        bot.send_message(chat_id, i18n.t("faq.search.ask"))
        return

    if action == "export":
        telegram_api.answer_callback(bot, call.id, i18n.t("faq.cb.preparing"))
        export_to_chat(chat_id)
        return

    if action == "clear":
        telegram_api.answer_callback(bot, call.id)
        bot.send_message(chat_id, i18n.t("faq.clear.ask"), parse_mode="HTML",
                         reply_markup=keyboards.confirm("faqclear"))
        return

    if action == "close":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


def _replace(call, text: str, reply_markup=None) -> None:
    try:
        handlers.bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                       parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        handlers.bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                                  reply_markup=reply_markup)


# =============================================================================
# Export / import
# =============================================================================
def export_to_chat(chat_id: int) -> None:
    rows = faq_service.export_rows()
    if not rows:
        return handlers.bot.send_message(chat_id, i18n.t("faq.export.empty"))
    payload = {"type": "smartel-faq", "version": 1, "entries": rows}
    path = Path(tempfile.gettempdir()) / f"smartel_faq_{utils.now_ts()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        telegram_api.send_document(handlers.bot, chat_id, path,
                                   caption=i18n.t("faq.export.caption", count=len(rows)))
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def apply_pending(message, kind: str, context: dict) -> None:
    owner = security.operator_id()
    chat_id = message.chat.id

    if kind == "faq_keywords":
        keywords = (getattr(message, "text", "") or "").strip()
        if not faq_service.parse_triggers(keywords):
            database.clear_owner_pending_input(owner)
            return handlers.bot.send_message(chat_id, i18n.t("faq.pending.short_triggers"))
        database.set_owner_pending_input(owner, "faq_answer", {"keywords": keywords},
                                        PENDING_TTL_MINUTES)
        return handlers.bot.send_message(
            chat_id, i18n.t("faq.pending.step2", triggers=utils.escape(keywords)),
            parse_mode="HTML",
        )

    if kind == "faq_answer":
        database.clear_owner_pending_input(owner)
        answer = (getattr(message, "text", "") or getattr(message, "caption", "") or "").strip()
        if not answer:
            return handlers.bot.send_message(chat_id, i18n.t("faq.pending.empty_answer"))
        return _create(chat_id, context.get("keywords", ""), answer)

    if kind == "faq_search":
        database.clear_owner_pending_input(owner)
        return _do_search(chat_id, (getattr(message, "text", "") or "").strip())

    if kind == "faq_import":
        database.clear_owner_pending_input(owner)
        document = getattr(message, "document", None)
        if document is None:
            return handlers.bot.send_message(chat_id, i18n.t("faq.import.not_json"))
        try:
            data = telegram_api.download_file_bytes(document.file_id)
            payload = json.loads(data.decode("utf-8", errors="replace"))
        except Exception as e:
            log.warning("FAQ import failed: %s", type(e).__name__)
            return handlers.bot.send_message(chat_id, i18n.t("faq.import.unreadable"))
        rows = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return handlers.bot.send_message(chat_id, i18n.t("faq.import.bad_structure"))
        inserted = faq_service.import_rows(rows)
        return handlers.bot.send_message(
            chat_id, i18n.t("faq.import.done", count=inserted))

"""Knowledge-base commands and menu: add text, upload files, search, list and
delete items, and clear the KB. Ingestion/retrieval live in services/kb_service.
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
from services import kb_service
from services.file_service import FileServiceError
from services.ai_service import AIServiceError as OpenAIServiceError

log = logging.getLogger("smartel.kb_handler")


def _args(message) -> str:
    text = getattr(message, "text", "") or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def register(bot, cfg) -> None:
    @bot.message_handler(commands=["kb"], func=security.is_operator_msg)
    def _kb(message):
        security.run_as_operator(message, lambda: _safe(lambda: open_menu(message)))

    @bot.message_handler(commands=["kb_add"], func=security.is_operator_msg)
    def _kb_add(message):
        security.run_as_operator(message, lambda: _safe(lambda: cmd_add(message)))

    @bot.message_handler(commands=["kb_upload"], func=security.is_operator_msg)
    def _kb_upload(message):
        security.run_as_operator(message, lambda: _safe(lambda: cmd_upload(message)))

    @bot.message_handler(commands=["kb_search"], func=security.is_operator_msg)
    def _kb_search(message):
        security.run_as_operator(message, lambda: _safe(lambda: cmd_search(message)))

    @bot.message_handler(commands=["kb_list"], func=security.is_operator_msg)
    def _kb_list(message):
        security.run_as_operator(message, lambda: _safe(lambda: send_list(message.chat.id, 0)))

    @bot.message_handler(commands=["kb_delete"], func=security.is_operator_msg)
    def _kb_delete(message):
        security.run_as_operator(message, lambda: _safe(lambda: cmd_delete(message)))

    @bot.message_handler(commands=["kb_clear"], func=security.is_operator_msg)
    def _kb_clear(message):
        security.run_as_operator(message, lambda: _safe(lambda: cmd_clear(message)))

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("kb:"))
    @security.owner_only_callback
    def _kb_cb(call):
        _safe(lambda: on_callback(call))


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("kb handler failed")


# =============================================================================
# Menu + commands
# =============================================================================
def open_menu(message) -> None:
    stats = kb_service.stats()
    text = i18n.t("kb.menu.title", items=stats["items"], chunks=stats["chunks"],
                  usage=i18n.t("set.value.on") if database.get_bool("kb_enabled")
                  else i18n.t("set.value.off"),
                  strict=i18n.t("set.value.on") if database.get_bool("strict_kb_mode")
                  else i18n.t("set.value.off"))
    handlers.bot.send_message(message.chat.id, text, parse_mode="HTML",
                              reply_markup=keyboards.kb_menu())


def cmd_add(message) -> None:
    text = _args(message)
    if not text:
        database.set_owner_pending_input(security.operator_id(), "kb_add", {}, 10)
        return handlers.notify_owner(i18n.t("kb.add.ask"))
    _do_add_text(text)


def cmd_upload(message) -> None:
    database.set_owner_pending_input(security.operator_id(), "kb_upload", {}, 10)
    handlers.notify_owner(i18n.t("kb.upload.ask"))


def cmd_search(message) -> None:
    query = _args(message)
    if not query:
        database.set_owner_pending_input(security.operator_id(), "kb_search", {}, 10)
        return handlers.notify_owner(i18n.t("kb.search.ask"))
    _do_search(message.chat.id, query)


def cmd_delete(message) -> None:
    raw = _args(message)
    try:
        item_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(message.chat.id, i18n.t("kb.delete.usage"))
    ok = kb_service.delete_item(item_id)
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("kb.delete.done", id=item_id) if ok
        else i18n.t("kb.delete.missing", id=item_id))


def cmd_clear(message) -> None:
    stats = kb_service.stats()
    if stats["items"] == 0:
        return handlers.bot.send_message(message.chat.id, i18n.t("kb.clear.empty"))
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("kb.clear.ask", items=stats["items"], chunks=stats["chunks"]),
        parse_mode="HTML", reply_markup=keyboards.confirm("kbclear"),
    )


def send_list(chat_id: int, page: int) -> None:
    items = kb_service.list_items()
    if not items:
        return handlers.bot.send_message(chat_id, i18n.t("kb.list.empty"))
    handlers.bot.send_message(
        chat_id, i18n.t("kb.list.title"), parse_mode="HTML",
        reply_markup=keyboards.kb_list_keyboard(items, page),
    )


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "menu":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        open_menu(call.message)
        return telegram_api.answer_callback(bot, call.id)

    if action == "add":
        database.set_owner_pending_input(security.operator_id(), "kb_add", {}, 10)
        handlers.notify_owner(i18n.t("kb.add.ask"))
        return telegram_api.answer_callback(bot, call.id, i18n.t("kb.cb.send_text"))

    if action == "upload":
        database.set_owner_pending_input(security.operator_id(), "kb_upload", {}, 10)
        handlers.notify_owner(i18n.t("kb.upload.ask_docs"))
        return telegram_api.answer_callback(bot, call.id, i18n.t("kb.cb.send_file"))

    if action == "search":
        database.set_owner_pending_input(security.operator_id(), "kb_search", {}, 10)
        handlers.notify_owner(i18n.t("kb.search.ask"))
        return telegram_api.answer_callback(bot, call.id, i18n.t("kb.cb.send_query"))

    if action == "list":
        page = int(parts[2]) if len(parts) > 2 else 0
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_list(call.message.chat.id, page)
        return telegram_api.answer_callback(bot, call.id)

    if action == "del":
        item_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        kb_service.delete_item(item_id)
        items = kb_service.list_items()
        try:
            if items:
                bot.edit_message_reply_markup(
                    call.message.chat.id, call.message.message_id,
                    reply_markup=keyboards.kb_list_keyboard(items, page),
                )
            else:
                bot.edit_message_text(i18n.t("kb.cb.now_empty"),
                                      call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id,
                                            i18n.t("kb.cb.deleted", id=item_id))

    if action == "clear":
        bot.send_message(call.message.chat.id, i18n.t("kb.clear.ask_plain"),
                         reply_markup=keyboards.confirm("kbclear"))
        return telegram_api.answer_callback(bot, call.id)

    if action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    telegram_api.answer_callback(bot, call.id)


# =============================================================================
# Pending-input application (routed from approvals.on_owner_pending_input)
# =============================================================================
def apply_pending(message, kind: str, context: dict) -> None:
    database.clear_owner_pending_input(security.operator_id())
    if kind == "kb_add":
        text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
        if not text:
            return handlers.notify_owner(i18n.t("kb.pending.empty"))
        _do_add_text(text)
    elif kind == "kb_upload":
        _do_upload(message)
    elif kind == "kb_search":
        query = (getattr(message, "text", "") or "").strip()
        if not query:
            return handlers.notify_owner(i18n.t("kb.pending.empty_query"))
        _do_search(message.chat.id, query)


def _do_add_text(text: str) -> None:
    title = text.splitlines()[0][:60] if text.strip() else "Note"
    result = kb_service.add_text(title, text)
    note = "" if result["embedded"] else i18n.t("kb.add.note_no_embeddings")
    handlers.notify_owner(i18n.t(
        "kb.add.done", id=result["item_id"], count=result["chunk_count"], note=note))


def _do_upload(message) -> None:
    doc = getattr(message, "document", None)
    if doc is None:
        return handlers.notify_owner(i18n.t("kb.upload.need_document"))
    file_name = getattr(doc, "file_name", "upload")
    try:
        data = telegram_api.download_file_bytes(doc.file_id)
    except Exception as e:
        log.warning("file download failed: %s", type(e).__name__)
        return handlers.notify_owner(i18n.t("kb.upload.download_failed"))
    try:
        result = kb_service.add_file(data, file_name)
    except FileServiceError as e:
        return handlers.notify_owner(f"⚠️ {utils.escape(str(e))}")
    except OpenAIServiceError as e:
        return handlers.notify_owner(f"⚠️ {utils.escape(e.owner_message)}")
    note = "" if result["embedded"] else i18n.t("kb.add.note_no_embeddings")
    handlers.notify_owner(i18n.t(
        "kb.upload.done", name=utils.escape(file_name), id=result["item_id"],
        count=result["chunk_count"], note=note))


def _do_search(chat_id: int, query: str) -> None:
    try:
        chunks = kb_service.search(query)
    except OpenAIServiceError as e:
        return handlers.bot.send_message(chat_id, f"⚠️ {utils.escape(e.owner_message)}")
    if not chunks:
        return handlers.bot.send_message(chat_id, i18n.t("kb.search.none"))
    lines = [i18n.t("kb.search.title", count=len(chunks), query=utils.escape(query[:80]))]
    for i, ch in enumerate(chunks, start=1):
        lines.append(f"\n<b>[{i}]</b> {utils.escape((ch['content'] or '')[:400])}")
    handlers.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

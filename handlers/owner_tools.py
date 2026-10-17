"""Owner tools: conversation handling, statistics, health checks and backups.

* `/mode`      — switch between auto-reply / draft (approve first) / off
* `/chats`     — recent customer chats, with transcripts and pause/resume
* `/chat <id>` — one chat's transcript
* `/reply <chat_id> <text>` — send a message yourself from the business account
* `/takeover` and `/handback` — pause / resume the AI for one customer
* `/stats`     — how many customers, messages and AI replies
* `/health`    — end-to-end checks of token, AI, connection, storage
* `/export`    — JSON backup of settings + quick answers + knowledge index
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import database
import handlers
import i18n
import keyboards
import security
import telegram_api
import utils
from services import ai_service, business_service, faq_service, memory_service, providers

log = logging.getLogger("smartel.tools")

TRANSCRIPT_LIMIT = 20
# How long a parked "/reply <chat_id>" waits for the owner's text.
TAKEOVER_INPUT_TTL_MINUTES = 15


def register(bot, cfg) -> None:
    def cmd(commands, fn):
        @bot.message_handler(commands=commands, func=security.is_operator_msg)
        def _handler(message, _fn=fn):
            security.run_as_operator(message, lambda: _safe(lambda: _fn(message)))

    cmd(["mode"], cmd_mode)
    cmd(["chats", "inbox"], cmd_chats)
    cmd(["chat"], cmd_chat)
    cmd(["reply"], cmd_reply)
    cmd(["takeover", "handover"], lambda m: _do_pause_command(m, pause=True))
    cmd(["handback", "handover_back"], lambda m: _do_pause_command(m, pause=False))
    cmd(["stats"], cmd_stats)
    cmd(["health"], cmd_health)
    cmd(["export", "backup"], lambda m: _safe(lambda: export_backup(m.chat.id)))

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("tool:"))
    @security.owner_only_callback
    def _tool_cb(call):
        _safe(lambda: on_callback(call))


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("owner tool failed")


def _args(message) -> str:
    parts = (getattr(message, "text", "") or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# =============================================================================
# Reply mode
# =============================================================================
def current_mode() -> str:
    if not database.get_bool("auto_reply_enabled"):
        return "off"
    return "draft" if database.get_bool("approval_mode_enabled") else "auto"


def set_mode(mode: str) -> str:
    """Apply a reply mode to the two underlying switches; returns the new mode."""
    mode = (mode or "").strip().lower()
    if mode == "auto":
        database.set_setting("auto_reply_enabled", True)
        database.set_setting("approval_mode_enabled", False)
    elif mode == "draft":
        database.set_setting("auto_reply_enabled", True)
        database.set_setting("approval_mode_enabled", True)
    else:
        mode = "off"
        database.set_setting("auto_reply_enabled", False)
        database.set_setting("approval_mode_enabled", True)
    return mode


_MODE_KEYS = {"auto": "tool.mode.auto", "draft": "tool.mode.draft", "off": "tool.mode.off"}


def mode_text(mode: str) -> str:
    """Localised one-line explanation of a reply mode."""
    return i18n.t(_MODE_KEYS.get(mode, "tool.mode.off"))


def cmd_mode(message) -> None:
    arg = _args(message).lower()
    if arg in ("auto", "draft", "off"):
        mode = set_mode(arg)
        return handlers.bot.send_message(
            message.chat.id, i18n.t("tool.mode.set", text=mode_text(mode), mode=mode),
            parse_mode="HTML", reply_markup=keyboards.mode_keyboard(mode))
    mode = current_mode()
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("tool.mode.current", text=mode_text(mode)),
        parse_mode="HTML",
        reply_markup=keyboards.mode_keyboard(mode),
    )


# =============================================================================
# Chats
# =============================================================================
def cmd_chats(message) -> None:
    rows = database.list_recent_customer_chats(limit=10)
    if not rows:
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.chats.empty"))
    buttons = []
    for row in rows:
        name = business_service.customer_display_name(row["business_connection_id"],
                                                      row["customer_chat_id"])
        buttons.append({"label": i18n.t("tool.chats.label", name=name,
                                        count=row["message_count"]),
                        "chat_id": row["customer_chat_id"]})
    handlers.bot.send_message(
        message.chat.id,
        i18n.t("tool.chats.title"),
        parse_mode="HTML",
        reply_markup=keyboards.chats_list(buttons),
    )


def _transcript_text(bcid: str, chat_id: int) -> str:
    name = business_service.customer_display_name(bcid, chat_id)
    rows = database.get_recent_messages(bcid, chat_id, TRANSCRIPT_LIMIT)
    lines = [i18n.t("tool.transcript.title", name=utils.escape(name), chat_id=chat_id)]
    if not rows:
        lines.append(i18n.t("tool.transcript.empty"))
    for row in rows:
        who = i18n.t("tool.transcript.customer") if row["direction"] == "in" \
            else i18n.t("tool.transcript.bot")
        text = utils.escape((row["content"] or "")[:400])
        lines.append(f"\n<b>{who}</b> · {utils.escape(row['created_at'][11:16])}\n{text}")
    paused = business_service.is_chat_paused(bcid, chat_id)
    lines.append("")
    lines.append(i18n.t(
        "tool.transcript.pause_state",
        state=i18n.t("tool.transcript.paused") if paused else i18n.t("tool.transcript.active"),
    ))
    lines.append(i18n.t("tool.transcript.reply_hint", chat_id=chat_id))
    return "\n".join(lines)


def cmd_chat(message) -> None:
    raw = _args(message)
    try:
        chat_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.chat.usage"))
    bcid = business_service.find_bcid_for_chat(chat_id)
    if bcid is None:
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.chat.none"))
    handlers.bot.send_message(message.chat.id, _transcript_text(bcid, chat_id), parse_mode="HTML",
                              reply_markup=keyboards.chat_actions(
                                  chat_id, business_service.is_chat_paused(bcid, chat_id)))


def cmd_reply(message) -> None:
    raw = _args(message)
    parts = raw.split(maxsplit=1)
    if not parts or not parts[0].lstrip("-").isdigit():
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.reply.usage"),
                                         parse_mode="HTML")
    chat_id = int(parts[0])
    if len(parts) < 2 or not parts[1].strip():
        # No text yet: park the target chat and let the owner type the message.
        database.set_owner_pending_input(security.operator_id(), "reply_to_chat",
                                        {"chat_id": chat_id}, TAKEOVER_INPUT_TTL_MINUTES)
        return handlers.bot.send_message(
            message.chat.id, i18n.t("tool.reply.ask", chat_id=chat_id), parse_mode="HTML")
    _send_owner_reply(message.chat.id, chat_id, parts[1].strip())


def _send_owner_reply(owner_chat_id: int, chat_id: int, text: str) -> None:
    """Deliver an owner-written message from the business account (takeover)."""
    bcid = business_service.find_bcid_for_chat(chat_id)
    if bcid is None:
        return handlers.bot.send_message(owner_chat_id, i18n.t("tool.reply.unknown_chat"))
    conn = business_service.get_connection(bcid)
    if conn is None or not (conn["is_enabled"] and conn["can_reply"]):
        return handlers.bot.send_message(owner_chat_id, i18n.t("tool.reply.cannot_reply"))
    try:
        telegram_api.send_reply(handlers.bot, chat_id, text, business_connection_id=bcid,
                                sanitize=False)
    except Exception as e:
        return handlers.bot.send_message(
            owner_chat_id, i18n.t("tool.reply.failed", error=type(e).__name__))
    database.insert_message(bcid, chat_id, None, "out", "owner", text)
    memory_service.append_exchange(bcid, chat_id, "[owner replied manually]", text)
    # Manual reply = takeover: keep the AI out of this chat for a while.
    minutes = database.get_int("owner_takeover_pause_minutes")
    business_service.pause_chat(bcid, chat_id, reason="owner_takeover", minutes=minutes)
    handlers.bot.send_message(
        owner_chat_id, i18n.t("tool.reply.sent", minutes=minutes), parse_mode="HTML")


def apply_pending(message, kind: str, context: dict) -> None:
    """Pending-input hook (called by the approvals router).

    Owns the ``reply_to_chat`` state: ``/reply <chat_id>`` parks the chat and the
    next owner message becomes the text to deliver.
    """
    if kind != "reply_to_chat":
        return
    owner = security.operator_id()
    database.clear_owner_pending_input(owner)
    try:
        chat_id = int((context or {}).get("chat_id") or 0)
    except (TypeError, ValueError):
        chat_id = 0
    text = (getattr(message, "text", "") or "").strip()
    if not chat_id or not text:
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.reply.cancelled"))
    _send_owner_reply(message.chat.id, chat_id, text)


def _do_pause_command(message, pause: bool) -> None:
    raw = _args(message)
    try:
        chat_id = int(raw)
    except ValueError:
        return handlers.bot.send_message(
            message.chat.id,
            i18n.t("tool.pause.usage", command="takeover" if pause else "handback"))
    bcid = business_service.find_bcid_for_chat(chat_id)
    if bcid is None:
        return handlers.bot.send_message(message.chat.id, i18n.t("tool.reply.unknown_chat"))
    if pause:
        business_service.pause_chat(bcid, chat_id, reason="manual_pause", minutes=None)
        handlers.bot.send_message(
            message.chat.id, i18n.t("tool.pause.done", chat_id=chat_id), parse_mode="HTML")
    else:
        ok = business_service.resume_chat(bcid, chat_id)
        handlers.bot.send_message(
            message.chat.id,
            i18n.t("tool.pause.resumed") if ok else i18n.t("tool.pause.not_paused"),
            parse_mode="HTML")


# =============================================================================
# Stats & health
# =============================================================================
def cmd_stats(message) -> None:
    day_ago = utils.future_iso(-60 * 24)
    week_ago = utils.future_iso(-60 * 24 * 7)
    conns = business_service.real_connections()
    lines = [
        i18n.t("tool.stats.title"),
        "",
        i18n.t("tool.stats.customers", count=database.count_customers()),
        i18n.t("tool.stats.messages",
               day=database.count_messages(direction="in", since_iso=day_ago),
               week=database.count_messages(direction="in", since_iso=week_ago),
               total=database.count_messages(direction="in")),
        i18n.t("tool.stats.replies",
               day=database.count_ai_replies(day_ago),
               week=database.count_ai_replies(week_ago),
               total=database.count_ai_replies()),
        "",
        i18n.t("tool.stats.summary", mode=current_mode(),
               pending=database.count_pending_approvals()),
        i18n.t("tool.stats.paused", count=len(database.list_active_pauses())),
        i18n.t("tool.stats.kb", count=len(database.list_kb_items())),
        i18n.t("tool.stats.faq", count=faq_service.count()),
        i18n.t("tool.stats.connections", count=len(conns)),
        i18n.t("tool.stats.direct",
               state=i18n.t("own.status.direct_on")
               if database.get_bool("direct_reply_enabled")
               else i18n.t("own.status.direct_off")),
    ]
    handlers.bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")


def cmd_health(message) -> None:
    handlers.bot.send_message(message.chat.id, health_report(), parse_mode="HTML")


def health_report() -> str:
    lines = [i18n.t("tool.health.title"), ""]

    # Token / API reachability
    try:
        me = handlers.bot.get_me()
        lines.append(i18n.t("tool.health.telegram_ok", username=utils.escape(me.username)))
    except Exception as e:
        lines.append(i18n.t("tool.health.telegram_error", error=utils.escape(type(e).__name__)))

    # AI provider
    provider = ai_service.active_provider()
    if ai_service.is_ready():
        lines.append(i18n.t("tool.health.ai_ok",
                            backend=utils.escape(ai_service.backend_label()),
                            model=utils.escape(ai_service.active_model_label())))
    else:
        lines.append(i18n.t("tool.health.ai_missing"))
    lines.append(i18n.t("tool.health.cost", cost=utils.escape(ai_service.cost_label(provider))))
    lines.append(i18n.t(
        "tool.health.embeddings",
        state=i18n.t("tool.health.embeddings_yes") if ai_service.supports_embeddings()
        else i18n.t("tool.health.embeddings_no"),
    ))
    if not ai_service.is_ready() or providers.needs_credit(provider.id):
        lines.append(i18n.t("tool.health.freeai_hint"))

    # Business connection
    conns = business_service.real_connections()
    if database.get_bool("direct_reply_enabled"):
        lines.append(i18n.t("tool.health.direct_ready"))
    if not conns:
        lines.append(i18n.t("tool.health.no_connection"))
    else:
        for conn in conns:
            ok = bool(conn["is_enabled"]) and bool(conn["can_reply"])
            icon = "✅" if ok else "⚠️"
            lines.append(i18n.t(
                "tool.health.connection_row", icon=icon,
                id=utils.escape(conn["business_connection_id"][:10]),
                enabled=bool(conn["is_enabled"]), can_reply=bool(conn["can_reply"])))
            if not conn["can_reply"]:
                lines.append(i18n.t("tool.health.enable_reply"))

    # Storage
    try:
        usage = shutil.disk_usage(Path(handlers.cfg.db_path).parent)
        free_mb = usage.free // (1024 * 1024)
        lines.append(i18n.t("tool.health.disk", mb=free_mb))
    except Exception:
        pass
    lines.append(i18n.t("tool.health.summary", mode=current_mode(),
                        pending=database.count_pending_approvals()))
    lines.append(i18n.t("tool.health.aitest_hint"))
    return "\n".join(lines)


# =============================================================================
# Backup
# =============================================================================
def export_backup(chat_id: int) -> None:
    payload = {
        "type": "smartel-backup",
        "version": 1,
        "exported_at": utils.now_iso(),
        "settings": database.get_all_settings(),
        "faq": faq_service.export_rows(),
        "knowledge_base": [
            {"id": row["id"], "title": row["title"], "source_type": row["source_type"],
             "filename": row["filename"], "chunks": row["chunk_count"]}
            for row in database.list_kb_items()
        ],
        "business_connections": [
            {"id": row["business_connection_id"], "enabled": bool(row["is_enabled"]),
             "can_reply": bool(row["can_reply"])}
            for row in database.list_business_connections()
        ],
        "stats": {
            "customers": database.count_customers(),
            "messages_in": database.count_messages(direction="in"),
            "ai_replies": database.count_ai_replies(),
        },
    }
    # Never export secrets.
    payload["settings"].pop("ai_api_key", None)
    path = Path(tempfile.gettempdir()) / f"smartel_backup_{utils.now_ts()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        telegram_api.send_document(handlers.bot, chat_id, path,
                                   caption=i18n.t("tool.export.caption"))
    finally:
        try:
            path.unlink()
        except OSError:
            pass


# =============================================================================
# Callbacks
# =============================================================================
def on_callback(call) -> None:
    bot = handlers.bot
    parts = (call.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    chat_id = call.message.chat.id

    if action == "close":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.closed"))

    if action == "health":
        telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.checking"))
        bot.send_message(chat_id, health_report(), parse_mode="HTML")
        return

    if action == "setup":
        from handlers import setup_guide
        telegram_api.answer_callback(bot, call.id)
        return setup_guide.send_checklist(chat_id)

    if action == "chat":
        try:
            target = int(arg)
        except ValueError:
            return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.bad_chat"))
        bcid = business_service.find_bcid_for_chat(target)
        if bcid is None:
            return telegram_api.answer_callback(
                bot, call.id, i18n.t("tool.callback.no_messages"))
        telegram_api.answer_callback(bot, call.id)
        bot.send_message(chat_id, _transcript_text(bcid, target), parse_mode="HTML",
                         reply_markup=keyboards.chat_actions(
                             target, business_service.is_chat_paused(bcid, target)))
        return

    if action in ("pause", "resume"):
        try:
            target = int(arg)
        except ValueError:
            return telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.bad_chat"))
        bcid = business_service.find_bcid_for_chat(target)
        if bcid is None:
            return telegram_api.answer_callback(bot, call.id, i18n.t("tool.reply.unknown_chat"))
        if action == "pause":
            business_service.pause_chat(bcid, target, reason="manual_pause", minutes=None)
            message = i18n.t("tool.callback.paused", chat_id=target)
        else:
            business_service.resume_chat(bcid, target)
            message = i18n.t("tool.callback.resumed", chat_id=target)
        telegram_api.answer_callback(bot, call.id, i18n.t("tool.callback.done"))
        bot.send_message(chat_id, message, parse_mode="HTML")
        return

    if action == "setup_step":
        from handlers import setup_guide
        telegram_api.answer_callback(bot, call.id)
        return setup_guide.send_step(chat_id, arg)

    if action == "fonts":
        from services import font_service
        fonts = font_service.list_cloud_fonts()
        telegram_api.answer_callback(bot, call.id)
        text = "🔤 <b>قائمة الخطوط السحابية المتوفرة (Google Drive / Cloud):</b>\nاختر خطًا لتحميله وإرساله فورًا:"
        return bot.send_message(chat_id, text, parse_mode="HTML",
                                reply_markup=keyboards.fonts_list(fonts))

    if action == "dlfont":
        from services import font_service
        import io
        fonts = font_service.list_cloud_fonts()
        try:
            fidx = int(arg)
            font_meta = fonts[fidx]
            fname, fdata = font_service.get_font_content(font_meta)
            bio = io.BytesIO(fdata)
            bio.name = fname
            bot.send_document(chat_id, bio, caption=f"📁 خط سحابي: <b>{fname}</b>", parse_mode="HTML")
            telegram_api.answer_callback(bot, call.id, "تم إرسال الخط بنجاح!")
        except Exception as e:
            telegram_api.answer_callback(bot, call.id, "فشل تحميل الخط", show_alert=True)
        return

    telegram_api.answer_callback(bot, call.id)

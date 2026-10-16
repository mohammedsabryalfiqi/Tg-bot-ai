"""`/setup` — a guided checklist that walks the owner from "bot created" to
"answering customers", with live status detection for each step.

The telegram-side steps (Business/Secretary mode in @BotFather, connecting the
bot in Telegram Business → Chatbots) cannot be automated — Telegram requires the
account owner to do them in the app — so this module explains each one exactly
and verifies what can be verified.

Direct messages (people writing to the bot's own chat) need none of that: the
checklist says so and points at /direct.
"""

from __future__ import annotations

import logging

import database
import handlers
import i18n
import keyboards
import utils
from services import ai_service, business_service, faq_service

log = logging.getLogger("smartel.setup")

STEP_LABELS = {
    "secretary": "setup.step.secretary.label",
    "business": "setup.step.business.label",
    "ai": "setup.step.ai.label",
    "content": "setup.step.content.label",
    "mode": "setup.step.mode.label",
    "test": "setup.step.test.label",
}

_DETAIL_KEYS = {
    "secretary": "setup.step.secretary.body",
    "business": "setup.step.business.body",
    "ai": "setup.step.ai.body",
    "content": "setup.step.content.body",
    "mode": "setup.step.mode.body",
    "test": "setup.step.test.body",
}


def step_labels() -> dict[str, str]:
    """Localised step titles (regenerated on every render)."""
    return {key: i18n.t(value) for key, value in STEP_LABELS.items()}


def details(key: str) -> str | None:
    detail_key = _DETAIL_KEYS.get(key)
    return i18n.t(detail_key) if detail_key else None


def _status() -> dict:
    conns = business_service.real_connections()
    can_reply = any(bool(c["is_enabled"]) and bool(c["can_reply"]) for c in conns)
    content = len(database.list_kb_items()) + faq_service.count()
    mode = "off"
    if database.get_bool("auto_reply_enabled"):
        mode = "draft" if database.get_bool("approval_mode_enabled") else "auto"
    return {
        "secretary": bool(conns),          # proxy: a connection implies business mode
        "business": can_reply,
        "ai": ai_service.is_ready(),
        "content": content > 0,
        # Direct messages are answered even with no Business connection at all.
        "mode": mode != "off" or database.get_bool("direct_reply_enabled"),
        "test": database.count_ai_replies() > 0,
    }


def render_checklist() -> str:
    state = _status()
    lines = [i18n.t("setup.title"), ""]
    for key, label in step_labels().items():
        icon = "✅" if state.get(key) else "⬜"
        lines.append(f"{icon} {label}")
    lines.append("")
    if state["business"]:
        lines.append(i18n.t("setup.connection.live"))
    elif business_service.real_connections():
        lines.append(i18n.t("setup.connection.readonly"))
    else:
        lines.append(i18n.t("setup.connection.none"))
    if database.get_bool("direct_reply_enabled"):
        lines.append(i18n.t("setup.direct"))
    lines.append("")
    lines.append(i18n.t("setup.tap_hint"))
    return "\n".join(lines)


def send_checklist(chat_id: int) -> None:
    handlers.bot.send_message(chat_id, render_checklist(), parse_mode="HTML",
                              reply_markup=keyboards.setup_checklist(step_labels()))


def send_step(chat_id: int, key: str) -> None:
    detail = details(key)
    if detail is None:
        return send_checklist(chat_id)
    extra = []
    if key == "ai":
        extra.append(i18n.t("setup.extra.current",
                            value=" · ".join(ai_service.status_lines())))
    elif key == "content":
        extra.append(i18n.t("setup.extra.content",
                            items=len(database.list_kb_items()),
                            faq=faq_service.count()))
    elif key == "business":
        extra.append(i18n.t("setup.extra.connections",
                            count=len(business_service.real_connections())))
    text = detail + ("\n\n" + "\n".join(utils.escape(line) for line in extra) if extra else "")
    handlers.bot.send_message(chat_id, text, parse_mode="HTML",
                              reply_markup=keyboards.setup_checklist(step_labels()))

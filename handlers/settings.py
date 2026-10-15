"""Settings menu: a declarative registry rendered as an inline keyboard with
in-place editing, grouped so the panel stays readable.

Types
-----
bool    toggle in place
enum    open a choice list
int     captured through the owner pending-input flow (range validated)
float   same as int, decimal
str     single-line text via the pending-input flow
text    free text (used for descriptions/instructions; newlines allowed)
"""

from __future__ import annotations

import logging

import database
import handlers
import keyboards
import security
import telegram_api
import utils
from services import ai_service, providers

log = logging.getLogger("smartel.settings")

GROUPS = {
    "reply": "🤖 Replies & behaviour",
    "persona": "🧑‍💼 Persona & language",
    "ai": "🧠 AI model",
    "ground": "📚 Answers (FAQ / knowledge base)",
    "limits": "🛡️ Safety & limits",
}

SETTINGS = [
    # --- replies & behaviour --------------------------------------------------
    {"key": "auto_reply_enabled", "group": "reply", "label": "Auto-reply", "type": "bool"},
    {"key": "approval_mode_enabled", "group": "reply", "label": "Approval (draft) mode",
     "type": "bool"},
    {"key": "sensitive_requires_approval", "group": "reply", "label": "Sensitive → approval",
     "type": "bool"},
    {"key": "monitoring_mode", "group": "reply", "label": "Notify me about activity",
     "type": "bool"},
    {"key": "memory_enabled", "group": "reply", "label": "Conversation memory", "type": "bool"},
    {"key": "typing_indicator", "group": "reply", "label": "Typing indicator", "type": "bool"},
    {"key": "reply_debounce_seconds", "group": "reply", "label": "Batch messages (seconds)",
     "type": "float", "min": 0.0, "max": 8.0},
    {"key": "process_nontext_enabled", "group": "reply", "label": "Read media captions",
     "type": "bool"},
    {"key": "nontext_ack_message", "group": "reply", "label": "Non-text auto-reply",
     "type": "text", "hint": "Sent when a customer sends a photo/voice without text. "
                             "Empty = never answer automatically."},
    {"key": "greet_new_customers", "group": "reply", "label": "Welcome new customers",
     "type": "bool"},
    {"key": "welcome_text", "group": "reply", "label": "Welcome message", "type": "text"},
    {"key": "owner_takeover_pause_minutes", "group": "reply", "label": "Takeover pause (min)",
     "type": "int", "min": 1, "max": 100000},
    {"key": "max_messages_per_customer_per_hour", "group": "reply", "label": "Rate limit / hour",
     "type": "int", "min": 1, "max": 100000},
    {"key": "public_direct_bot_chat_enabled", "group": "reply", "label": "Direct-DM notice",
     "type": "bool"},

    # --- persona --------------------------------------------------------------
    {"key": "assistant_name", "group": "persona", "label": "Assistant name", "type": "str",
     "hint": "How the assistant refers to itself, e.g. “Sara”."},
    {"key": "business_name", "group": "persona", "label": "Business name", "type": "str"},
    {"key": "business_description", "group": "persona", "label": "What the business does",
     "type": "text", "hint": "One or two sentences the AI uses as context."},
    {"key": "tone", "group": "persona", "label": "Tone", "type": "enum",
     "choices": ["friendly", "professional", "casual", "concise", "warm"]},
    {"key": "reply_language", "group": "persona", "label": "Reply language", "type": "enum",
     "choices": ["auto", "ar", "en", "fr", "es", "de", "tr", "fa", "ur", "ru", "id", "hi", "zh"]},
    {"key": "signature", "group": "persona", "label": "Signature", "type": "text",
     "hint": "Appended to every reply. Empty = no signature."},
    {"key": "max_reply_chars", "group": "persona", "label": "Max reply length", "type": "int",
     "min": 80, "max": 4096},
    {"key": "disclose_ai", "group": "persona", "label": "May say it is an AI", "type": "bool"},
    {"key": "custom_instructions", "group": "persona", "label": "Extra instructions",
     "type": "text", "hint": "Always added to the AI prompt (also via /instructions)."},

    # --- AI model -------------------------------------------------------------
    {"key": "temperature", "group": "ai", "label": "Temperature", "type": "float",
     "min": 0.0, "max": 2.0},
    {"key": "max_tokens", "group": "ai", "label": "Max tokens", "type": "int",
     "min": 1, "max": 8192},
    {"key": "ai_base_url", "group": "ai", "label": "Custom base URL", "type": "str"},

    # --- grounding ------------------------------------------------------------
    {"key": "faq_enabled", "group": "ground", "label": "Quick answers", "type": "bool"},
    {"key": "faq_direct_reply", "group": "ground", "label": "Exact match sends as-is",
     "type": "bool"},
    {"key": "faq_match_threshold", "group": "ground", "label": "FAQ match strictness (%)",
     "type": "int", "min": 10, "max": 100},
    {"key": "kb_enabled", "group": "ground", "label": "Knowledge base", "type": "bool"},
    {"key": "strict_kb_mode", "group": "ground", "label": "Strict KB mode", "type": "bool"},
]
_BY_KEY = {s["key"]: s for s in SETTINGS}


def register(bot, cfg) -> None:
    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("set:"))
    @security.owner_only_callback
    def _on_settings_callback(call):
        try:
            on_settings_callback(call)
        except Exception:
            log.exception("settings callback failed")
            telegram_api.answer_callback(bot, call.id, "Error.")


# =============================================================================
# Rendering
# =============================================================================
def _format_value(spec) -> str:
    value = database.get_setting(spec["key"])
    if spec["type"] == "bool":
        return "ON" if value else "OFF"
    text = str(value)
    if spec["type"] == "text" or len(text) > 24:
        text = text.replace("\n", " ")[:24] + ("…" if len(text) > 24 else "")
    return text or "—"


def _rows_for_group(group: str) -> list[dict]:
    rows = []
    for spec in SETTINGS:
        if spec.get("group") != group:
            continue
        label = f"{spec['label']}: {_format_value(spec)}"
        if spec["type"] == "bool":
            data = keyboards.cb("set", "toggle", spec["key"])
        elif spec["type"] == "enum":
            data = keyboards.cb("set", "enum", spec["key"])
        elif spec["type"] in ("int", "float"):
            data = keyboards.cb("set", "num", spec["key"])
        else:
            data = keyboards.cb("set", "text", spec["key"])
        rows.append({"label": label, "callback_data": data})
    return rows


def _root_rows() -> list[dict]:
    rows = [{"label": GROUPS[group], "callback_data": keyboards.cb("set", "group", group)}
            for group in GROUPS]
    # AI provider/model are managed by the richer /ai screen.
    provider = ai_service.active_provider()
    rows.insert(3, {
        "label": f"🧠 Provider: {provider.label}",
        "callback_data": keyboards.cb("ai", "root"),
    })
    rows.insert(4, {
        "label": f"🧠 Model: {ai_service.active_model_label()}",
        "callback_data": keyboards.cb("ai", "models"),
    })
    return rows


def _root_text() -> str:
    mode = "off"
    if database.get_bool("auto_reply_enabled"):
        mode = "draft" if database.get_bool("approval_mode_enabled") else "auto"
    return (
        "⚙️ <b>Settings</b>\n"
        f"Reply mode: <b>{mode}</b> (change with /mode) · "
        f"AI: <b>{utils.escape(ai_service.backend_label())}</b>\n"
        "Choose a section:"
    )


def _group_text(group: str) -> str:
    return f"{GROUPS.get(group, '⚙️ Settings')}\nTap a row to change it."


def open_root(message) -> None:
    handlers.bot.send_message(message.chat.id, _root_text(), parse_mode="HTML",
                              reply_markup=keyboards.settings_root(_root_rows()))


def _edit(call, text: str, reply_markup) -> None:
    try:
        handlers.bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                       parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        pass  # "message is not modified" etc.


def _edit_root(call) -> None:
    _edit(call, _root_text(), keyboards.settings_root(_root_rows()))


# =============================================================================
# Callback handling
# =============================================================================
def on_settings_callback(call) -> None:
    bot = handlers.bot
    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "root":
        _edit_root(call)
        return telegram_api.answer_callback(bot, call.id)

    if action == "group":
        group = parts[2]
        _edit(call, _group_text(group), keyboards.settings_root(_rows_for_group(group)))
        return telegram_api.answer_callback(bot, call.id)

    if action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id, "Closed.")

    if action == "toggle":
        key = parts[2]
        new_value = not database.get_bool(key)
        database.set_setting(key, new_value)
        spec = _BY_KEY.get(key, {})
        _back(call, spec, f"{spec.get('label', key)} → {'ON' if new_value else 'OFF'}")
        return telegram_api.answer_callback(
            bot, call.id, f"{spec.get('label', key)} {'ON' if new_value else 'OFF'}")

    if action == "enum":
        key = parts[2]
        spec = _BY_KEY[key]
        choices = list(spec.get("choices", []))
        current = database.get_str(key)
        if current not in choices:
            choices = [current] + choices
        try:
            bot.edit_message_text(
                f"Select <b>{spec['label']}</b>:", call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=keyboards.settings_enum(key, choices, current),
            )
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id)

    if action == "enumval":
        key, choice = parts[2], parts[3]
        database.set_setting(key, choice)
        spec = _BY_KEY.get(key, {})
        _back(call, spec, f"{spec.get('label', key)} → {choice}")
        return telegram_api.answer_callback(bot, call.id, f"{key} → {choice}")

    if action in ("num", "text"):
        key = parts[2]
        spec = _BY_KEY[key]
        kind = {"int": "set_int", "float": "set_float"}.get(spec["type"], "set_text")
        database.set_owner_pending_input(security.owner_id(), kind, {"key": key}, 10)
        hint = spec.get("hint", "")
        rng = ""
        if "min" in spec and "max" in spec:
            rng = f" (allowed {spec['min']}–{spec['max']})"
        text = (f"Send the new value for <b>{spec['label']}</b>{rng}."
                + (f"\n<i>{utils.escape(hint)}</i>" if hint else "")
                + "\n\n/cancel to abort.")
        handlers.notify_owner(text)
        return telegram_api.answer_callback(bot, call.id, "Waiting for a value…")

    telegram_api.answer_callback(bot, call.id)


def _back(call, spec, status: str) -> None:
    """Return to the section the edited row belongs to, with a fresh status line."""
    group = spec.get("group", "reply")
    try:
        handlers.bot.edit_message_text(
            _group_text(group) + f"\n\n<b>{utils.escape(status)}</b>",
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML", reply_markup=keyboards.settings_root(_rows_for_group(group)),
        )
    except Exception:
        pass


# =============================================================================
# Pending-input application (numbers & free text)
# =============================================================================
def apply_pending(message, kind: str, context: dict) -> None:
    owner = security.owner_id()
    database.clear_owner_pending_input(owner)
    key = context.get("key")
    spec = _BY_KEY.get(key)
    if spec is None:
        return
    raw = (getattr(message, "text", "") or getattr(message, "caption", "") or "").strip()
    if not raw:
        return handlers.notify_owner("Empty value — nothing changed.")

    if kind == "set_text":
        database.set_setting(key, raw)
        return handlers.notify_owner(
            f"✅ {spec['label']} updated:\n<b>{utils.escape(raw[:400])}</b>")

    try:
        value = int(raw) if kind == "set_int" else float(raw)
    except ValueError:
        return handlers.notify_owner(f"'{utils.escape(raw)}' is not a valid number. "
                                     f"{spec['label']} unchanged.")
    lo, hi = spec.get("min"), spec.get("max")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return handlers.notify_owner(
            f"Value must be between {lo} and {hi}. {spec['label']} unchanged.")
    database.set_setting(key, value)
    handlers.notify_owner(f"✅ {spec['label']} set to <b>{value}</b>.")

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

Every row points at an i18n key (``set.opt.<setting>``) so the panel follows the
owner's interface language (/language); the stored setting *values* stay in their
internal English form (``friendly``, ``auto``, ``ar`` …).
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
from services import ai_service, providers

log = logging.getLogger("smartel.settings")

_GROUP_KEYS = {
    "reply": "set.group.reply",
    "persona": "set.group.persona",
    "lang": "set.group.lang",
    "ai": "set.group.ai",
    "ground": "set.group.ground",
    "limits": "set.group.limits",
}

SETTINGS = [
    # --- replies & behaviour --------------------------------------------------
    {"key": "auto_reply_enabled", "group": "reply", "type": "bool"},
    {"key": "approval_mode_enabled", "group": "reply", "type": "bool"},
    {"key": "sensitive_requires_approval", "group": "reply", "type": "bool"},
    {"key": "monitoring_mode", "group": "reply", "type": "bool"},
    {"key": "memory_enabled", "group": "reply", "type": "bool"},
    {"key": "typing_indicator", "group": "reply", "type": "bool"},
    {"key": "process_nontext_enabled", "group": "reply", "type": "bool"},
    {"key": "nontext_ack_message", "group": "reply", "type": "text",
     "hint_key": "set.opt.nontext_ack_message.hint"},
    {"key": "greet_new_customers", "group": "reply", "type": "bool"},
    {"key": "welcome_text", "group": "reply", "type": "text"},
    {"key": "direct_reply_enabled", "group": "reply", "type": "bool",
     "hint_key": "set.opt.direct_reply_enabled.hint"},
    {"key": "public_direct_bot_chat_enabled", "group": "reply", "type": "bool"},

    # --- persona --------------------------------------------------------------
    {"key": "assistant_name", "group": "persona", "type": "str",
     "hint_key": "set.opt.assistant_name.hint"},
    {"key": "business_name", "group": "persona", "type": "str"},
    {"key": "business_description", "group": "persona", "type": "text",
     "hint_key": "set.opt.business_description.hint"},
    {"key": "tone", "group": "persona", "type": "enum",
     "choices": ["friendly", "professional", "casual", "concise", "warm"],
     "choice_prefix": "set.tone."},
    {"key": "reply_language", "group": "persona", "type": "enum",
     "choices": ["auto", "ar", "en", "fr", "es", "de", "tr", "fa", "ur", "ru",
                 "id", "hi", "zh"],
     "choice_prefix": "set.lang."},
    {"key": "signature", "group": "persona", "type": "text",
     "hint_key": "set.opt.signature.hint"},
    {"key": "disclose_ai", "group": "persona", "type": "bool"},
    {"key": "custom_instructions", "group": "persona", "type": "text",
     "hint_key": "set.opt.custom_instructions.hint"},
    {"key": "reply_priorities", "group": "persona", "type": "text",
     "hint_key": "set.opt.reply_priorities.hint"},
    {"key": "never_reply_rules", "group": "persona", "type": "text",
     "hint_key": "set.opt.never_reply_rules.hint"},

    # --- language of the bot itself -------------------------------------------
    {"key": "ui_language", "group": "lang", "type": "enum",
     "choices": list(i18n.LANGUAGES),
     "hint_key": "set.opt.ui_language.hint"},

    # --- AI model -------------------------------------------------------------
    {"key": "temperature", "group": "ai", "type": "float", "min": 0.0, "max": 2.0},
    {"key": "max_tokens", "group": "ai", "type": "int", "min": 1, "max": 8192},
    {"key": "ai_base_url", "group": "ai", "type": "str"},

    # --- grounding ------------------------------------------------------------
    {"key": "faq_enabled", "group": "ground", "type": "bool"},
    {"key": "faq_direct_reply", "group": "ground", "type": "bool"},
    {"key": "faq_match_threshold", "group": "ground", "type": "int", "min": 10, "max": 100,
     "hint_key": "set.opt.faq_match_threshold.hint"},
    {"key": "kb_enabled", "group": "ground", "type": "bool"},
    {"key": "strict_kb_mode", "group": "ground", "type": "bool"},

    # --- limits & timing ------------------------------------------------------
    {"key": "max_reply_chars", "group": "limits", "type": "int", "min": 80, "max": 4096},
    {"key": "reply_debounce_seconds", "group": "limits", "type": "float",
     "min": 0.0, "max": 8.0},
    {"key": "max_messages_per_customer_per_hour", "group": "limits", "type": "int",
     "min": 1, "max": 100000},
    {"key": "owner_takeover_pause_minutes", "group": "limits", "type": "int",
     "min": 1, "max": 100000},
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
            telegram_api.answer_callback(bot, call.id, i18n.t("set.error"))


# =============================================================================
# Rendering
# =============================================================================
def label_of(spec) -> str:
    return i18n.t(f"set.opt.{spec['key']}")


def _choice_label(spec, choice: str) -> str:
    prefix = spec.get("choice_prefix")
    if not prefix:
        return choice
    key = f"{prefix}{choice}"
    rendered = i18n.t(key)
    return choice if rendered == key else rendered


def _format_value(spec) -> str:
    value = database.get_setting(spec["key"])
    if spec["type"] == "bool":
        return i18n.t("set.value.on") if value else i18n.t("set.value.off")
    if spec.get("choice_prefix"):
        return _choice_label(spec, str(value))
    text = str(value)
    if spec["type"] == "text" or len(text) > 24:
        text = text.replace("\n", " ")[:24] + ("…" if len(text) > 24 else "")
    return text or "—"


def _rows_for_group(group: str) -> list[dict]:
    rows = []
    for spec in SETTINGS:
        if spec.get("group") != group:
            continue
        label = f"{label_of(spec)}: {_format_value(spec)}"
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
    primary = security.is_primary_admin(security.operator_id())
    rows = [{"label": i18n.t(_GROUP_KEYS[group]),
             "callback_data": keyboards.cb("set", "group", group)}
            for group in _GROUP_KEYS if primary or group != "ai"]
    # Delegated admins can add/test their own key for the primary-selected model,
    # but only the primary can switch providers or models.
    provider = ai_service.active_provider()
    rows.insert(3, {
        "label": i18n.t("set.provider_row" if primary else "set.connection_row",
                        label=provider.label),
        "callback_data": keyboards.cb("ai", "root"),
    })
    if primary:
        rows.insert(4, {
            "label": i18n.t("set.model_row", model=ai_service.active_model_label()),
            "callback_data": keyboards.cb("ai", "models"),
        })
        if not ai_service.is_ready() or providers.needs_credit(provider.id):
            rows.insert(5, {
                "label": i18n.t("set.free_ai_row"),
                "callback_data": keyboards.cb("ai", "providers_free"),
            })
    return rows


def _mode() -> str:
    if not database.get_bool("auto_reply_enabled"):
        return "off"
    return "draft" if database.get_bool("approval_mode_enabled") else "auto"


def _root_text() -> str:
    return i18n.t(
        "set.title",
        mode=_mode(),
        backend=utils.escape(ai_service.backend_label()),
    )


def _group_text(group: str) -> str:
    return i18n.t("set.section_hint", title=i18n.t(_GROUP_KEYS.get(group, "set.title_plain")))


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
    primary = security.is_primary_admin(security.operator_id())
    if not primary and action == "group" and len(parts) > 2 and parts[2] == "ai":
        return telegram_api.answer_callback(
            bot, call.id, i18n.t("set.primary_only"), show_alert=True,
        )
    if (not primary and action in {"enum", "num", "text", "enumval"}
            and len(parts) > 2 and parts[2] in {"ai_provider", "ai_model_by_provider",
                                                "ai_base_url", "temperature", "max_tokens"}):
        return telegram_api.answer_callback(
            bot, call.id, i18n.t("set.primary_only"), show_alert=True,
        )

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
        return telegram_api.answer_callback(bot, call.id, i18n.t("set.closed"))

    if action == "toggle":
        key = parts[2]
        new_value = not database.get_bool(key)
        database.set_setting(key, new_value)
        spec = _BY_KEY.get(key, {"key": key})
        state = i18n.t("set.value.on") if new_value else i18n.t("set.value.off")
        _back(call, spec, i18n.t("set.saved_value", label=label_of(spec), value=state))
        return telegram_api.answer_callback(
            bot, call.id, i18n.t("set.toggle_alert", label=label_of(spec), state=state))

    if action == "enum":
        key = parts[2]
        spec = _BY_KEY[key]
        choices = list(spec.get("choices", []))
        current = database.get_str(key)
        if current not in choices:
            choices = [current] + choices
        try:
            bot.edit_message_text(
                i18n.t("set.enum_title", label=label_of(spec)),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
                reply_markup=keyboards.settings_enum(key, choices, current,
                                                     labels=_choice_labels(spec, choices)),
            )
        except Exception:
            pass
        return telegram_api.answer_callback(bot, call.id)

    if action == "enumval":
        key, choice = parts[2], parts[3]
        if key == "ui_language":
            # Routed through i18n so the caches and the Telegram command menu
            # follow along (see handlers/owner_commands.cmd_language).
            i18n.set_language(choice)
            from handlers import owner_commands
            owner_commands._republish_commands()
        else:
            database.set_setting(key, choice)
        spec = _BY_KEY.get(key, {"key": key})
        _back(call, spec, i18n.t("set.saved_value", label=label_of(spec),
                                 value=_choice_label(spec, choice)))
        return telegram_api.answer_callback(
            bot, call.id, i18n.t("set.saved_value", label=label_of(spec),
                                 value=_choice_label(spec, choice)))

    if action in ("num", "text"):
        key = parts[2]
        spec = _BY_KEY[key]
        kind = {"int": "set_int", "float": "set_float"}.get(spec["type"], "set_text")
        database.set_owner_pending_input(security.operator_id(), kind, {"key": key}, 10)
        hint = i18n.t(spec["hint_key"]) if spec.get("hint_key") else ""
        if hint == spec.get("hint_key"):
            hint = ""
        rng = ""
        if "min" in spec and "max" in spec:
            rng = i18n.t("set.prompt_range", min=spec["min"], max=spec["max"])
        text = i18n.t("set.prompt_value", label=label_of(spec), range=rng,
                      hint=f"\n<i>{utils.escape(hint)}</i>" if hint else "")
        handlers.notify_owner(text)
        return telegram_api.answer_callback(bot, call.id, i18n.t("set.waiting"))

    telegram_api.answer_callback(bot, call.id)


def _choice_labels(spec, choices: list[str]) -> dict[str, str]:
    if not spec.get("choice_prefix"):
        return {}
    return {choice: _choice_label(spec, choice) for choice in choices}


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
    owner = security.operator_id()
    database.clear_owner_pending_input(owner)
    key = context.get("key")
    spec = _BY_KEY.get(key)
    if spec is None:
        return
    raw = (getattr(message, "text", "") or getattr(message, "caption", "") or "").strip()
    if not raw:
        return handlers.notify_owner(i18n.t("set.empty"))

    if kind == "set_text":
        database.set_setting(key, raw)
        return handlers.notify_owner(
            i18n.t("set.text_saved", label=label_of(spec), value=utils.escape(raw[:400])))

    try:
        value = int(raw) if kind == "set_int" else float(raw)
    except ValueError:
        return handlers.notify_owner(
            i18n.t("set.not_number", raw=utils.escape(raw), label=label_of(spec)))
    lo, hi = spec.get("min"), spec.get("max")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return handlers.notify_owner(
            i18n.t("set.out_of_range", low=lo, high=hi, label=label_of(spec)))
    database.set_setting(key, value)
    handlers.notify_owner(i18n.t("set.number_saved", label=label_of(spec), value=value))

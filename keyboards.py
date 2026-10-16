"""Inline keyboard builders. Callback-data scheme (kept well under Telegram's
64-byte limit; never embeds free text):

  panel:<action>            control panel
  set:<action>[:key[:val]]  settings menu
  apr:<action>:<id>         approval actions
  kb:<action>[:id[:page]]   knowledge base
  ai:<action>[:arg]         AI provider setup (/ai)
  faq:<action>[:id[:page]]  FAQ / canned answers
  tool:<action>[:arg]       owner tools (mode, chats, setup, health)
  rule:<action>[:arg]       topic rules (/rules)
  res:<action>[:arg]        resources (/resources)
  unans:<action>[:arg]      unanswered questions
  gate:<action>[:arg]       entry gates (/gate)
  confirm:<yes|no>:<token>  destructive confirmations
"""

from __future__ import annotations

from telebot import types

import i18n


def cb(*parts) -> str:
    data = ":".join(str(p) for p in parts)
    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"callback_data too long: {data!r}")
    return data


def _btn(text: str, data: str, style: str = "primary") -> types.InlineKeyboardButton:
    """Telegram inline-button color: primary=blue, success=green, danger=red."""
    return types.InlineKeyboardButton(text, callback_data=data, style=style)


# =============================================================================
# Control panel
# =============================================================================
_MODE_KEYS = {"auto": "kbd.mode.auto", "draft": "kbd.mode.draft", "off": "kbd.mode.off"}


def mode_label(mode: str) -> str:
    """Localised label of a reply mode."""
    return i18n.t(_MODE_KEYS.get(mode, "kbd.mode.off"))


def control_panel(auto_on: bool, approval_on: bool, mode: str | None = None) -> types.InlineKeyboardMarkup:
    if mode is None:
        mode = "auto" if (auto_on and not approval_on) else ("draft" if auto_on else "off")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn(i18n.t("kbd.panel.status"), cb("panel", "status")),
        _btn(i18n.t("kbd.panel.help"), cb("panel", "help")),
    )
    kb.add(_btn(i18n.t("kbd.mode_row", label=mode_label(mode)), cb("panel", "mode"),
         "success" if mode == "auto" else ("danger" if mode == "off" else "primary")))
    kb.add(
        _btn(i18n.t("kbd.panel.ai"), cb("ai", "root")),
        _btn(i18n.t("kbd.panel.faq"), cb("faq", "menu")),
    )
    kb.add(
        _btn(i18n.t("kbd.panel.kb"), cb("kb", "menu")),
        _btn(i18n.t("kbd.panel.settings"), cb("set", "root")),
    )
    kb.add(
        _btn(i18n.t("kbd.panel.pending"), cb("panel", "pending")),
        _btn(i18n.t("kbd.panel.mem_clear"), cb("panel", "mem_clear"), "danger"),
    )
    kb.add(
        _btn(i18n.t("kbd.panel.setup"), cb("tool", "setup")),
        _btn(i18n.t("kbd.panel.health"), cb("tool", "health")),
    )
    return kb


def mode_keyboard(current: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mode in ("auto", "draft", "off"):
        mark = "• " if mode == current else ""
        kb.add(_btn(f"{mark}{mode_label(mode)}", cb("panel", "mode_set", mode),
                    "success" if mode == "auto" else ("danger" if mode == "off" else "primary")))
    kb.add(_btn(i18n.t("kbd.back"), cb("panel", "home")))
    return kb


# =============================================================================
# AI provider setup
# =============================================================================
def ai_root(has_key: bool, is_ready: bool, provider_label: str,
            primary_admin: bool = True) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    if primary_admin:
        kb.add(_btn(i18n.t("kbd.ai.free_providers"), cb("ai", "providers_free")))
        kb.add(_btn(i18n.t("kbd.ai.change_provider"), cb("ai", "providers")))
        kb.add(_btn(i18n.t("kbd.ai.change_model"), cb("ai", "models")))
        kb.add(_btn(i18n.t("kbd.ai.load_models"), cb("ai", "models_live")))
    kb.add(_btn(i18n.t("kbd.ai.add_key"), cb("ai", "key"), "success"))
    kb.add(_btn(i18n.t("kbd.ai.test"), cb("ai", "test"), "success"))
    if has_key:
        kb.add(_btn(i18n.t("kbd.ai.remove_key"), cb("ai", "disconnect"), "danger"))
    kb.add(_btn(i18n.t("kbd.close"), cb("ai", "close")))
    return kb


def _provider_label(provider, active_id: str) -> str:
    mark = "• " if provider.id == active_id else ""
    label = f"{mark}{provider.label}"
    if provider.local:
        label += "  💻"
    elif provider.free_tier:
        label += "  🆓"
    elif not provider.key_required:
        label += "  🔓"
    return label


def ai_providers(active_id: str, free_only: bool = False) -> types.InlineKeyboardMarkup:
    """Provider picker. ``free_only`` shows just the zero-cost options."""
    from services import providers as _providers
    kb = types.InlineKeyboardMarkup(row_width=1)
    shown = _providers.free() if free_only else _providers.ordered()
    for provider in shown:
        kb.add(_btn(_provider_label(provider, active_id), cb("ai", "provider", provider.id)))
    if free_only:
        kb.add(_btn(i18n.t("kbd.ai.show_every"), cb("ai", "providers")))
    else:
        kb.add(_btn(i18n.t("kbd.ai.only_free"), cb("ai", "providers_free")))
    kb.add(_btn(i18n.t("kbd.back"), cb("ai", "root")))
    return kb


def ai_free_switch(suggestions, active_id: str = "") -> types.InlineKeyboardMarkup:
    """"Switch to this free provider" buttons, shown after a key/quota failure.

    One tap moves the owner to a working free backend and asks for its key.
    """
    kb = types.InlineKeyboardMarkup(row_width=1)
    for provider in suggestions:
        if provider.key_required:
            text = i18n.t("kbd.ai.switch", label=provider.label)
        else:
            text = i18n.t("kbd.ai.switch_nokey", label=provider.label)
        kb.add(_btn(text, cb("ai", "freeswitch", provider.id)))
    kb.add(_btn(i18n.t("kbd.ai.resend_key"), cb("ai", "key")))
    kb.add(_btn(i18n.t("kbd.ai.back_menu"), cb("ai", "root")))
    return kb


def ai_models(models: list[str], current: str, can_refresh: bool = True,
              ) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for model in models:
        mark = "• " if model == current else ""
        try:
            data = cb("ai", "model", model)
        except ValueError:
            continue          # Telegram callback data is capped at 64 bytes
        kb.add(_btn(f"{mark}{model[:58]}", data))
    if can_refresh:
        kb.add(_btn(i18n.t("kbd.ai.load_models"), cb("ai", "models_live")))
    kb.add(_btn(i18n.t("kbd.ai.type_model"), cb("ai", "model_custom")))
    kb.add(_btn(i18n.t("kbd.back"), cb("ai", "root")))
    return kb


def ai_provider_actions(provider_id: str, key_required: bool) -> types.InlineKeyboardMarkup:
    from services import providers as _providers
    # Some endpoints need no key but still accept one (self-hosted OmniRoute with
    # REQUIRE_API_KEY=true); Ollama/LM Studio expose no key env var at all.
    optional_key = not key_required and bool(_providers.key_env_var(provider_id))
    kb = types.InlineKeyboardMarkup(row_width=1)
    if key_required:
        kb.add(_btn(i18n.t("kbd.ai.send_key"), cb("ai", "key")))
    elif optional_key:
        kb.add(_btn(i18n.t("kbd.ai.send_key_optional"), cb("ai", "key")))
    kb.add(_btn(i18n.t("kbd.ai.choose_model"), cb("ai", "models")))
    kb.add(_btn(i18n.t("kbd.ai.load_models"), cb("ai", "models_live")))
    if provider_id == "custom":
        kb.add(_btn(i18n.t("kbd.ai.set_base_url"), cb("ai", "base_url")))
    kb.add(_btn(i18n.t("kbd.ai.test"), cb("ai", "test"), "success"))
    if not _providers.get(provider_id) or not _providers.is_free(
            _providers.get_or_default(provider_id)):
        kb.add(_btn(i18n.t("kbd.ai.free_instead"), cb("ai", "providers_free")))
    kb.add(_btn(i18n.t("kbd.back"), cb("ai", "providers")))
    return kb


# =============================================================================
# FAQ / canned answers
# =============================================================================
def faq_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn(i18n.t("kbd.faq.add"), cb("faq", "add"), "success"))
    kb.add(_btn(i18n.t("kbd.faq.list"), cb("faq", "list", 0)))
    kb.add(_btn(i18n.t("kbd.faq.search"), cb("faq", "search")))
    kb.add(_btn(i18n.t("kbd.faq.export"), cb("faq", "export")))
    kb.add(_btn(i18n.t("kbd.faq.clear"), cb("faq", "clear"), "danger"))
    kb.add(_btn(i18n.t("kbd.close"), cb("faq", "close")))
    return kb


def faq_list(entries: list, page: int, per_page: int = 5) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    for entry in entries[start:start + per_page]:
        title = (entry["keywords"] or "")[:28]
        state = "• " if entry["enabled"] else "✖ "
        kb.add(_btn(i18n.t("kbd.faq.entry", state=state, title=title),
                    cb("faq", "del", entry["id"], page), "danger"))
    nav = []
    if page > 0:
        nav.append(_btn(i18n.t("kbd.prev"), cb("faq", "list", page - 1)))
    if start + per_page < len(entries):
        nav.append(_btn(i18n.t("kbd.next"), cb("faq", "list", page + 1)))
    if nav:
        kb.row(*nav)
    kb.add(_btn(i18n.t("kbd.back"), cb("faq", "menu")))
    return kb


# =============================================================================
# Owner tools
# =============================================================================
def chats_list(rows: list[dict]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        kb.add(_btn(row["label"], cb("tool", "chat", row["chat_id"])))
    kb.add(_btn(i18n.t("kbd.close"), cb("tool", "close")))
    return kb


def chat_actions(chat_id: int, paused: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    if paused:
        kb.add(_btn(i18n.t("kbd.chat.resume"), cb("tool", "resume", chat_id), "success"))
    else:
        kb.add(_btn(i18n.t("kbd.chat.pause"), cb("tool", "pause", chat_id), "danger"))
    kb.add(_btn(i18n.t("kbd.close"), cb("tool", "close")))
    return kb


def setup_checklist(steps: dict) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, label in steps.items():
        kb.add(_btn(label, cb("tool", "setup_step", key)))
    kb.add(_btn(i18n.t("kbd.close"), cb("tool", "close")))
    return kb


# =============================================================================
# Approvals
# =============================================================================
def approval_actions(approval_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn(i18n.t("kbd.apr.send"), cb("apr", "send", approval_id), "success"),
        _btn(i18n.t("kbd.apr.edit"), cb("apr", "edit", approval_id)),
    )
    kb.add(
        _btn(i18n.t("kbd.apr.reject"), cb("apr", "reject", approval_id), "danger"),
        _btn(i18n.t("kbd.apr.pause"), cb("apr", "pause", approval_id), "danger"),
    )
    return kb


# =============================================================================
# Settings
# =============================================================================
def settings_root(rows: list[dict]) -> types.InlineKeyboardMarkup:
    """rows: list of {"label": str, "callback_data": str}."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        kb.add(_btn(r["label"], r["callback_data"]))
    kb.add(_btn(i18n.t("kbd.close"), cb("set", "close")))
    return kb


def settings_enum(key: str, choices: list[str], current: str,
                  labels: dict | None = None) -> types.InlineKeyboardMarkup:
    """Choice list for an enum setting. ``labels`` localises the shown text while
    the callback data keeps the stored (English) value."""
    labels = labels or {}
    kb = types.InlineKeyboardMarkup(row_width=1)
    for choice in choices:
        mark = "• " if choice == current else ""
        kb.add(_btn(f"{mark}{labels.get(choice, choice)}",
                    cb("set", "enumval", key, choice)))
    kb.add(_btn(i18n.t("kbd.back"), cb("set", "root")))
    return kb


# =============================================================================
# Knowledge base
# =============================================================================
def kb_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn(i18n.t("kbd.kb.add"), cb("kb", "add"), "success"),
        _btn(i18n.t("kbd.kb.upload"), cb("kb", "upload"), "success"),
    )
    kb.add(
        _btn(i18n.t("kbd.kb.search"), cb("kb", "search")),
        _btn(i18n.t("kbd.kb.list"), cb("kb", "list", 0)),
    )
    kb.add(_btn(i18n.t("kbd.kb.clear"), cb("kb", "clear"), "danger"))
    kb.add(_btn(i18n.t("kbd.close"), cb("kb", "close")))
    return kb


def kb_list_keyboard(items: list, page: int, per_page: int = 5) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    page_items = items[start : start + per_page]
    for item in page_items:
        title = (item["title"] or i18n.t("kbd.kb.untitled"))[:30]
        kb.add(_btn(i18n.t("kbd.kb.item", id=item["id"], title=title,
                           count=item["chunk_count"]),
                    cb("kb", "del", item["id"], page), "danger"))
    nav = []
    if page > 0:
        nav.append(_btn(i18n.t("kbd.prev"), cb("kb", "list", page - 1)))
    if start + per_page < len(items):
        nav.append(_btn(i18n.t("kbd.next"), cb("kb", "list", page + 1)))
    if nav:
        kb.row(*nav)
    kb.add(_btn(i18n.t("kbd.back"), cb("kb", "menu")))
    return kb


# =============================================================================
# Language picker
# =============================================================================
def language_menu(current: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for code, label in i18n.LANGUAGES.items():
        mark = "• " if code == current else ""
        kb.add(_btn(f"{mark}{label}", cb("set", "enumval", "ui_language", code)))
    return kb


# =============================================================================
# Confirmation
# =============================================================================
# =============================================================================
# Rules, resources, unanswered questions, gates
# =============================================================================
def rules_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        _btn(i18n.t("kbd.rule.add"), cb("rule", "add")),
        _btn(i18n.t("kbd.rule.list"), cb("rule", "list", 0)),
        _btn(i18n.t("kbd.rule.ask_questions"), cb("unans", "list", 0)),
    )
    kb.add(_btn(i18n.t("kbd.close"), cb("rule", "close")))
    return kb


def rules_draft(batch: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        _btn(i18n.t("kbd.rule.approve"), cb("rule", "ok", batch), "success"),
        _btn(i18n.t("kbd.rule.edit"), cb("rule", "edit", batch)),
        _btn(i18n.t("kbd.rule.discard"), cb("rule", "no", batch), "danger"),
    )
    return kb


def rules_list(rows: list) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        mark = "✅" if row["enabled"] else "⏸"
        kb.add(_btn(f"{mark} #{row['id']} {(row['topic'] or row['rule'])[:40]}",
                    cb("rule", "toggle", row["id"])))
    kb.add(_btn(i18n.t("kbd.back"), cb("rule", "root")))
    kb.add(_btn(i18n.t("kbd.close"), cb("rule", "close")))
    return kb


def resources_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        _btn(i18n.t("kbd.res.add"), cb("res", "add")),
        _btn(i18n.t("kbd.res.list"), cb("res", "list")),
    )
    kb.add(_btn(i18n.t("kbd.close"), cb("res", "close")))
    return kb


def resources_list(rows: list) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        mark = "✅" if row["enabled"] else "⏸"
        icon = {"telegram": "📣", "link": "🔗", "text": "📄"}.get(row["kind"], "🔗")
        kb.add(_btn(f"{mark} {icon} #{row['id']} {(row['title'] or row['url'])[:34]}",
                    cb("res", "toggle", row["id"])))
    kb.add(_btn(i18n.t("kbd.back"), cb("res", "root")))
    kb.add(_btn(i18n.t("kbd.close"), cb("res", "close")))
    return kb


def unanswered_list(rows: list, page: int = 0, per_page: int = 5) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    for row in rows[start:start + per_page]:
        question = (row["question"] or "").replace("\n", " ")[:44]
        kb.add(_btn(f"#{row['id']} {question}", cb("unans", "open", row["id"])))
    nav = []
    if page > 0:
        nav.append(_btn(i18n.t("kbd.prev"), cb("unans", "list", page - 1)))
    if start + per_page < len(rows):
        nav.append(_btn(i18n.t("kbd.next"), cb("unans", "list", page + 1)))
    if nav:
        kb.add(*nav)
    kb.add(_btn(i18n.t("kbd.close"), cb("unans", "close")))
    return kb


def unanswered_card(question_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        _btn(i18n.t("kbd.unans.answer"), cb("unans", "answer", question_id), "success"),
        _btn(i18n.t("kbd.unans.ignore"), cb("unans", "ignore", question_id), "danger"),
        _btn(i18n.t("kbd.back"), cb("unans", "list", 0)),
    )
    return kb


def gate_menu(stats: dict) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn(i18n.t("kbd.gate.subscription"), cb("gate", "sub")))
    kb.add(_btn(i18n.t("kbd.gate.stars"), cb("gate", "stars")))
    kb.add(_btn(i18n.t("kbd.gate.list"), cb("gate", "list")))
    kb.add(_btn(i18n.t("kbd.close"), cb("gate", "close")))
    return kb


def required_channels(rows: list) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        mark = "✅" if row["enabled"] else "⏸"
        kb.add(_btn(f"{mark} {row['title'] or row['chat_ref']}",
                    cb("gate", "toggle_channel", row["id"])))
    kb.add(_btn(i18n.t("kbd.gate.add_channel"), cb("gate", "add_channel")))
    kb.add(_btn(i18n.t("kbd.back"), cb("gate", "root")))
    return kb


def pay_button(stars: int, payload: str) -> types.InlineKeyboardMarkup:
    """Button that re-opens the Stars invoice for a parked message."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn(i18n.t("kbd.paid.buy", stars=stars), cb("pay", "buy", payload)))
    return kb


def subscription_gate() -> types.InlineKeyboardMarkup:
    """Join buttons + the re-check button shown to a gated visitor."""
    from services import gate_service

    rows = gate_service.join_rows()
    rows.append([_btn(i18n.t("kbd.gate.verify"), cb("gate", "verify"), "success")])
    return types.InlineKeyboardMarkup(rows)


def paid_message_actions(message_id: int) -> types.InlineKeyboardMarkup:
    """Owner-side refund control for a confirmed Stars payment."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn(i18n.t("kbd.gate.refund"), cb("gate", "refund", message_id), "danger"))
    return kb


def confirm(token: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn(i18n.t("kbd.confirm.yes"), cb("confirm", "yes", token), "success"),
        _btn(i18n.t("kbd.confirm.no"), cb("confirm", "no", token), "danger"),
    )
    return kb

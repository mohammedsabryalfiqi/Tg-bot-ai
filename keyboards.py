"""Inline keyboard builders. Callback-data scheme (kept well under Telegram's
64-byte limit; never embeds free text):

  panel:<action>            control panel
  set:<action>[:key[:val]]  settings menu
  apr:<action>:<id>         approval actions
  kb:<action>[:id[:page]]   knowledge base
  ai:<action>[:arg]         AI provider setup (/ai)
  faq:<action>[:id[:page]]  FAQ / canned answers
  tool:<action>[:arg]       owner tools (mode, chats, setup, health)
  confirm:<yes|no>:<token>  destructive confirmations
"""

from __future__ import annotations

from telebot import types


def cb(*parts) -> str:
    data = ":".join(str(p) for p in parts)
    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"callback_data too long: {data!r}")
    return data


def _btn(text: str, data: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text, callback_data=data)


# =============================================================================
# Control panel
# =============================================================================
MODE_LABELS = {
    "auto": "🟢 Auto-reply",
    "draft": "📝 Draft (approve)",
    "off": "🔴 Off",
}


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, MODE_LABELS["off"])


def control_panel(auto_on: bool, approval_on: bool, mode: str | None = None) -> types.InlineKeyboardMarkup:
    if mode is None:
        mode = "auto" if (auto_on and not approval_on) else ("draft" if auto_on else "off")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn("📊 Status", cb("panel", "status")),
        _btn("❓ Help", cb("panel", "help")),
    )
    kb.add(_btn(f"{mode_label(mode)} — tap to change", cb("panel", "mode")))
    kb.add(
        _btn("🤖 AI provider", cb("ai", "root")),
        _btn("💬 Quick answers", cb("faq", "menu")),
    )
    kb.add(
        _btn("📚 Knowledge Base", cb("kb", "menu")),
        _btn("⚙️ Settings", cb("set", "root")),
    )
    kb.add(
        _btn("📨 Pending approvals", cb("panel", "pending")),
        _btn("🧹 Clear memory", cb("panel", "mem_clear")),
    )
    kb.add(
        _btn("🚀 Setup guide", cb("tool", "setup")),
        _btn("❤️ Health check", cb("tool", "health")),
    )
    return kb


def mode_keyboard(current: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mode in ("auto", "draft", "off"):
        mark = "• " if mode == current else ""
        kb.add(_btn(f"{mark}{mode_label(mode)}", cb("panel", "mode_set", mode)))
    kb.add(_btn("« Back", cb("panel", "home")))
    return kb


# =============================================================================
# AI provider setup
# =============================================================================
def ai_root(has_key: bool, is_ready: bool, provider_label: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn("🔁 Change provider", cb("ai", "providers")))
    kb.add(_btn("🧠 Change model", cb("ai", "models")))
    kb.add(_btn("🔑 Add / update API key", cb("ai", "key")))
    kb.add(_btn("🧪 Test connection", cb("ai", "test")))
    if has_key:
        kb.add(_btn("🗑 Remove API key", cb("ai", "disconnect")))
    kb.add(_btn("✖ Close", cb("ai", "close")))
    return kb


def ai_providers(active_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    from services import providers as _providers
    for provider in _providers.ordered():
        mark = "• " if provider.id == active_id else ""
        label = f"{mark}{provider.label}"
        if provider.free_tier:
            label += "  🆓"
        if provider.local:
            label += "  💻"
        kb.add(_btn(label, cb("ai", "provider", provider.id)))
    kb.add(_btn("« Back", cb("ai", "root")))
    return kb


def ai_models(models: list[str], current: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for model in models:
        mark = "• " if model == current else ""
        kb.add(_btn(f"{mark}{model}", cb("ai", "model", model)))
    kb.add(_btn("✏️ Type another model name", cb("ai", "model_custom")))
    kb.add(_btn("« Back", cb("ai", "root")))
    return kb


def ai_provider_actions(provider_id: str, key_required: bool) -> types.InlineKeyboardMarkup:
    from services import providers as _providers
    # Some endpoints need no key but still accept one (self-hosted OmniRoute with
    # REQUIRE_API_KEY=true); Ollama/LM Studio expose no key env var at all.
    optional_key = not key_required and bool(_providers.key_env_var(provider_id))
    kb = types.InlineKeyboardMarkup(row_width=1)
    if key_required:
        kb.add(_btn("🔑 Send API key now", cb("ai", "key")))
    elif optional_key:
        kb.add(_btn("🔑 Send API key (optional)", cb("ai", "key")))
    kb.add(_btn("🧠 Choose model", cb("ai", "models")))
    if provider_id == "custom":
        kb.add(_btn("🌐 Set base URL", cb("ai", "base_url")))
    kb.add(_btn("🧪 Test connection", cb("ai", "test")))
    kb.add(_btn("« Back", cb("ai", "providers")))
    return kb


# =============================================================================
# FAQ / canned answers
# =============================================================================
def faq_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(_btn("➕ Add a quick answer", cb("faq", "add")))
    kb.add(_btn("📃 List / delete", cb("faq", "list", 0)))
    kb.add(_btn("🔍 Search", cb("faq", "search")))
    kb.add(_btn("⬇️ Export (JSON)", cb("faq", "export")))
    kb.add(_btn("🗑 Clear all", cb("faq", "clear")))
    kb.add(_btn("✖ Close", cb("faq", "close")))
    return kb


def faq_list(entries: list, page: int, per_page: int = 5) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    for entry in entries[start:start + per_page]:
        title = (entry["keywords"] or "")[:28]
        state = "• " if entry["enabled"] else "✖ "
        kb.add(_btn(f"🗑 {state}{title}", cb("faq", "del", entry["id"], page)))
    nav = []
    if page > 0:
        nav.append(_btn("« Prev", cb("faq", "list", page - 1)))
    if start + per_page < len(entries):
        nav.append(_btn("Next »", cb("faq", "list", page + 1)))
    if nav:
        kb.row(*nav)
    kb.add(_btn("« Back", cb("faq", "menu")))
    return kb


# =============================================================================
# Owner tools
# =============================================================================
def chats_list(rows: list[dict]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        kb.add(_btn(row["label"], cb("tool", "chat", row["chat_id"])))
    kb.add(_btn("✖ Close", cb("tool", "close")))
    return kb


def chat_actions(chat_id: int, paused: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    if paused:
        kb.add(_btn("▶️ Resume auto-reply", cb("tool", "resume", chat_id)))
    else:
        kb.add(_btn("⏸ Pause auto-reply", cb("tool", "pause", chat_id)))
    kb.add(_btn("✖ Close", cb("tool", "close")))
    return kb


def setup_checklist(steps: dict) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, label in steps.items():
        kb.add(_btn(label, cb("tool", "setup_step", key)))
    kb.add(_btn("✖ Close", cb("tool", "close")))
    return kb


# =============================================================================
# Approvals
# =============================================================================
def approval_actions(approval_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn("✅ Send", cb("apr", "send", approval_id)),
        _btn("✏️ Edit", cb("apr", "edit", approval_id)),
    )
    kb.add(
        _btn("🚫 Reject", cb("apr", "reject", approval_id)),
        _btn("⏸ Pause Chat", cb("apr", "pause", approval_id)),
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
    kb.add(_btn("✖ Close", cb("set", "close")))
    return kb


def settings_enum(key: str, choices: list[str], current: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for choice in choices:
        mark = "• " if choice == current else ""
        kb.add(_btn(f"{mark}{choice}", cb("set", "enumval", key, choice)))
    kb.add(_btn("« Back", cb("set", "root")))
    return kb


# =============================================================================
# Knowledge base
# =============================================================================
def kb_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn("➕ Add text", cb("kb", "add")),
        _btn("📎 Upload file", cb("kb", "upload")),
    )
    kb.add(
        _btn("🔍 Search", cb("kb", "search")),
        _btn("📃 List items", cb("kb", "list", 0)),
    )
    kb.add(_btn("🗑 Clear all", cb("kb", "clear")))
    kb.add(_btn("✖ Close", cb("kb", "close")))
    return kb


def kb_list_keyboard(items: list, page: int, per_page: int = 5) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    page_items = items[start : start + per_page]
    for item in page_items:
        title = (item["title"] or "Untitled")[:30]
        kb.add(_btn(f"🗑 #{item['id']} {title} ({item['chunk_count']})",
                    cb("kb", "del", item["id"], page)))
    nav = []
    if page > 0:
        nav.append(_btn("« Prev", cb("kb", "list", page - 1)))
    if start + per_page < len(items):
        nav.append(_btn("Next »", cb("kb", "list", page + 1)))
    if nav:
        kb.row(*nav)
    kb.add(_btn("« Back", cb("kb", "menu")))
    return kb


# =============================================================================
# Confirmation
# =============================================================================
def confirm(token: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        _btn("✅ Yes", cb("confirm", "yes", token)),
        _btn("✖ No", cb("confirm", "no", token)),
    )
    return kb

"""English interface text. Keys must match ``i18n/ar.py`` exactly.

Chunk A: security notices, keyboards, owner commands, owner tools.
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    'gate.user.start': '👋 Send your message here to talk to the personal assistant.',
    'gate.user.start_paid': '⭐ Each message costs {stars} Stars. You have {free} free messages left. Send your text to receive an invoice; after the free allowance, replies require payment.',

    "gate.user.payment_unavailable": '⚠️ Paid messages are enabled but the price is not configured. Please try later.',
    'ai.key_source.shared': 'Shared owner key',
    'kbd.gate.sub_toggle': '🔒 Turn forced subscription on/off',
    'gate.user.unavailable': '⚠️ Messaging is temporarily blocked while the subscription gate is configured. Please try later.',
    'gate.user.text_required': '⭐ Payment is required. Send your message as text to receive a Stars invoice.',
    'gate.sub.bad': 'Send @username or a public https://t.me/channel link. For a private channel: -1001234567890 | Channel title | https://t.me/+invite',

    # =========================================================================
    # security.py — notices, claim flow, guards
    # =========================================================================
    "sec.non_owner_notice": (
        "👋 This is a <b>managed Telegram Business assistant</b>. It does not chat "
        "directly here.\n\n"
        "To reach the business, please message them through their Telegram Business "
        "profile. The owner connects this bot via <b>Telegram Settings → Business → "
        "Chatbots</b>."
    ),
    "sec.claim_notice": (
        "🔐 This assistant is not activated yet.\n\n"
        "If you are the owner, open the terminal where the bot is running and send: "
        "<code>/start &lt;claim-code&gt;</code> with the code printed there."
    ),
    "sec.claimed": (
        "✅ <b>You are now the owner of this assistant.</b>\n\n"
        "Next: /setup walks you through connecting it to your Telegram Business "
        "account, /ai picks the AI provider, /faq adds your answers, /mode chooses "
        "how replies are sent.\n\n"
        "Replying to the bot's own private chats needs no Telegram Business account "
        "at all — it works as soon as /mode is on. See /help → “Direct messages”."
    ),
    "sec.not_authorized": "Not authorized.",

    # =========================================================================
    # keyboards.py
    # =========================================================================
    "kbd.mode.auto": "🟢 Auto-reply",
    "kbd.mode.draft": "📝 Draft (approve)",
    "kbd.mode.off": "🔴 Off",
    "kbd.mode_row": "{label} — tap to change",
    "kbd.panel.status": "📊 Status",
    "kbd.panel.help": "❓ Help",
    "kbd.panel.ai": "🤖 AI provider",
    "kbd.panel.faq": "💬 Quick answers",
    "kbd.panel.kb": "📚 Knowledge Base",
    "kbd.panel.settings": "⚙️ Settings",
    "kbd.panel.pending": "📨 Pending approvals",
    "kbd.panel.mem_clear": "🧹 Clear memory",
    "kbd.panel.fonts": "🔤 Search Fonts (TTF/OTF)",
    "kbd.panel.setup": "🚀 Setup guide",
    "kbd.panel.health": "❤️ Health check",
    "kbd.back": "« Back",
    "kbd.close": "✖ Close",
    "kbd.prev": "« Prev",
    "kbd.next": "Next »",
    "kbd.confirm.yes": "✅ Yes",
    "kbd.confirm.no": "✖ No",

    # AI provider screens
    "kbd.ai.free_providers": "🆓 Free providers (no credit card)",
    "kbd.ai.change_provider": "🔁 Change provider",
    "kbd.ai.change_model": "🧠 Change model",
    "kbd.ai.load_models": "🔄 Load models from the provider",
    "kbd.ai.add_key": "🔑 Add / update API key",
    "kbd.ai.test": "🧪 Test connection",
    "kbd.ai.remove_key": "🗑 Remove API key",
    "kbd.ai.show_every": "🔁 Show every provider",
    "kbd.ai.only_free": "🆓 Only the free ones",
    "kbd.ai.switch": "🆓 Switch to {label}",
    "kbd.ai.switch_nokey": "🆓 Switch to {label} (no key)",
    "kbd.ai.resend_key": "🔑 Send the same key again",
    "kbd.ai.back_menu": "« Back to the AI menu",
    "kbd.ai.type_model": "✏️ Type another model name",
    "kbd.ai.send_key": "🔑 Send API key now",
    "kbd.ai.send_key_optional": "🔑 Send API key (optional)",
    "kbd.ai.choose_model": "🧠 Choose model",
    "kbd.ai.set_base_url": "🌐 Set base URL",
    "kbd.ai.free_instead": "🆓 Free providers instead",

    # Quick answers
    "kbd.faq.add": "➕ Add a quick answer",
    "kbd.faq.list": "📃 List / delete",
    "kbd.faq.search": "🔍 Search",
    "kbd.faq.export": "⬇️ Export (JSON)",
    "kbd.faq.clear": "🗑 Clear all",
    "kbd.faq.entry": "🗑 {state}{title}",

    # Knowledge base
    "kbd.kb.add": "➕ Add text",
    "kbd.kb.upload": "📎 Upload file",
    "kbd.kb.search": "🔍 Search",
    "kbd.kb.list": "📃 List items",
    "kbd.kb.clear": "🗑 Clear all",
    "kbd.kb.untitled": "Untitled",
    "kbd.kb.item": "🗑 #{id} {title} ({count})",

    # Chats / approvals
    "kbd.chat.pause": "⏸ Pause auto-reply",
    "kbd.chat.resume": "▶️ Resume auto-reply",
    "kbd.apr.send": "✅ Send",
    "kbd.apr.edit": "✏️ Edit",
    "kbd.apr.reject": "🚫 Reject",
    "kbd.apr.pause": "⏸ Pause Chat",

    # =========================================================================
    # owner_commands.py
    # =========================================================================
    "own.ai.ready": "ready ✅",
    "own.ai.not_ready": "not configured ⚠️ — open /ai",
    "own.ai.not_ready_short": "not configured ⚠️",
    "own.start": (
        "👋 <b>Alfiqi Ai — Telegram Business assistant</b>\n\n"
        "Mode: <b>{mode}</b> · AI: <b>{backend}</b> ({ai_state})\n\n"
        "Setup in three taps: /setup · /ai · /faq"
    ),
    "own.help": (
        "🤖 <b>Alfiqi Ai — Telegram assistant</b>\n\n"
        "The bot answers the private messages that reach it — either the customers of "
        "your Telegram Business account (linked in Telegram → Business → Chatbots) or "
        "anyone who writes to the bot's own chat. Customers never talk to it directly: "
        "they write, it replies.\n\n"
        "<b>First-time setup</b>\n"
        "1. @BotFather → /mybots → your bot → Bot Settings → <b>Business Mode</b> "
        "(some versions: Secretary Mode) → Turn on — only needed to answer your "
        "Telegram Business account's chats.\n"
        "2. Telegram → <b>Settings → Telegram Business → Chatbots</b> → paste the bot's "
        "@username → allow it <b>to reply to messages</b> → choose chats → save.\n"
        "3. Here: /ai to choose the AI, /faq to add answers, /mode to switch mode.\n"
        "Guided version of all this: /setup\n\n"
        "<b>Direct messages (no Business account needed)</b>\n"
        "Anyone messaging the bot in private gets an AI answer while the mode is on, "
        "and you are notified about every message. Switch it with /direct or in "
        "/settings → Replies. /takeover &lt;chat_id&gt; keeps you in charge of one chat.\n\n"
        "<b>Everyday commands</b>\n"
        "/mode — auto-reply · draft (approve first) · off\n"
        "/status — full status\n"
        "/health — run checks (token, AI, connection, storage)\n"
        "/chats — recent customer chats · /chat &lt;id&gt; — transcript\n"
        "/reply &lt;chat_id&gt; &lt;text&gt; — send a message yourself\n"
        "/takeover &lt;id&gt; · /handback &lt;id&gt; — stop / resume the AI for one chat\n"
        "/pause_chat &lt;id&gt; · /resume_chat &lt;id&gt; — the same for any paused chat\n"
        "/stats — customers, messages, AI replies\n"
        "/export — backup file (settings + quick answers)\n\n"
        "<b>AI setup</b>\n"
        "/ai — provider, API key, model, test · /aitest — quick test\n"
        "/freeai — providers that cost nothing (no credit card, no balance)\n"
        "/aimodel &lt;name&gt; — set a model · /instructions — standing instructions\n\n"
        "<b>Answers</b>\n"
        "/faq — quick answers menu (exact replies, sent instantly)\n"
        "/faq_add trigger1, trigger2 :: the exact reply\n"
        "/kb — knowledge base menu · /kb_add · /kb_upload · /kb_search · /kb_list\n\n"
        "<b>Teaching the bot (private messages)</b>\n"
        "/rules — your instructions in your own words; you approve the draft\n"
        "/unanswered — questions it could not answer; your reply is learned\n"
        "/resources — websites / platforms / Telegram groups it may use\n"
        "/gate — forced subscription to your channels, and paid messages "
        "(Telegram Stars, price set by you)\n\n"
        "<b>Panel & housekeeping</b>\n"
        "/start — control panel · /settings — all settings\n"
        "/language — switch the interface language (العربية / English)\n"
        "/approval_on · /approval_off · /auto_on · /auto_off\n"
        "/memory_clear — forget conversations · /reset — cancel approvals & pauses\n"
        "/cancel — abort a pending prompt\n\n"
        "<i>Owner takeover:</i> whenever you reply to a customer yourself (from the app "
        "or with /reply), the bot pauses that chat automatically for a while."
    ),
    "own.status.title": "📊 <b>Status</b>",
    "own.status.reply_mode": "Reply mode: <b>{mode}</b>",
    "own.status.switches": (
        "Auto-reply switch: <b>{auto}</b> · Approval: <b>{approval}</b>"
    ),
    "own.status.ai": "AI: <b>{state}</b>",
    "own.status.key_url": "   Get a key: {url}",
    "own.status.freeai_hint": (
        "   💡 /freeai — AI providers that need no credit card or balance."
    ),
    "own.status.direct": "Direct messages (bot chat): <b>{state}</b>",
    "own.status.direct_on": "answering ✅",
    "own.status.direct_off": "off — enable with /direct",
    "own.status.direct_hint": (
        "   Direct chats need no Telegram Business connection: anyone who writes to "
        "the bot gets an answer while the mode is on."
    ),
    "own.status.conn_none": (
        "Business connections: <b>none</b> — connect the bot in "
        "Telegram → Settings → Business → Chatbots."
    ),
    "own.status.conn_count": "Business connections: <b>{count}</b>",
    "own.status.conn_row": (
        "  • owner <code>{owner}</code> · {state} · {reply}"
    ),
    "own.status.conn_enabled": "enabled",
    "own.status.conn_disabled": "disabled",
    "own.status.conn_can_reply": "can reply",
    "own.status.conn_read_only": "read-only ⚠️",
    "own.status.paused": "Paused chats: <b>{count}</b>",
    "own.status.pending": "Pending approvals: <b>{count}</b>",
    "own.status.kb": "Knowledge base: <b>{items}</b> items / {chunks} chunks",
    "own.status.faq": "Quick answers: <b>{count}</b>",
    "own.status.health_hint": "<i>Run /health for a full check.</i>",

    "own.connections.none": (
        "No business connection yet.\n\n"
        "Telegram → Settings → Telegram Business → Chatbots → add this bot → "
        "allow it to reply. Full guide: /setup\n\n"
        "Not using Telegram Business? Direct messages to the bot are answered too — "
        "see /direct."
    ),
    "own.connections.title": "🔗 <b>Business connections</b>",
    "own.connections.row_id": "• ID <code>{id}</code>",
    "own.connections.row_owner": "  owner: <code>{owner}</code>",
    "own.connections.row_state": "  enabled: <b>{enabled}</b> · can reply: <b>{can_reply}</b>",
    "own.connections.row_updated": "  updated: {updated}",

    "own.key_removed": (
        "{provider} key removed. AI replies are off until you add a key again with /ai."
    ),
    "own.toggle": "{label}: <b>{state}</b>\nReply mode: <b>{mode}</b>",
    "own.label.auto": "Automatic replies",
    "own.label.approval": "Approval mode",

    "own.mem_clear_ask": "Clear <b>all</b> conversation memory?",
    "own.mem_clear_ask_plain": "Clear all conversation memory?",
    "own.pause.ask": "Send the customer chat ID to pause, or /cancel.",
    "own.resume.ask": "Send the customer chat ID to resume, or /cancel.",
    "own.pause.bad_id": "'{raw}' is not a valid chat ID.",
    "own.pause.no_connection": (
        "Couldn't determine the business connection for that chat "
        "(no messages seen yet, or multiple connections)."
    ),
    "own.pause.paused": "⏸ Paused chat <code>{chat_id}</code>.",
    "own.pause.resumed": "▶️ Resumed <code>{chat_id}</code>.",
    "own.pause.not_paused": "Chat was not paused",
    "own.reset_ask": (
        "Reset transient state? This cancels all <b>pending approvals</b>, clears "
        "<b>pauses</b>, and clears any pending input. Settings, KB and history are kept."
    ),
    "own.cancelled": "Cancelled. ✖",
    "own.instructions.title": (
        "📝 <b>Custom instructions</b> — always added to the AI's system prompt "
        "(applies to every reply, on every provider):\n\n"
        "{current}\n\n"
        "Set:   <code>/instructions &lt;text&gt;</code>\n"
        "Example: <code>/instructions Always reply in Egyptian Arabic, keep it short.</code>\n"
        "Clear: <code>/instructions clear</code>\n\n"
        "<i>Tip: language, tone and persona also have their own rows in /settings → "
        "Persona.</i>"
    ),
    "own.instructions.none": "<i>(none)</i>",
    "own.instructions.cleared": "Custom instructions cleared. ✖",
    "own.instructions.updated": (
        "✅ Custom instructions updated. They'll be applied to every reply from now on."
    ),

    "own.admin.usage": (
        "Usage: <code>/admin &lt;user_id&gt;</code> to add, "
        "<code>/admin remove &lt;user_id&gt;</code> to remove, or "
        "<code>/admin list</code>."
    ),
    "own.admin.list_title": "Delegated admins:",
    "own.admin.list_none": "(none)",
    "own.admin.bad_id": "Send a positive numeric Telegram user ID.",
    "own.admin.primary_kept": "The primary owner cannot be removed as a delegated admin.",
    "own.admin.not_changed": "Admin <code>{user_id}</code> was not {verb}.",
    "own.admin.changed": (
        "✅ Admin <code>{user_id}</code> {verb}. They must connect their own "
        "Telegram Business account before managing its assistant."
    ),
    "own.admin.added": "added",
    "own.admin.removed": "removed",
    "own.fallback": (
        "I didn't recognise that. Use /start for the control panel "
        "or /help for commands."
    ),

    # Control-panel callbacks & confirmations
    "own.panel.home": "👋 <b>Control panel</b>",
    "own.panel.choose_mode": "Choose the reply mode",
    "own.panel.mode_set": "Mode: {mode}",
    "own.panel.toggle": "{label} {state}",
    "own.confirm.cancelled": "Cancelled.",
    "own.confirm.done": "Done.",
    "own.confirm.done_ok": "Done ✅",
    "own.confirm.kb_cleared": "Knowledge base cleared.",
    "own.confirm.faq_cleared": "Quick answers cleared ({count} entries).",
    "own.confirm.key_removed": "{provider} key removed.",
    "own.confirm.mem_cleared": "Cleared conversation memory ({count} rows).",
    "own.confirm.reset": (
        "Reset done: {cancelled} approval(s) cancelled, {paused} pause(s) cleared."
    ),

    # =========================================================================
    # handlers/owner_tools.py
    # =========================================================================
    "tool.mode.auto": "🟢 <b>Auto-reply</b> — the bot answers customers immediately.",
    "tool.mode.draft": (
        "📝 <b>Draft mode</b> — the bot writes the reply and waits for your tap "
        "(Send / Edit / Reject). Nothing reaches the customer on its own."
    ),
    "tool.mode.off": (
        "🔴 <b>Off</b> — the bot stays silent; you get a notification per message."
    ),
    "tool.mode.set": "{text}\n\nMode: <b>{mode}</b>",
    "tool.mode.current": (
        "Current mode: {text}\n\n"
        "Choose a mode (or use <code>/mode auto|draft|off</code>):"
    ),
    "tool.chats.empty": (
        "No customer chats yet. Once someone messages your business account "
        "(with the bot connected in Telegram Business → Chatbots), they appear here."
    ),
    "tool.chats.title": (
        "🗂 <b>Recent customer chats</b>\nTap one to see the last messages."
    ),
    "tool.chats.label": "{name} · {count} msgs",
    "tool.transcript.title": "💬 <b>{name}</b> · chat <code>{chat_id}</code>",
    "tool.transcript.empty": (
        "\n<i>No stored messages (history starts when the bot is running).</i>"
    ),
    "tool.transcript.customer": "👤 customer",
    "tool.transcript.bot": "🤖 bot",
    "tool.transcript.pause_state": "Auto-reply for this chat: <b>{state}</b>",
    "tool.transcript.paused": "paused ⏸",
    "tool.transcript.active": "active ▶️",
    "tool.transcript.reply_hint": "Reply manually: <code>/reply {chat_id} your text</code>",
    "tool.chat.usage": "Usage: /chat <chat_id> …",
    "tool.chat.none": "I have no messages for that chat id yet.",
    "tool.reply.usage": (
        "Usage: <code>/reply &lt;chat_id&gt; the message</code>\n"
        "Send only the chat id and I'll ask you for the text.\n"
        "Tip: the chat id is shown in every notification and in /chats."
    ),
    "tool.reply.ask": (
        "✍️ Send the message you want me to deliver to chat <code>{chat_id}</code>.\n"
        "<i>(/cancel to abort)</i>"
    ),
    "tool.reply.unknown_chat": "Unknown chat id.",
    "tool.reply.cannot_reply": "The business connection cannot reply right now.",
    "tool.reply.failed": "Could not send ({error}). Check the chat.",
    "tool.reply.sent": (
        "✅ Sent.\nAuto-reply for this chat is paused for {minutes} min."
    ),
    "tool.reply.cancelled": "Reply cancelled — nothing sent.",
    "tool.pause.usage": "Usage: /{command} <chat_id>",
    "tool.pause.done": (
        "⏸ The bot will not answer chat <code>{chat_id}</code> until you /handback."
    ),
    "tool.pause.resumed": "▶️ The bot is answering that chat again.",
    "tool.pause.not_paused": "That chat was not paused.",

    "tool.stats.title": "📈 <b>Statistics</b>",
    "tool.stats.customers": "Customers: <b>{count}</b>",
    "tool.stats.messages": (
        "Messages received · 24h: <b>{day}</b> · 7d: <b>{week}</b> · total: <b>{total}</b>"
    ),
    "tool.stats.replies": (
        "AI replies · 24h: <b>{day}</b> · 7d: <b>{week}</b> · total: <b>{total}</b>"
    ),
    "tool.stats.summary": (
        "Mode: <b>{mode}</b> · Pending approvals: <b>{pending}</b>"
    ),
    "tool.stats.paused": "Paused chats: <b>{count}</b>",
    "tool.stats.kb": "Knowledge base: <b>{count}</b> items",
    "tool.stats.faq": "Quick answers: <b>{count}</b>",
    "tool.stats.connections": "Business connections: <b>{count}</b>",
    "tool.stats.direct": "Direct messages: <b>{state}</b>",

    "tool.health.title": "❤️ <b>Health check</b>",
    "tool.health.telegram_ok": "✅ Telegram API reachable — @{username}",
    "tool.health.telegram_error": "❌ Telegram API error: {error}",
    "tool.health.ai_ok": "✅ AI ready — {backend} · <code>{model}</code>",
    "tool.health.ai_missing": (
        "❌ AI not configured — open /ai to add a key or pick a provider."
    ),
    "tool.health.cost": "ℹ️ Cost: {cost}",
    "tool.health.embeddings": "ℹ️ Embeddings: {state}",
    "tool.health.embeddings_yes": "available",
    "tool.health.embeddings_no": "not available (keyword search)",
    "tool.health.freeai_hint": (
        "💡 Key rejected or no balance? /freeai lists providers that cost "
        "nothing (Google Gemini, Groq, Cerebras, Mistral…)."
    ),
    "tool.health.no_connection": (
        "❌ No business connection — connect the bot in Telegram → Settings → "
        "Business → Chatbots, or use direct messages (/direct)."
    ),
    "tool.health.direct_ready": "✅ Direct messages: enabled — the bot answers its own chats.",
    "tool.health.connection_row": (
        "{icon} Connection <code>{id}…</code> · enabled: {enabled} · can reply: {can_reply}"
    ),
    "tool.health.enable_reply": (
        "   ↳ Enable “Allow bot to reply to messages” for the bot in "
        "Telegram Business → Chatbots."
    ),
    "tool.health.disk": "✅ Disk free: {mb} MB",
    "tool.health.summary": (
        "ℹ️ Mode: <b>{mode}</b> · Pending approvals: <b>{pending}</b>"
    ),
    "tool.health.aitest_hint": "ℹ️ Test the AI end-to-end with /aitest.",
    "tool.export.caption": (
        "Backup: settings, quick answers, knowledge index "
        "(API keys are never exported)"
    ),
    "tool.callback.closed": "Closed.",
    "tool.callback.checking": "Checking…",
    "tool.callback.bad_chat": "Bad chat id.",
    "tool.callback.no_messages": "No messages for that chat yet.",
    "tool.callback.done": "Done",
    "tool.callback.paused": "⏸ Paused chat <code>{chat_id}</code>.",
    "tool.callback.resumed": "▶️ Resumed chat <code>{chat_id}</code>.",

    # =========================================================================
    # Shared pipeline notifications (business chats AND direct messages)
    # =========================================================================
    "biz.welcome_default": "👋 Hello! Thanks for messaging — how can I help you?",
    "biz.conn.enabled": (
        "🔗 <b>Business connection enabled.</b>\n"
        "Owner account ID: <code>{owner}</code>\n"
        "Bot can reply: <b>{can_reply}</b>\n\n"
        "The bot will now receive this account's customer messages. "
        "Use /status any time."
    ),
    "biz.conn.no_reply_permission": (
        "⚠️ This connection does <b>not</b> grant reply permission, so the "
        "bot can read but not send. Enable replies for the bot in your "
        "Telegram Business → Chatbots settings."
    ),
    "biz.conn.disabled": "🔌 <b>Business connection disabled or removed.</b>",
    "biz.notify.incoming": (
        "📥 <b>{name}</b> (chat <code>{chat_id}</code>):\n"
        "<i>{text}</i>\n\n"
        "<i>Auto-reply is OFF — reply yourself or turn it on with /mode.</i>"
    ),
    "biz.notify.auto_replied": (
        "🤖 Auto-replied to <b>{name}</b>:\n"
        "<i>“{text}”</i>\n"
        "➡️ {reply}"
    ),
    "biz.notify.rate_limit": (
        "🚦 <b>{name}</b> hit the message limit "
        "({used}/{limit} in the last hour). "
        "Auto-replies for this chat are paused for 1 hour."
    ),
    "biz.notify.ai_failed": (
        "⚠️ Could not generate a reply for <b>{name}</b> "
        "(chat <code>{chat_id}</code>): {error}"
    ),
    "biz.notify.ai_failed_tail": "No message was sent to the customer.",
    "biz.notify.delivery_partial": (
        "⚠️ An automatic reply to <b>{name}</b> was only "
        "partially delivered ({sent}/{total} parts). "
        "Check the customer chat before sending anything else."
    ),
    "biz.notify.delivery_unknown": (
        "⚠️ Delivery of an automatic reply to <b>{name}</b> "
        "could not be confirmed. No outbound history was recorded; check "
        "the customer chat before retrying."
    ),
    "biz.notify.cannot_reply": (
        "⚠️ Cannot auto-reply: the connection is disabled or lacks "
        "reply permission. Check Telegram Business → Chatbots."
    ),
    "biz.notify.nontext": (
        "📎 <b>{name}</b> sent a non-text <i>{type}</i> message "
        "(chat <code>{chat_id}</code>).{suffix}"
    ),
    "biz.notify.nontext_ack": " Sent the configured acknowledgement.",
    "biz.edited": (
        "✏️ <b>{name}</b> edited a message: "
        "<i>{text}</i>{cancellation}"
    ),
    "biz.edited_cancelled": "\nThe pending approval for the earlier version was cancelled.",
    "biz.deleted_pending": (
        "🗑 A customer deleted a message that had a pending approval; "
        "that approval was cancelled."
    ),

    # =========================================================================
    # main.py — startup notification, bot commands, bot description
    # =========================================================================
    "main.online": (
        "✅ <b>Alfiqi Ai {version} is online</b> as @{username}.\n"
        "Mode: <b>{mode}</b>\n"
        "AI: <b>{ai_state}</b> ({backend})\n"
        "Cost: {cost}"
    ),
    "main.online.setup_hint": (
        "\n\nFirst time? Run /setup for the checklist "
        "(BotFather Business Mode + Telegram Business → Chatbots)."
    ),
    "main.online.direct_hint": (
        "\n\n💬 Direct messages are {state}: anyone who writes to the bot in private "
        "gets an answer while the mode is on — no Telegram Business account needed. "
        "Switch it with /direct."
    ),
    "main.online.on": "ON",
    "main.online.off": "OFF",
    "main.online.freeai": (
        "\n\n💡 No API key yet, or your key has no credit? Send /freeai "
        "for the providers that cost nothing — Google Gemini, Groq and "
        "Cerebras need no credit card."
    ),
    "main.online.interrupted": (
        "\n\n⚠️ <b>Manual review required:</b> "
        "{count} approval delivery attempt(s) were interrupted. "
        "Check the customer chat before sending another reply."
    ),
    "main.description": (
        "Alfiqi Ai answers the private messages sent to this account with AI — "
        "Arabic by default."
    ),
    "main.description_short": "AI replies to your private messages 🤖",
    "main.cmd.start": "Control panel",
    "main.cmd.setup": "Guided setup checklist",
    "main.cmd.mode": "Auto-reply / draft / off",
    "main.cmd.ai": "AI provider, key, model",
    "main.cmd.freeai": "Free AI providers (no credit card)",
    "main.cmd.aitest": "Test the AI connection",
    "main.cmd.faq": "Quick answers (canned replies)",
    "main.cmd.kb": "Knowledge base menu",
    "main.cmd.status": "Bot, AI & connection status",
    "main.cmd.health": "Run system checks",
    "main.cmd.settings": "All settings",
    "main.cmd.chats": "Recent chats",
    "main.cmd.stats": "Statistics",
    "main.cmd.instructions": "Standing instructions (tone/language)",
    "main.cmd.help": "Usage guide",
    "main.cmd.direct": "Answer private messages to the bot",
    "main.cmd.language": "Interface language (العربية/English)",

    # =========================================================================
    # /direct and /language
    # =========================================================================
    "own.direct.on": (
        "🟢 <b>Direct messages:</b> enabled — the bot answers anyone who writes "
        "to its private chat with the AI, and you are notified about every message."
    ),
    "own.direct.off": (
        "🔴 <b>Direct messages:</b> off — people writing to the bot only get the "
        "“managed assistant” notice."
    ),
    "own.direct.now": "\n\nReply mode: <b>{mode}</b> — the bot actually answers only "
                      "while auto-reply or draft mode is on (/mode).",
    "own.direct.hint": (
        "\n\nTurn it {opposite} with <code>/direct {command}</code>."
    ),
    "own.direct.usage": "Usage: <code>/direct on|off</code> (currently: {state})",
    "own.direct.on_word": "on",
    "own.direct.off_word": "off",
    "own.language.title": (
        "🌐 <b>Interface language</b>\n\n"
        "Current: <b>{label}</b>\n"
        "This changes the bot's own menus, buttons and notifications — not the "
        "language of the replies sent to customers (that is /settings → Persona → "
        "Reply language)."
    ),

    # =========================================================================
    # handlers/settings.py
    # =========================================================================
    "set.group.reply": "🤖 Replies & behaviour",
    "set.group.messages": "💬 Welcome & payment messages",
    "set.group.persona": "🧑‍💼 Persona & language",
    "set.group.lang": "🌐 Bot language",
    "set.group.ai": "🧠 AI model",
    "set.group.ground": "📚 Answers (FAQ / knowledge base)",
    "set.group.limits": "🛡️ Safety & limits",
    "set.title": (
        "⚙️ <b>Settings</b>\n"
        "Reply mode: <b>{mode}</b> (change with /mode) · "
        "AI: <b>{backend}</b>\n"
        "Choose a section:"
    ),
    "set.title_plain": "⚙️ Settings",
    "set.section_hint": "{title}\nTap a row to change it.",
    "set.value.on": "ON",
    "set.value.off": "OFF",
    "set.provider_row": "🧠 Provider: {label}",
    "set.connection_row": "🧠 AI connection: {label}",
    "set.model_row": "🧠 Model: {model}",
    "set.free_ai_row": "🆓 Free AI providers (no card)",
    "set.primary_only": "Only the primary admin can change the AI provider/model.",
    "set.error": "Error.",
    "set.closed": "Closed.",
    "set.waiting": "Waiting for a value…",
    "set.enum_title": "Select <b>{label}</b>:",
    "set.saved_value": "{label} → {value}",
    "set.toggle_alert": "{label} {state}",
    "set.prompt_value": "Send the new value for <b>{label}</b>{range}.{hint}\n\n/cancel to abort.",
    "set.prompt_range": " (allowed {min}–{max})",
    "set.empty": "Empty value — nothing changed.",
    "set.text_saved": "✅ {label} updated:\n<b>{value}</b>",
    "set.text_reset": "✅ Restored the default {label}.",
    "set.not_number": "'{raw}' is not a valid number. {label} unchanged.",
    "set.out_of_range": "Value must be between {low} and {high}. {label} unchanged.",
    "set.number_saved": "✅ {label} set to <b>{value}</b>.",

    "set.opt.auto_reply_enabled": "Auto-reply",
    "set.opt.approval_mode_enabled": "Approval (draft) mode",
    "set.opt.sensitive_requires_approval": "Sensitive → approval",
    "set.opt.monitoring_mode": "Notify me about activity",
    "set.opt.memory_enabled": "Conversation memory",
    "set.opt.typing_indicator": "Typing indicator",
    "set.opt.reply_debounce_seconds": "Batch messages (seconds)",
    "set.opt.process_nontext_enabled": "Read media captions",
    "set.opt.nontext_ack_message": "Non-text auto-reply",
    "set.opt.nontext_ack_message.hint": (
        "Sent when a customer sends a photo/voice without text. "
        "Empty = never answer automatically."
    ),
    "set.opt.greet_new_customers": "Welcome new customers",
    "set.opt.welcome_text": "Welcome message",
    "set.opt.welcome_text.hint": (
        "Sent to a first-time customer when welcome-new-customers is on. "
        "Send clear to restore the default welcome."
    ),
    "set.opt.owner_takeover_pause_minutes": "Takeover pause (min)",
    "set.opt.max_messages_per_customer_per_hour": "Rate limit / hour",
    "set.opt.direct_reply_enabled": "Direct messages (bot chat)",
    "set.opt.direct_reply_enabled.hint": (
        "Answer the private messages people send to the bot itself "
        "(no Telegram Business account needed). The reply mode still applies."
    ),
    "set.opt.public_direct_bot_chat_enabled": "Direct-DM notice",
    "set.opt.assistant_name": "Assistant name",
    "set.opt.assistant_name.hint": "How the assistant refers to itself, e.g. “Sara”.",
    "set.opt.business_name": "Account holder name",
    "set.opt.business_description": "About the account holder",
    "set.opt.business_description.hint": "One or two sentences the AI uses as context.",
    "set.opt.tone": "Tone",
    "set.opt.reply_language": "Reply language",
    "set.opt.signature": "Signature",
    "set.opt.signature.hint": "Appended to every reply. Empty = no signature.",
    "set.opt.max_reply_chars": "Max reply length",
    "set.opt.disclose_ai": "May say it is an AI",
    "set.opt.custom_instructions": "Extra instructions",
    "set.opt.custom_instructions.hint": "Always added to the AI prompt (also via /instructions).",
    "set.opt.reply_priorities": "Reply priorities",
    "set.opt.reply_priorities.hint": (
        "Ordered priorities for replies, one per line "
        "(e.g. answer accurately, then be concise)."
    ),
    "set.opt.never_reply_rules": "When not to answer",
    "set.opt.never_reply_rules.hint": (
        "Topics or situations to avoid; the assistant will ask a human to follow up."
    ),
    "set.opt.ui_language": "Bot language",
    "set.opt.ui_language.hint": (
        "Language of the bot's own menus and notifications (Arabic by default)."
    ),
    "set.opt.temperature": "Temperature",
    "set.opt.max_tokens": "Max tokens",
    "set.opt.ai_base_url": "Custom base URL",
    "set.opt.faq_enabled": "Quick answers",
    "set.opt.faq_direct_reply": "Exact match sends as-is",
    "set.opt.faq_match_threshold": "FAQ match strictness (%)",
    "set.opt.faq_match_threshold.hint": (
        "Any exact trigger = 100%. Word-form hits (deliver ↔ delivery) count as "
        "50%, so they only reply verbatim if you lower this."
    ),
    "set.opt.kb_enabled": "Knowledge base",
    "set.opt.strict_kb_mode": "Strict KB mode",

    "set.tone.friendly": "Friendly",
    "set.tone.professional": "Professional",
    "set.tone.casual": "Casual",
    "set.tone.concise": "Very concise",
    "set.tone.warm": "Warm",
    "set.lang.auto": "Auto (match the customer)",
    "set.lang.ar": "العربية",
    "set.lang.en": "English",
    "set.lang.fr": "Français",
    "set.lang.es": "Español",
    "set.lang.de": "Deutsch",
    "set.lang.tr": "Türkçe",
    "set.lang.fa": "فارسی",
    "set.lang.ur": "اردو",
    "set.lang.ru": "Русский",
    "set.lang.id": "Bahasa Indonesia",
    "set.lang.hi": "हिन्दी",
    "set.lang.zh": "中文",

    # =========================================================================
    # handlers/setup_guide.py (/setup)
    # =========================================================================
    "setup.title": "🚀 <b>Setup</b>",
    "setup.tap_hint": "Tap a step below for the exact instructions.",
    "setup.connection.live": "Business connection: <b>live and allowed to reply</b> ✅",
    "setup.connection.readonly": (
        "Business connection found, but the bot is <b>not allowed to "
        "reply</b> — enable it in Telegram Business → Chatbots ⚠️"
    ),
    "setup.connection.none": (
        "No business connection yet — that is step 2️⃣ above. "
        "Not using Telegram Business? Skip it: /direct answers the private "
        "messages people send to the bot itself."
    ),
    "setup.direct": "Direct messages: <b>ON</b> — no Telegram Business account needed ✅",
    "setup.extra.current": "Current: {value}",
    "setup.extra.content": "Knowledge base items: {items} · Quick answers: {faq}",
    "setup.extra.connections": "Connections detected: {count}",
    "setup.step.secretary.label": "1️⃣ Business/Secretary mode in @BotFather",
    "setup.step.business.label": "2️⃣ Connect in Telegram Business → Chatbots",
    "setup.step.ai.label": "3️⃣ Choose the AI provider",
    "setup.step.content.label": "4️⃣ Add your answers (quick answers / knowledge base)",
    "setup.step.mode.label": "5️⃣ Choose the reply mode",
    "setup.step.test.label": "6️⃣ Send a test message",
    "setup.step.secretary.body": (
        "1️⃣ <b>Enable Business (Secretary) mode</b>\n\n"
        "Telegram only lets a bot answer on your behalf if it is switched to "
        "business mode:\n\n"
        "1. Open <b>@BotFather</b> in Telegram\n"
        "2. Send /mybots\n"
        "3. Pick this bot\n"
        "4. <b>Bot Settings</b> → <b>Business Mode</b> (some app versions call it "
        "<b>Secretary Mode</b>)\n"
        "5. Tap <b>Turn on</b>\n\n"
        "Then come back and check this list with /setup.\n"
        "<i>Only needed to answer your Telegram Business account's chats — direct "
        "messages to the bot work without it.</i>"
    ),
    "setup.step.business.body": (
        "2️⃣ <b>Connect the bot to your Telegram Business account</b>\n\n"
        "You need <b>Telegram Premium</b> on the account that will answer "
        "customers.\n\n"
        "1. Telegram → <b>Settings</b>\n"
        "2. Open <b>Telegram Business</b>\n"
        "3. Open <b>Chatbots</b>\n"
        "4. Paste this bot's @username\n"
        "5. Choose who it may answer: <b>All private chats except…</b> "
        "(recommended) or only selected chats\n"
        "6. Under <b>Bot permissions</b>, enable "
        "<b>“Allow bot to reply to messages”</b> — without it the bot can read but "
        "never answer\n"
        "7. Save\n\n"
        "The bot messages you here as soon as the connection is live, and /status "
        "shows whether it can reply."
    ),
    "setup.step.ai.body": (
        "3️⃣ <b>Choose the AI provider</b>\n\n"
        "Open /ai and pick one — no terminal needed. <b>No credit card?</b> Send "
        "/freeai for the full list; the short version:\n\n"
        "• <b>Google Gemini</b> 🆓 — the most generous free tier, a Google account "
        "is enough\n"
        "• <b>Groq</b> 🆓 / <b>Cerebras</b> 🆓 — very fast, free with an email\n"
        "• <b>OpenRouter</b> 🆓 — one key, many models (use a name ending in "
        "<code>:free</code>)\n"
        "• <b>Mistral</b>, <b>NVIDIA</b>, <b>SambaNova</b>, <b>Hugging Face</b> 🆓 — "
        "more free tiers\n"
        "• <b>Pollinations</b> 🆓 — no key at all (slow, best effort)\n"
        "• <b>Ollama / LM Studio</b> 💻 — free and private, runs on your own computer\n"
        "• <b>OpenAI</b>, <b>Anthropic</b>, <b>DeepSeek</b> 💳 — paid: the account "
        "needs credit, a ChatGPT/Claude subscription is not enough\n\n"
        "Then press “Test connection” — you should see the model answer. If it fails, "
        "the bot tells you exactly why (wrong key · no credit · wrong model name) and "
        "offers a free provider in one tap."
    ),
    "setup.step.content.body": (
        "4️⃣ <b>Teach the bot your answers</b>\n\n"
        "<b>Quick answers</b> (recommended first): exact replies for frequent "
        "questions — prices, delivery, working hours.\n"
        "Add one: <code>/faq_add سعر, كام, price :: our prices start at 500</code>\n"
        "Menu: /faq\n\n"
        "<b>Knowledge base</b>: longer material (policies, brochures) as "
        "<code>.txt</code>, <code>.md</code>, <code>.pdf</code> or "
        "<code>.docx</code> — upload with /kb_upload, menu with /kb.\n\n"
        "Rule of thumb: facts the bot must get exactly right → quick answers; "
        "background material → knowledge base."
    ),
    "setup.step.mode.body": (
        "5️⃣ <b>Choose how replies are sent</b>\n\n"
        "• 📝 <b>Draft mode</b> (safest): the bot writes the reply and waits — you "
        "tap Send / Edit / Reject.\n"
        "• 🟢 <b>Auto-reply</b>: the bot answers immediately, and you get a "
        "notification for every reply.\n"
        "• 🔴 <b>Off</b>: the bot only notifies you.\n\n"
        "Use /mode to switch any time. Start with Draft mode for a day or two, then "
        "switch to Auto-reply once you trust the answers."
    ),
    "setup.step.test.body": (
        "6️⃣ <b>Test it end to end</b>\n\n"
        "1. From <b>another</b> Telegram account (a friend's phone works), send a "
        "message to your business account — or simply message this bot in private.\n"
        "2. With Draft mode on, you get an approval card here — tap Send.\n"
        "3. With Auto-reply on, the answer goes out by itself.\n\n"
        "Nothing arriving? Check /health, and confirm that “Allow bot to reply to "
        "messages” is enabled in Telegram Business → Chatbots."
    ),

    # =========================================================================
    # handlers/approvals.py
    # =========================================================================
    "appr.sensitive_banner": "🚨 <b>SENSITIVE</b> — please review carefully\n\n",
    "appr.card": (
        "{banner}📨 <b>Approval #{id}</b>\n"
        "From: <b>{name}</b> (chat <code>{chat_id}</code>)\n\n"
        "<b>Customer:</b>\n<i>{customer}</i>\n\n"
        "<b>Proposed reply:</b>\n{reply}"
    ),
    "appr.something_wrong": "Something went wrong.",
    "appr.bad_action": "Bad action.",
    "appr.not_found": "Approval not found.",
    "appr.sending": "Delivery is already in progress.",
    "appr.uncertain": "Delivery outcome is uncertain. Check the customer chat before replying again.",
    "appr.already": "Already {status}.",
    "appr.unknown_action": "Unknown action.",
    "appr.conn_unavailable": "Connection unavailable / cannot reply.",
    "appr.send_failed": "Send failed; the approval is still pending. Please retry.",
    "appr.partial": "Part of the reply was delivered. Check the customer chat before sending more.",
    "appr.state_failed": "Delivered, but the approval state could not be finalized.",
    "appr.sent": "Sent ✅",
    "appr.already_handled": "Already handled.",
    "appr.rejected": "Rejected 🚫",
    "appr.paused": "Chat paused ⏸ (use /resume_chat to resume).",
    "appr.edit_prompt_cb": "Send me the edited reply text.",
    "appr.edit_prompt": (
        "✏️ <b>Editing reply for approval #{id}</b> "
        "(chat <code>{chat_id}</code>).\n"
        "Send the new reply text as your next message, or /cancel to abort."
    ),
    "appr.edit.not_pending": "That approval is no longer pending.",
    "appr.edit.empty": "Empty edit ignored. The approval is still pending.",
    "appr.edit.conn": "Connection unavailable; the edited reply was not sent.",
    "appr.edit.handled": "That approval was already handled.",
    "appr.edit.failed": (
        "The edited reply could not be delivered. The approval is still pending; please retry."
    ),
    "appr.edit.partial": (
        "Part of the edited reply was delivered. Check the customer chat before sending more."
    ),
    "appr.edit.state_failed": (
        "The edited reply was delivered, but its approval state could not be finalized."
    ),
    "appr.edit.sent": "Edited reply sent ✅",
    "appr.pending.none": "No pending approvals. 🎉",
    "appr.pending.title": "<b>Pending approvals ({count}):</b>",
    "appr.pending.row": "• #{id} chat <code>{chat_id}</code>: <i>{preview}</i>",
    "appr.pending.hint": "\nEach approval was sent as its own message with action buttons.",

    # =========================================================================
    # handlers/faq.py — quick answers
    # =========================================================================
    "faq.menu.title": "💬 <b>Quick answers</b>",
    "faq.menu.entries": "Entries: <b>{total}</b> ({active} active)",
    "faq.menu.direct": "Exact match → send as-is: <b>{state}</b>",
    "faq.menu.fuzzy": "Fuzzy match → give to the AI: <b>{state}</b>",
    "faq.menu.example": (
        "Example: triggers <code>سعر, كام, price</code> → answer "
        "«الأسعار تبدأ من 500 جنيه» is sent instantly whenever a customer asks "
        "about price."
    ),
    "faq.menu.add": "Add: <code>/faq_add trigger1, trigger2 {sep} the answer</code>",
    "faq.add.step1": (
        "➕ <b>New quick answer — step 1/2</b>\n\n"
        "Send the trigger words, separated by commas.\n"
        "Example: <code>سعر, كام, price, how much</code>\n\n"
        "A customer message containing any of them can trigger the answer. "
        "/cancel to abort."
    ),
    "faq.delete.usage": "Usage: /faq_del <id>",
    "faq.delete.done": "Deleted quick answer #{id}.",
    "faq.delete.missing": "No entry #{id}.",
    "faq.search.ask": "Send a customer-like message to test, or /cancel.",
    "faq.search.none": (
        "No quick answer matches “{query}”.\n"
        "A message like this would be answered by the AI instead."
    ),
    "faq.search.title": "🔍 Matches for “{query}”:",
    "faq.search.mode_instant": "instant reply ✅",
    "faq.search.mode_exact": "context for the AI (all triggers hit)",
    "faq.search.mode_fuzzy": "context for the AI ({score} confidence)",
    "faq.list.title": "💬 <b>Quick answers</b> ({count}) — tap 🗑 to delete:",
    "faq.list.empty": "No quick answers yet. Add one with /faq_add.",
    "faq.list.none": "No entries yet.",
    "faq.list.next_page": "<i>Next page →</i>",
    "faq.clear.ask": "Delete <b>all</b> quick answers?",
    "faq.import.ask": (
        "📥 Send the JSON file exported earlier (or /cancel).\n"
        "<i>This replaces all current quick answers.</i>"
    ),
    "faq.import.not_json": "That is not a JSON file — nothing imported.",
    "faq.import.unreadable": "Could not read that file as JSON.",
    "faq.import.bad_structure": "Unexpected JSON structure.",
    "faq.import.done": "✅ Imported {count} quick answers (previous ones replaced).",
    "faq.create.short_trigger": (
        "That trigger is too short — use at least 2 characters per trigger."
    ),
    "faq.create.empty_answer": "The answer cannot be empty.",
    "faq.create.saved": (
        "✅ Quick answer #{id} saved.\n\n"
        "Triggers: <code>{triggers}</code>\n"
        "Answer: {answer}\n\n"
        "<i>Exactly matching messages get this answer instantly; close matches are "
        "handed to the AI as approved context.</i>"
    ),
    "faq.cb.send_triggers": "Send the trigger words.",
    "faq.cb.step1": "➕ <b>Step 1/2</b> — send the trigger words (comma separated), or /cancel.",
    "faq.cb.deleted": "Deleted ✅",
    "faq.cb.not_found": "Entry not found.",
    "faq.cb.send_test": "Send a test message.",
    "faq.cb.preparing": "Preparing the file…",
    "faq.export.empty": "There is nothing to export yet.",
    "faq.export.caption": "Quick answers export ({count} entries)",
    "faq.pending.short_triggers": (
        "Those triggers are too short — nothing saved. Try /faq_add again."
    ),
    "faq.pending.step2": (
        "➕ <b>Step 2/2</b> — now send the exact reply for:\n"
        "<code>{triggers}</code>\n\n(/cancel to abort)"
    ),
    "faq.pending.empty_answer": "Empty answer — nothing saved.",

    # =========================================================================
    # handlers/knowledge_base.py
    # =========================================================================
    "kb.menu.title": (
        "📚 <b>Knowledge Base</b>\n"
        "Items: <b>{items}</b> · Chunks: <b>{chunks}</b>\n"
        "KB usage: <b>{usage}</b> · "
        "Strict mode: <b>{strict}</b>"
    ),
    "kb.add.ask": "Send the text to add to the knowledge base, or /cancel.",
    "kb.upload.ask": (
        "Send a document to add to the knowledge base "
        "(.txt, .md, .pdf, or .docx), or /cancel."
    ),
    "kb.upload.ask_docs": "Send a .txt/.md/.pdf/.docx document, or /cancel.",
    "kb.upload.need_document": "Please send a <b>document</b> (.txt/.md/.pdf/.docx).",
    "kb.upload.download_failed": "Could not download the file from Telegram. Try again.",
    "kb.upload.done": (
        "✅ Added <b>{name}</b> as item #{id} — {count} chunk(s){note}."
    ),
    "kb.add.done": "✅ Added KB item #{id} — {count} chunk(s){note}.",
    "kb.add.note_no_embeddings": " (stored for keyword search; embeddings unavailable)",
    "kb.search.ask": "Send a search query, or /cancel.",
    "kb.search.none": "No relevant knowledge-base entries found.",
    "kb.search.title": "🔍 Top {count} result(s) for <i>{query}</i>:",
    "kb.list.title": "📃 <b>KB items</b> (tap to delete):",
    "kb.list.empty": "Knowledge base is empty. Use /kb_add or /kb_upload.",
    "kb.delete.usage": "Usage: /kb_delete <item_id>",
    "kb.delete.done": "Deleted item #{id}.",
    "kb.delete.missing": "No item #{id}.",
    "kb.clear.empty": "Knowledge base is already empty.",
    "kb.clear.ask": "Delete <b>all {items}</b> KB items and {chunks} chunks?",
    "kb.clear.ask_plain": "Delete the entire knowledge base?",
    "kb.cb.send_text": "Send text…",
    "kb.cb.send_file": "Send a file…",
    "kb.cb.send_query": "Send a query…",
    "kb.cb.deleted": "Deleted #{id}",
    "kb.cb.now_empty": "Knowledge base is now empty.",
    "kb.pending.empty": "Nothing to add (empty message).",
    "kb.pending.empty_query": "Empty query.",

    # =========================================================================
    # handlers/ai_setup.py — provider / key / model screens
    # =========================================================================
    "ai.title": "🤖 <b>AI provider</b>",
    "ai.status": "Status: <b>{state}</b>",
    "ai.send_key_hint": "Send your API key with the button below.",
    "ai.send_key_hint_or_pick": (
        "Send the API key with the button below, or choose another provider."
    ),
    "ai.primary_only_note": "\nOnly the primary admin can change the AI provider/model.",
    "ai.legend": (
        "Providers with 🆓 offer a usable free tier; 💻 runs on your own computer."
    ),
    "ai.delegate_note": (
        "The primary admin chooses the provider/model. The owner key is shared for replies; personal data stays separate."
    ),
    "ai.freeai_hint": (
        "💡 No credit card / no balance? Send /freeai for the providers "
        "that cost nothing."
    ),
    "ai.get_key": "🔑 Get a key: {url}",
    "ai.key_source.env": "from .env (terminal)",
    "ai.key_source.telegram": "saved in Telegram",
    "ai.current_key": "Current key: {masked} ({origin})",
    "ai.not_set": "(not set)",
    "ai.base_url": "Base URL: <code>{base}</code>",
    "ai.custom_hint": "Send the base URL, the model name and (optionally) an API key.",
    "ai.endpoint": "Endpoint: <code>{base}</code>",
    "ai.local_note": "<i>Must be reachable from the machine running the bot.</i>",
    "ai.model_line": "Model: <code>{model}</code>",
    "ai.cost_line": "Cost: {cost}",
    "ai.needs_credit": "💡 This provider needs paid credit. /freeai lists the free ones.",
    "ai.providers.free_title": (
        "🆓 <b>Free AI providers</b>\n\n"
        "No credit card and no balance needed. Tap one and the bot switches to "
        "it, then asks for its key (a couple of these need no key at all)."
    ),
    "ai.providers.title": (
        "🔁 <b>Choose an AI provider</b>\n\n"
        "Your customers' messages are answered by this model. "
        "You can switch any time — nothing else in the bot changes."
    ),
    "ai.free.title": "🆓 <b>AI providers that cost nothing</b>",
    "ai.free.intro": (
        "No credit card, no balance top-up. Pick one, get a key, tap it here:"
    ),
    "ai.free.active": "  ← active now",
    "ai.free.no_key_needed": "    🔑 No API key needed",
    "ai.free.which": (
        "<b>Which one?</b>\n"
        "• Easiest + most generous: <b>Google Gemini</b> (a Google account is enough).\n"
        "• Fastest: <b>Groq</b> or <b>Cerebras</b>.\n"
        "• Many models with one key: <b>OpenRouter</b> (use a model ending in "
        "<code>:free</code>).\n"
        "• No signup at all: <b>Pollinations</b> — but it is slow and best effort.\n"
        "• No internet / total privacy: <b>Ollama</b> or <b>LM Studio</b> on your PC.\n\n"
        "Free tiers are rate limited (per minute / per day) and reset on their own. "
        "After switching, press 🧪 Test connection — and if a model name is refused, "
        "use 🔄 Load models to see what your key can run."
    ),
    "ai.unknown_provider": "Unknown provider.",
    "ai.provider_set": "Provider: {label}",
    "ai.models.title": (
        "🧠 <b>Model for {label}</b>\n\n"
        "Current: <code>{current}</code>\n"
        "Pick one, or type any model name your account supports."
    ),
    "ai.primary_only_cb": "Only the primary admin can change the AI provider or model.",
    "ai.model_set_cb": "Model: {model}",
    "ai.testing": "Testing…",
    "ai.remove_key_ask": (
        "Remove the stored API key for <b>{label}</b>?\n"
        "The bot will stop generating replies until a key is added again."
    ),
    "ai.ask_key_cb": "Send the key as your next message.",
    "ai.key_url_hint": "\n\n🔑 Get one here: {url}",
    "ai.key_url_free": "  (free — no credit card)",
    "ai.ask_key": (
        "🔑 Send the <b>{label}</b> API key as your next message "
        "(or /cancel).\n\n<i>I delete the message right after reading it.</i>{hint}"
    ),
    "ai.switched": "Switched to {label}",
    "ai.no_key_needed_test": "✅ <b>{label}</b> needs no API key. Testing it now…",
    "ai.ask_model_cb": "Type the model name.",
    "ai.ask_model": (
        "🧠 Send the model name for <b>{label}</b> "
        "(e.g. <code>gpt-4.1-mini</code>, <code>gemini-2.5-flash</code>), or /cancel."
    ),
    "ai.ask_base_url_cb": "Send the base URL.",
    "ai.ask_base_url": (
        "🌐 Send the base URL of your OpenAI-compatible endpoint "
        "(e.g. <code>http://localhost:1234/v1</code>), or /cancel."
    ),
    "ai.aimodel.usage": (
        "Current model: <code>{model}</code>\n"
        "Usage: <code>/aimodel &lt;model-name&gt;</code>"
    ),
    "ai.aimodel.set": "✅ Model set to <code>{model}</code>. Use /aitest to verify it.",
    "ai.pending.nothing": "Nothing received — cancelled. ✖",
    "ai.pending.model_set": (
        "✅ Model set to <code>{model}</code>.\nUse /aitest to verify."
    ),
    "ai.pending.base_url_set": (
        "✅ Base URL saved: <code>{url}</code>.\n"
        "Send the model name next with /aimodel, then /aitest."
    ),
    "ai.checking_key": "🔎 Checking the key with {label}…",
    "ai.key_rejected": "⚠️ <b>{label}</b> did not accept this key",
    "ai.connected": (
        "✅ <b>{label}</b> connected.\n{message}\n\nModel: <code>{model}</code>"
    ),
    "ai.how_to_fix": "<b>How to fix it</b>",
    "ai.switch_hint": "Or switch to a free provider in one tap 👇 ({names})",
    "ai.loading_models": "Loading models…",
    "ai.asking_models": "🔄 Asking <b>{label}</b> which models your key can use…",
    "ai.still_type_model": "You can still type a model name: /aimodel &lt;name&gt;",
    "ai.no_model_list": (
        "{label} did not return a model list. Type the name instead: "
        "/aimodel &lt;name&gt;"
    ),
    "ai.models_found": (
        "🧠 <b>{count} models</b> your key can run on {label}\n"
        "Current: <code>{current}</code>\nTap one to use it:"
    ),
    "ai.choose_model": "🧠 Choose a model for {label} (current: <code>{current}</code>):",
    "ai.testing_msg": "🧪 Testing the connection (may take a few seconds)…",
    "ai.test_failed": "⚠️ <b>The test failed</b>",


    # =========================================================================
    # services/ai_service.py — key diagnostics, hints, status
    # =========================================================================
    "util.or_join": " or ",
    "ai.hint.openai": "OpenAI needs credit on the API account — a ChatGPT Plus "
                      "subscription is not API credit (platform.openai.com → Billing).",
    "ai.hint.anthropic": "Anthropic needs credit on console.anthropic.com — a Claude "
                         "subscription is not API credit.",
    "ai.hint.google": "Use a key from aistudio.google.com/app/apikey (Gemini API), not a "
                      "Google Cloud OAuth token.",
    "ai.hint.groq": "Groq keys come from console.groq.com/keys — a free account, no card.",
    "ai.hint.cerebras": "Cerebras keys come from cloud.cerebras.ai → API Keys.",
    "ai.hint.openrouter": "OpenRouter: models ending in ':free' need no credit; any other "
                          "model needs a paid balance.",
    "ai.hint.mistral": "Mistral's free plan needs phone verification before the key works.",
    "ai.hint.nvidia": "NVIDIA: copy the model name exactly as build.nvidia.com shows it "
                      "(e.g. meta/llama-3.1-8b-instruct).",
    "ai.hint.huggingface": "Hugging Face: use a token with 'Read' scope, and open the model "
                           "page once to accept its licence if it is gated.",
    "ai.hint.deepseek": "DeepSeek keys only work after the balance is topped up "
                        "(platform.deepseek.com → Top up).",
    "ai.hint.together": "Together needs a minimum top-up before the key works.",
    "ai.hint.pollinations": "Pollinations needs no key at all — a 402/429 here means the "
                            "free per-IP slot is busy: wait ~30 seconds and retry.",
    "ai.hint.free": "Free providers that need no card: Google Gemini, Groq, Cerebras, "
                    "Mistral — open /ai → 🆓 Free providers (or send /freeai).",
    "ai.classify.generic_label": "The provider",
    "ai.classify.model": (
        "{label} rejected the model name{tail} Your key may not have access to "
        "it, or the name is spelled differently on this provider."
    ),
    "ai.classify.pollinations_busy": (
        "{label} is throttling this address{tail} The free endpoint allows "
        "roughly one request per 30 seconds: wait a moment and test again."
    ),
    "ai.classify.no_credit": (
        "{label}: the key was understood, but the account has no credit left "
        "or its paid quota is used up{tail}"
    ),
    "ai.classify.rate_limit": (
        "{label} hit a rate/quota limit{tail} Free tiers cap requests per "
        "minute or per day — this resets on its own, nothing is broken."
    ),
    "ai.classify.region": (
        "{label} refused the request because of your country/region{tail} "
        "Another provider will work."
    ),
    "ai.classify.verify_suffix": " Finish the account verification first.",
    "ai.classify.auth": "{label} rejected this API key (HTTP {status}){tail}{extra}",
    "ai.classify.not_found": (
        "{label} returned 404 — the base URL or the endpoint path is wrong "
        "(most providers expect the base URL to end in /v1){tail}"
    ),
    "ai.classify.too_many": (
        "{label} is rate limiting the bot right now{tail} Free tiers cap "
        "requests per minute/day; this resets on its own."
    ),
    "ai.classify.server": "{label} is having problems (HTTP {status}). Retry in a moment.{tail}",
    "ai.classify.other": "{label} rejected the request (HTTP {status}).{tail}",
    "ai.hint_rule.no_credit.1": "This is a billing/quota problem, not a broken key — "
                                "re-sending the same key will not help.",
    "ai.hint_rule.no_credit.2": "Either add credit at the provider's billing page, or switch "
                                "to a provider with a real free tier.",
    "ai.hint_rule.auth.1": "Check the key was copied from THIS provider — a "
                           "Groq/OpenRouter/Gemini key never works on another one.",
    "ai.hint_rule.auth.2": "Paste it again with no spaces or line breaks, and make sure it "
                           "was not revoked or expired.",
    "ai.hint_rule.auth.new_key": "Create a fresh key: {url}",
    "ai.hint_rule.model.1": "Open /ai → 🧠 Change model → 🔄 Load models from the provider "
                            "to see the exact names this key can run.",
    "ai.hint_rule.model.2": "Free tiers often allow only some models — pick a smaller/older one.",
    "ai.hint_rule.rate_limit.1": "Wait a minute and run /aitest again; free quotas reset per "
                                 "minute or per day.",
    "ai.hint_rule.rate_limit.2": "For a bigger free daily quota use Google Gemini, Groq or "
                                 "Cerebras.",
    "ai.hint_rule.bad_request": "Check the base URL ends in /v1 and that the model name "
                                "matches the provider's docs.",
    "ai.hint_rule.connection": "The server could not be reached — check this machine's "
                               "internet access, DNS and any firewall/proxy.",
    "ai.hint_rule.timeout": "The provider took too long. Retry, or pick a faster provider "
                            "(Groq and Cerebras answer in well under a second).",
    "ai.hint_rule.no_key.1": "Open /ai → 🔑 Add / update API key.",
    "ai.err.timeout": "{what} timed out. Try again.",
    "ai.err.network": "Could not reach the provider ({error}). Check the network.",
    "ai.err.no_base_url": "No base URL configured for this endpoint.",
    "ai.err.no_base_url_list": "No base URL set for this endpoint.",
    "ai.err.no_base_url_probe": "No base URL set for this endpoint.",
    "ai.err.no_key": "No API key configured for this provider. Add one with /ai.",
    "ai.err.no_anthropic_key": "No Anthropic API key configured. Add one with /ai.",
    "ai.err.empty_reply": "The model returned an empty reply.",
    "ai.err.no_embeddings_full": "Embeddings are not available for the active provider "
                                 "(knowledge base will use keyword search).",
    "ai.err.no_embeddings_url": "No base URL for embeddings.",
    "ai.err.embeddings_payload": "The embeddings endpoint returned an unexpected payload.",
    "ai.err.unknown_provider": "Unknown provider: {provider}",
    "ai.err.codex_missing": "The Codex CLI is not installed on this machine.",
    "ai.err.model_list_timeout": "{label}: fetching the model list timed out.",
    "ai.err.model_list_unreachable": "Could not reach {label} ({error}).",
    "ai.err.model_list_not_json": "{label} returned a non-JSON model list.",
    "ai.err.non_json": "{what}: the provider returned a non-JSON response.",
    "ai.err.what_failed": "{what} failed.",
    "ai.shape.bot_token": (
        "That is your Telegram bot token (from @BotFather), not an AI API key. "
        "The bot token is already in use — what {label} needs is its own "
        "API key, from that provider's own website."
    ),
    "ai.shape.other_provider": (
        "This looks like a key for {names}, but you are adding it to "
        "{label}. Each provider only accepts its own keys."
    ),
    "ai.check.no_key": "No API key for {label} yet.",
    "ai.check.no_key_hint": "Send the key: /ai → 🔑 Add / update API key.",
    "ai.check.get_one_at": " Get one at {url}.",
    "ai.check.shape_hint": "You are adding a key for {label}; get it from {source}",
    "ai.check.that_console": "that provider's console.",
    "ai.check.belongs_to": "That key belongs to {label}: {url}",
    "ai.check.ok": "Connection OK — {label} answered with “{sample}” using {model} ({seconds}s).",
    "ai.status.provider": "Provider: {label}",
    "ai.status.model": "Model: {model}",
    "ai.status.codex": "Codex CLI: {cli} · login: {login}",
    "ai.status.found": "found",
    "ai.status.not_found": "NOT found",
    "ai.status.yes": "yes",
    "ai.status.no_unknown": "no/unknown",
    "ai.status.from_env": " (from .env)",
    "ai.status.in_telegram": " (saved in Telegram)",
    "ai.status.api_key": "API key: {masked}{origin}",
    "ai.status.api_key_optional": "API key: {masked} (optional here)",
    "ai.status.base_url": "Base URL: {url}",
    "ai.status.endpoint": "Endpoint: {url}",
    "ai.status.embeddings": "Embeddings: {state}",
    "ai.status.keyword_only": "no (keyword search only)",
    "ai.status.cost": "Cost: {cost}",
    "ai.cost.local": "free — runs on your own machine 💻",
    "ai.cost.no_key": "free — no API key needed 🆓",
    "ai.cost.free_tier": "free tier available 🆓",
    "ai.cost.beyond": " (paid credit needed beyond it)",
    "ai.cost.paid": "paid — the account needs credit 💳",
    "ai.cost.endpoint": "depends on your endpoint",
    "ai.model_label.codex_cli": "ChatGPT via Codex CLI",
    "ai.model_label.codex_default": "Codex default",
    "ai.what.chat": "{label} chat",
    "ai.what.embeddings": "{label} embeddings",
    "ai.what.anthropic_test": "Anthropic test",
    "ai.what.test": "{label} test",

    # ==== append-below ==='''
    # =========================================================================
    # services/providers.py — registry texts (en)
    # =========================================================================
    'prov.google.label': 'Google Gemini',
    'prov.google.docs': 'Free API key from Google AI Studio: sign in with a Google account, press “Create API key”, done. Free tier is rate limited per day (resets at midnight Pacific time) and the newest Pro models need billing — Flash models are the free ones. Also does KB embeddings.',
    'prov.google.free_note': 'Best free tier: hundreds of free requests/day with any Google account — no card, no phone number.',
    'prov.groq.label': 'Groq (fastest)',
    'prov.groq.docs': 'Free API key from console.groq.com — sign up with an email (no credit card), open “API Keys”, create one. Very fast. Knowledge base uses keyword search (Groq has no embeddings API). Groq rotates its free catalogue often; if a model name is rejected, use “Load models”.',
    'prov.groq.free_note': 'Free forever with an email only: ~1,000 requests/day on the chat models, ~30 requests/minute. Replies in milliseconds. (Llama 3.3 70B was retired from the free tier on 2026-08-16; GPT-OSS / Qwen are the replacements.)',
    'prov.cerebras.label': 'Cerebras (fast, big daily quota)',
    'prov.cerebras.docs': 'Free key from cloud.cerebras.ai → API Keys (email or GitHub, no card). The free catalogue changes often, so after connecting press “Load models” and pick one your key can actually run. Free tier context is limited (~8K tokens).',
    'prov.cerebras.free_note': 'About 1M free tokens/day and thousands of free requests/day — email or GitHub signup, no credit card.',
    'prov.openrouter.label': 'OpenRouter (hundreds of models)',
    'prov.openrouter.docs': 'Free key from openrouter.ai/keys. Pick a model that ends in “:free” to stay at zero cost — press “Load models” and the free ones are listed first. Paid models need credit, so a “no credit” error here means you picked a non-:free model.',
    'prov.openrouter.free_note': 'One free key for hundreds of models. Models whose name ends in “:free” cost nothing (~50 free requests/day).',
    'prov.mistral.label': 'Mistral AI',
    'prov.mistral.docs': 'Free API key from console.mistral.ai (no credit card; the free plan asks for phone verification and may use your prompts to improve their models unless you opt out). Good multilingual quality, ~1 request per second.',
    'prov.mistral.free_note': 'Free “Experiment” plan: roughly 1 request/second and a large monthly token allowance. No card, but phone verification.',
    'prov.nvidia.label': 'NVIDIA NIM (free signup credits)',
    'prov.nvidia.docs': "Free key from build.nvidia.com (NVIDIA account, no credit card). Copy the model name exactly as shown on the model's page — NVIDIA names include the vendor, e.g. meta/llama-3.1-8b-instruct.",
    'prov.nvidia.free_note': 'Free API credits with an NVIDIA account (no card). Credits run out instead of refreshing daily.',
    'prov.sambanova.label': 'SambaNova',
    'prov.sambanova.docs': 'Free key from community.sambanova.ai (developer portal, no card). Fast open-weight models; use “Load models” for the exact names your key can run.',
    'prov.sambanova.free_note': 'Free developer key with generous rate limits on open models — email signup, no card.',
    'prov.huggingface.label': 'Hugging Face (small allowance)',
    'prov.huggingface.docs': 'Free token from huggingface.co/settings/tokens (“Read” permission is enough). Model names are the repo ids, e.g. meta-llama/Llama-3.3-70B-Instruct. Some models are gated: open their page once and accept the licence. Small free monthly allowance.',
    'prov.huggingface.free_note': 'Free with an HF access token (read scope) — a small monthly allowance, enough for testing and light traffic.',
    'prov.pollinations.label': 'Pollinations (no key needed)',
    'prov.pollinations.docs': '⚠️ Community-run, best-effort endpoint: no signup and no key, but about one request per 30 seconds per IP and no uptime promise, so it suits testing rather than a busy shop. Customer messages go to a third party — switch to Google/Groq/Cerebras for real traffic.',
    'prov.pollinations.free_note': 'Zero signup and zero keys: works the moment you pick it. Best effort — roughly one request per 30 seconds per IP.',
    'prov.openai.label': 'OpenAI (ChatGPT API)',
    'prov.openai.docs': 'Pay-as-you-go API key from platform.openai.com — it needs credit on the account (a ChatGPT Plus subscription is NOT API credit). Best quality plus KB embeddings. No card / no credit yet? Use a 🆓 provider.',
    'prov.anthropic.label': 'Anthropic (Claude)',
    'prov.anthropic.docs': 'API key from console.anthropic.com (needs credit on the account; a Claude subscription is not API credit). Knowledge base uses keyword search (Anthropic has no embeddings API).',
    'prov.deepseek.label': 'DeepSeek (very cheap)',
    'prov.deepseek.docs': 'Very cheap API key from platform.deepseek.com — the balance must be topped up before the key works (a few dollars last a long time).',
    'prov.xai.label': 'xAI (Grok)',
    'prov.xai.docs': 'API key from console.x.ai. New accounts sometimes get a small trial credit; after that it is pay-as-you-go.',
    'prov.together.label': 'Together AI',
    'prov.together.docs': 'API key from api.together.xyz — needs a minimum top-up, so use a 🆓 provider if you do not want to pay yet.',
    'prov.custom.label': 'Custom OpenAI-compatible endpoint',
    'prov.custom.docs': 'Any server exposing /chat/completions (a proxy, a self-hosted model, an aggregator, Cloudflare Workers AI). Send the base URL and the model name; the key is optional.',
    'prov.omniroute.label': 'OmniRoute (self-hosted gateway)',
    'prov.omniroute.docs': "Self-hosted OpenAI-compatible gateway (github.com/diegosouzapw/OmniRoute). No AI key is stored in the bot: OmniRoute holds the provider accounts and routes/falls back between them. Run it on the bot's machine (default http://localhost:20128/v1), or point the bot elsewhere with OMNIROUTE_BASE_URL. If your OmniRoute sets REQUIRE_API_KEY=true, send its API key (OMNIROUTE_API_KEY).",
    'prov.ollama.label': 'Ollama (local, 100% free)',
    'prov.ollama.docs': "Runs on your own machine: install Ollama, then `ollama pull llama3.2`. No API key and no internet needed — but the bot must run on the same computer (or set the base URL to that computer's address).",
    'prov.ollama.free_note': 'Completely free and private — the model runs on your own computer. Needs ~8 GB RAM for a small model.',
    'prov.lmstudio.label': 'LM Studio (local, 100% free)',
    'prov.lmstudio.docs': 'Load a model in LM Studio and start its local server (port 1234), then test here. No key needed; the bot must run on the same computer.',
    'prov.lmstudio.free_note': 'Completely free and private — a local model with a Windows/macOS interface.',
    'prov.codex.label': 'ChatGPT subscription via Codex CLI',
    'prov.codex.docs': 'Uses `codex exec` with your ChatGPT login (install: npm i -g @openai/codex, then `codex login`). Reuses a ChatGPT plan you already pay for — no API key. The bot must run on that machine.',

    # =========================================================================
    # services — canned replies, file errors, Codex errors
    # =========================================================================
    "kb.strict_no_info": "I don't have enough information about that in the knowledge base.",
    "biz.apology_default": (
        "Sorry, I'm having trouble responding right now. Someone will get back to "
        "you shortly."
    ),
    "file.err.unsupported": "Unsupported file type. Allowed: {allowed}",
    "file.err.unsupported_type": "Unsupported file type: {suffix}",
    "file.err.empty": "The file is empty.",
    "file.err.too_large": "File too large (max {mb} MB).",
    "file.err.unreadable": "Could not read '{name}' (unsupported or corrupt).",
    "file.err.no_text": (
        "No readable text found in '{name}'. "
        "Scanned/image-only PDFs are not supported (no OCR)."
    ),
    "codex.err.not_installed": (
        "Codex CLI not found. Install it (npm i -g @openai/codex) and run `codex login`."
    ),
    "codex.err.bad_flags": (
        "Codex rejected the exec flags for your CLI version. Set CODEX_EXEC_ARGS "
        "in .env to flags your `codex exec` accepts (or leave it blank)."
    ),
    "codex.err.not_logged_in": "Codex isn't logged in — run `codex login` (Sign in with ChatGPT).",
    "codex.err.failed": "Codex failed to generate a reply. See logs.",
    "codex.err.empty": "Codex returned an empty reply.",
    "kbd.rule.add": "✍️ Send instructions",
    "kbd.rule.list": "📃 Rules list",
    "kbd.rule.ask_questions": "❓ Unanswered questions",
    "kbd.rule.approve": "✅ Approve and apply",
    "kbd.rule.edit": "✏️ Edit the text and resend",
    "kbd.rule.discard": "🗑 Discard",
    "kbd.res.add": "🔗 Add a resource",
    "kbd.res.list": "📃 Resources list",
    "kbd.unans.answer": "✍️ Answer",
    "kbd.unans.ignore": "🚫 Ignore",
    "kbd.gate.subscription": "🔒 Forced subscription (channels)",
    "kbd.gate.stars": "⭐ Paid messages (Stars)",
    "kbd.gate.list": "📃 What is required now",
    "kbd.gate.add_channel": "➕ Add a channel/group",
    "kbd.gate.refund": "↩️ Refund this star payment",
    "kbd.paid.buy": "⭐ Pay {stars} and send my message",
    # =========================================================================
    # handlers/gates.py — entry gates (/gate)
    # =========================================================================
    "gate.title": "🚪 <b>Entry gates</b>",
    "gate.body": (
        "Both gates are off by default and apply to the <b>private messages</b> "
        "people send to this bot. Telegram Business customer chats are never "
        "gated, so nothing that works today stops working."
    ),
    "gate.hint": "Turn them on here whenever you are ready.",
    "gate.sub.title": "🔒 <b>Forced subscription</b>",
    "gate.sub.body": (
        "Everyone must join the channels/groups below before the bot answers. "
        "People get join buttons, then a ✅ button that re-checks."
    ),
    "gate.sub.empty": "No channels yet.",
    "gate.sub.add_hint": "Current state: <b>{state}</b>",
    "gate.sub.ask": (
        "Send a public channel link, <code>@username</code>, or "
        "<code>@username | Title | invite-link</code>. The bot must be an admin "
        "there to check membership."
    ),
    "gate.sub.saved": "✅ Added #{id} <b>{title}</b> (<code>{ref}</code>).",
    "gate.sub.on_alert": "Forced subscription is ON",
    "gate.sub.off_alert": "Forced subscription is OFF",
    "gate.sub.row_on": "Enabled ✅",
    "gate.sub.row_off": "Disabled ⏸",
    "gate.sub.channel": "channel",
    "gate.sub.group": "group",
    "gate.stars.title": "⭐ <b>Paid messages (Telegram Stars)</b>",
    "gate.stars.body": (
        "Each message costs the number of stars you set. The bot answers the "
        "first free messages, then asks for stars and delivers the message once "
        "Telegram confirms the payment."
    ),
    "gate.stars.enabled": "Paid messages: <b>{state}</b>",
    "gate.stars.price": "Price per message: <b>{stars}</b> stars",
    "gate.stars.free": "Free messages before paying: <b>{count}</b>",
    "gate.stars.earned": "Paid messages: <b>{count}</b> · stars earned: <b>{stars}</b>",
    "gate.stars.need_price": "⚠️ Set a price above 0 — paid messages stay blocked until it is configured.",
    "gate.stars.hint": (
        "Tap a value to change it, or open /settings → Grounding for the same "
        "switches."
    ),
    "gate.stars.on_alert": "Paid messages are ON",
    "gate.stars.off_alert": "Paid messages are OFF",
    "gate.price.ask": "⭐ Send the price in stars as a number (e.g. 50).",
    "gate.price.bad": "Send the price as digits only.",
    "gate.price.range": "Send a number between 1 and {max}.",
    "gate.price.saved": "✅ Price set to <b>{stars}</b> stars; paid messages are on.",
    "gate.free.ask": "Send how many free messages each person gets (0 = none).",
    "gate.free.bad": "Send the number as digits only.",
    "gate.free.saved": "✅ Free messages before paying: <b>{count}</b>.",
    "gate.cb.type": "Send the value as your next message.",
    "gate.list.title": "📃 <b>What is required now</b>",
    "gate.list.payments": "<b>Recent payments</b>",
    "gate.list.payment_row": "#{id} chat <code>{chat_id}</code> — {stars}⭐ ({status})",
    "gate.refunded": "Marked as refunded.",
    "gate.refund_missing": "Payment not found.",
    "gate.status.subscription": "Forced subscription: <b>{state}</b> ({count} chat(s))",
    "gate.status.payments": "Paid messages: <b>{state}</b>",
    "gate.status.price": "Price: <b>{stars}</b> stars",
    "gate.status.free": "Free messages first: <b>{count}</b>",
    "gate.status.earned": "Paid: <b>{count}</b> · stars: <b>{stars}</b>",
    # --- what the visitor sees ---
    "gate.user.sub": (
        "🔒 Before I can answer you, please join these channels/groups:\n\n{list}\n\n"
        "Once you have, tap ✅ Check my subscription."
    ),
    "gate.user.sub_ok": "✅ Thanks — your subscription is confirmed. Send your message again 👇",
    "gate.user.still_missing": "Still not joined:\n{list}",
    "gate.user.pay": (
        "⭐ This message costs {stars} stars.\n"
        "Tap the button below to pay {stars} stars — I will send your message "
        "as soon as the payment goes through."
    ),
    "gate.user.free": "🎁 You have {left} free message(s) left.",
    "gate.pay.expired": "That invoice has expired — please send your message again.",
    "gate.pay.done": "✅ Payment received! Reading your message now…",
    "gate.pay.failed": "⚠️ The payment was not completed. Please try again.",
    "gate.pay.off": (
        "⚠️ A paid message arrived from chat <code>{chat_id}</code> while replies are OFF. "
        "No automatic reply was sent. Message: “{text}”"
    ),
    "gate.owner.copy": (
        "⭐ <b>Paid message ({stars} stars)</b>\n"
        "From: <b>{name}</b> (chat <code>{chat_id}</code>)\n\n"
        "<b>Message:</b>\n<i>{text}</i>\n\n"
        "<b>Reply:</b>\n{reply}"
    ),
    "kbd.gate.stars_toggle": "⭐ Turn paid messages on/off",
    "kbd.gate.price": "💲 Set the price (stars)",
    "kbd.gate.free": "🎁 Free messages before paying",
    "main.cmd.rules": "Instructions & topic rules",
    "main.cmd.unanswered": "Questions the bot could not answer",
    "main.cmd.resources": "Resources the bot can search",
    "main.cmd.gate": "Entry gates (subscribe / stars)",
    "set.group.learning": "Learning (rules & resources)",
    "set.group.gate": "Entry gates (private messages)",
    "set.opt.rules_enabled": "Follow my topic rules",
    "set.opt.rules_enabled.hint": (
        "Apply the rules you approved from /rules to every reply."
    ),
    "set.opt.resources_enabled": "Let the bot search my resources",
    "set.opt.resources_enabled.hint": (
        "Use the websites and Telegram groups/channels added in /resources when "
        "they help answer."
    ),
    "set.opt.unanswered_enabled": "Ask me about questions it cannot answer",
    "set.opt.unanswered_enabled.hint": (
        "The bot says it will ask the team, then sends you the question from "
        "/unanswered; your answer is learned as a quick answer."
    ),
    "set.opt.require_subscription_enabled": "Force subscription to my channels",
    "set.opt.require_subscription_enabled.hint": (
        "People must join before the bot answers; manage the list in /gate. "
        "Applies to private messages only."
    ),
    "set.opt.paid_messages_enabled": "Charge stars for messages",
    "set.opt.paid_messages_enabled.hint": (
        "Each message costs the price below. Switch paid messages off to keep the gate "
        "open. Works in direct bot chats and linked Telegram Business conversations."
    ),
    "set.opt.payment_message": "Payment message (before invoice)",
    "set.opt.payment_message.hint": (
        "Shown before the invoice. Use {stars} to insert the price automatically; "
        "send clear to restore the default text."
    ),
    "set.opt.paid_message_stars": "Price per message (stars)",
    "set.opt.paid_message_stars.hint": (
        "The number of Telegram Stars a person pays before their message reaches "
        "you. A positive price is required while paid messages are enabled."
    ),
    "set.opt.paid_message_free_count": "Free messages before paying",
    "set.opt.gate_copy_to_owner": "Send me a copy of gated messages",
    "set.opt.gate_copy_to_owner.hint": (
        "After a gated message is delivered, the bot forwards you the message and "
        "the reply it sent."
    ),
    "kbd.gate.verify": "✅ Check my subscription",
    "gate.user.still_missing_alert": "You have not joined yet",
    "gate.invoice.title": "{name}: paid message",
    "gate.invoice.default_title": "Paid message",
    "gate.invoice.desc": "Your message is delivered to {name} once Telegram confirms the payment ({stars} star).",
    "gate.invoice.label": "Message of the day",
    "gate.user.free_last": "🎁 That was your last free message — from now on each message costs {stars} stars.",
    "gate.refunded_local": "Refund recorded here, but Telegram refused the star refund — check the bot's balance.",
    # ==== append-below ====    # ==== append-below ====    # ==== append-below ====

    # =========================================================================
    # services/rules_service.py — topic rules + unanswered questions
    # =========================================================================
    "rule.status.rules": "Topic rules: {count} active",
    "rule.status.unanswered": "Unanswered questions: {count}",
    "rule.status.resources": "Resources: {count}",
    "rule.menu.title": "🧠 <b>Instructions & rules</b>",
    "rule.menu.body": (
        "Send me your instructions in your own words — tone, what to say and "
        "what never to say, prices, delivery, working hours.\n"
        "I split them into <b>topic rules</b> and show you a draft: nothing is "
        "applied until you tap ✅ Approve."
    ),
    "rule.menu.stats": "Active rules: <b>{rules}</b> · drafts waiting: <b>{drafts}</b>",
    "rule.menu.hint": (
        "Add rules: just send the text (or /rules_add). "
        "Pending questions: {unanswered}."
    ),
    "rule.ask": "✍️ Send the instructions now (or /cancel).",
    "rule.draft.title": "🧠 <b>Draft rules — review before applying</b>",
    "rule.draft.count": "{count} rule(s) from your text{ai}",
    "rule.draft.ai": " (organised by the AI)",
    "rule.draft.plain": " (split line by line)",
    "rule.draft.questions": "❓ <b>I need clarity on this:</b>",
    "rule.draft.hint": "Tap ✅ to apply them to every reply, ✏️ to update, 🗑 to discard.",
    "rule.draft.approved": "✅ Applied {count} rule(s).",
    "rule.draft.rejected": "🗑 Draft discarded ({count} rule(s)).",
    "rule.draft.gone": "That draft is no longer waiting.",
    "rule.empty": "No topic rules yet. Send /rules_add with your instructions.",
    "rule.list.title": "🧠 <b>Topic rules</b> ({count}) — tap to disable/enable:",
    "rule.list.row": "{icon} #{id} <b>{topic}</b>",
    "rule.list.row_body": "    {rule}",
    "rule.toggled.on": "Enabled ✅",
    "rule.toggled.off": "Disabled ⏸",
    "rule.deleted": "Deleted rule #{id}.",
    "rule.delete.missing": "No rule #{id}.",
    "rule.clear.ask": "Delete <b>all {count}</b> topic rules?",
    "rule.clear.done": "Deleted {count} rule(s).",
    "rule.disabled": (
        "Topic rules are switched off (/settings → Grounding). "
        "The rules are stored but not sent to the model."
    ),
    "rule.cb.send": "Send the instructions.",
    "rule.cb.step": "✍️ Send the instructions now (or /cancel).",
    "rule.cb.approved": "Applied ✅",
    "rule.cb.rejected": "Discarded 🗑",
    "rule.cb.toggled": "Updated",
    "rule.cb.not_found": "Not found.",
    "rule.usage": "Usage: /rules_add <your instructions>",
    "rule.pending.empty": "Nothing to organise — try again with some text.",
    # --- unanswered questions ---
    "unans.menu.title": "❓ <b>Questions I could not answer</b>",
    "unans.menu.none": "Nothing pending — the assistant answered everything. 🎉",
    "unans.menu.count": "<b>{count}</b> question(s) waiting for your answer.",
    "unans.menu.hint": "Tap a question, answer it, and the assistant learns it forever.",
    "unans.row": "#{id} — {question}",
    "unans.card": (
        "❓ <b>Question #{id}</b>\n"
        "From: <b>{name}</b> (chat <code>{chat_id}</code>)\n"
        "Asked: {when}\n\n"
        "<i>{question}</i>"
    ),
    "unans.notify": (
        "❓ <b>The assistant could not answer</b>\n"
        "From: <b>{name}</b> (chat <code>{chat_id}</code>)\n\n"
        "<i>{question}</i>\n\n"
        "Reply to this message with the answer and I will send it to them and "
        "remember it. Or use /unanswered to see the list."
    ),
    "unans.ask": "✍️ Send the answer for #{id} (or /cancel).",
    "unans.asked": "Send the answer as your next message.",
    "unans.answered": "✅ Answer saved (#{id}) and sent to the person who asked.",
    "unans.answered_learned": "✅ Saved and reused as a quick answer (#{faq}).",
    "unans.answered_not_sent": "✅ Answer saved, but it could not be delivered.",
    "unans.ignored": "Ignored.",
    "unans.gone": "That question is no longer pending.",
    "unans.empty_answer": "Empty answer — nothing saved.",
    "unans.deleted": "Removed from the list.",
    "unans.clear.ask": "Clear all {count} pending question(s)?",
    "unans.clear.done": "Cleared {count} question(s).",
    "unans.auto_reply": (
        "Thanks for your question 🙏 I have passed it to the team and someone "
        "will get back to you shortly."
    ),

    # =========================================================================
    # services/resource_service.py — resources the assistant can search/share
    # =========================================================================
    "res.status.summary": "Resources: {total} ({links} link(s) · {telegram} Telegram)",
    "res.menu.title": "📚 <b>Resources</b>",
    "res.menu.body": (
        "Send a link (website, platform, Telegram group or channel) and I will "
        "read it, add it to the knowledge base, and use it when answering — "
        "either as facts or as a link to hand out.\n\n"
        "Shape: <code>https://example.com | Title | short note</code> "
        "(the title and note are optional). Plain text works too."
    ),
    "res.menu.empty": "No resources yet.",
    "res.menu.count": "<b>{count}</b> resource(s) saved — {telegram} Telegram, {links} link(s).",
    "res.menu.hint": "Add: send the link (or /resources_add). List: /resources_list.",
    "res.ask": "🔗 Send the link (or the text), or /cancel.",
    "res.cb.ask": "Send the link.",
    "res.added.link": "✅ Saved <b>{title}</b>.\n{url}\n\n{read}",
    "res.added.read": "Read {chars} characters into the knowledge base — I can quote it now.",
    "res.added.unread": (
        "Saved as a reference. (I could not read the page — Telegram links and "
        "some sites need a browser; the link still works in replies.)"
    ),
    "res.added.telegram": (
        "✅ Saved your Telegram channel/group: <b>{title}</b>\n{url}\n\n"
        "I will point people to it when it fits."
    ),
    "res.added.text": "✅ Saved as a text resource (<b>{title}</b>) — {chars} characters.",
    "res.failed": "I could not read that link, but I saved it as a reference.",
    "res.empty_input": "Nothing to save — send a link or some text.",
    "res.list.title": "📚 <b>Resources</b> ({count}) — tap to enable/disable:",
    "res.list.empty": "No resources yet. Send a link, or use /resources_add.",
    "res.row.title": "#{id} <b>{title}</b>",
    "res.row.kind": "Type: {kind}",
    "res.row.url": "Link: {url}",
    "res.row.notes": "Note: {notes}",
    "res.row.chars": "Read: {count} characters",
    "res.row.disabled": "⏸ Disabled",
    "res.kind.link": "web page",
    "res.kind.telegram": "Telegram channel/group",
    "res.kind.text": "text",
    "res.toggled.on": "Enabled ✅",
    "res.toggled.off": "Disabled ⏸",
    "res.deleted": "Deleted resource #{id}.",
    "res.delete.missing": "No resource #{id}.",
    "res.clear.ask": "Delete all {count} resource(s)?",
    "res.clear.done": "Deleted {count} resource(s).",
    "res.usage": "Usage: /resources_add <link or text>",
    "res.disabled": (
        "Resources are switched off (/settings → Grounding). "
        "They stay stored but are not sent to the model."
    ),

    # ==== append-below ====
}

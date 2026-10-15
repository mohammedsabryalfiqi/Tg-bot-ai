"""`/setup` — a guided checklist that walks the owner from "bot created" to
"answering customers", with live status detection for each step.

The telegram-side steps (Business/Secretary mode in @BotFather, connecting the
bot in Telegram Business → Chatbots) cannot be automated — Telegram requires the
account owner to do them in the app — so this module explains each one exactly
and verifies what can be verified.
"""

from __future__ import annotations

import logging

import database
import handlers
import keyboards
import utils
from services import ai_service, faq_service

log = logging.getLogger("smartel.setup")

STEP_LABELS = {
    "secretary": "1️⃣ Business/Secretary mode in @BotFather",
    "business": "2️⃣ Connect in Telegram Business → Chatbots",
    "ai": "3️⃣ Choose the AI provider",
    "content": "4️⃣ Add your answers (quick answers / knowledge base)",
    "mode": "5️⃣ Choose the reply mode",
    "test": "6️⃣ Send a test message",
}

DETAILS = {
    "secretary": (
        "1️⃣ <b>Enable Business (Secretary) mode</b>\n\n"
        "Telegram only lets a bot answer on your behalf if it is switched to "
        "business mode:\n\n"
        "1. Open <b>@BotFather</b> in Telegram\n"
        "2. Send /mybots\n"
        "3. Pick this bot\n"
        "4. <b>Bot Settings</b> → <b>Business Mode</b> (some app versions call it "
        "<b>Secretary Mode</b>)\n"
        "5. Tap <b>Turn on</b>\n\n"
        "Then come back and check this list with /setup."
    ),
    "business": (
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
    "ai": (
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
    "content": (
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
    "mode": (
        "5️⃣ <b>Choose how replies are sent</b>\n\n"
        "• 📝 <b>Draft mode</b> (safest): the bot writes the reply and waits — you "
        "tap Send / Edit / Reject.\n"
        "• 🟢 <b>Auto-reply</b>: the bot answers immediately, and you get a "
        "notification for every reply.\n"
        "• 🔴 <b>Off</b>: the bot only notifies you.\n\n"
        "Use /mode to switch any time. Start with Draft mode for a day or two, then "
        "switch to Auto-reply once you trust the answers."
    ),
    "test": (
        "6️⃣ <b>Test it end to end</b>\n\n"
        "1. From <b>another</b> Telegram account (a friend's phone works), send a "
        "message to your business account.\n"
        "2. With Draft mode on, you get an approval card here — tap Send.\n"
        "3. With Auto-reply on, the answer goes out by itself.\n\n"
        "Nothing arriving? Check /health, and confirm that “Allow bot to reply to "
        "messages” is enabled in Telegram Business → Chatbots."
    ),
}


def _status() -> dict:
    conns = database.list_business_connections()
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
        "mode": mode != "off",
        "test": database.count_ai_replies() > 0,
    }


def render_checklist() -> str:
    state = _status()
    lines = ["🚀 <b>Setup</b>", ""]
    for key, label in STEP_LABELS.items():
        icon = "✅" if state.get(key) else "⬜"
        lines.append(f"{icon} {label}")
    lines.append("")
    if state["business"]:
        lines.append("Business connection: <b>live and allowed to reply</b> ✅")
    elif database.list_business_connections():
        lines.append("Business connection found, but the bot is <b>not allowed to "
                     "reply</b> — enable it in Telegram Business → Chatbots ⚠️")
    else:
        lines.append("No business connection yet — that is step 2️⃣ above.")
    lines.append("")
    lines.append("Tap a step below for the exact instructions.")
    return "\n".join(lines)


def send_checklist(chat_id: int) -> None:
    handlers.bot.send_message(chat_id, render_checklist(), parse_mode="HTML",
                              reply_markup=keyboards.setup_checklist(STEP_LABELS))


def send_step(chat_id: int, key: str) -> None:
    detail = DETAILS.get(key)
    if detail is None:
        return send_checklist(chat_id)
    extra = []
    if key == "ai":
        extra.append("Current: " + " · ".join(ai_service.status_lines()))
    elif key == "content":
        extra.append(f"Knowledge base items: {len(database.list_kb_items())} · "
                     f"Quick answers: {faq_service.count()}")
    elif key == "business":
        conns = database.list_business_connections()
        extra.append(f"Connections detected: {len(conns)}")
    text = detail + ("\n\n" + "\n".join(utils.escape(line) for line in extra) if extra else "")
    handlers.bot.send_message(chat_id, text, parse_mode="HTML",
                              reply_markup=keyboards.setup_checklist(STEP_LABELS))

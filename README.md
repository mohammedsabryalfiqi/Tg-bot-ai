# SmarTel — Telegram Business Managed AI Bot

**Languages:** English (this file) · [العربية / Arabic](README.ar.md) · [فارسی / Persian](README_FA.md)

SmarTel is a **Telegram Business "managed bot"** AI assistant — the same model as
ChatPlace's *"AI Agent connected to a Telegram Business account"*. A Telegram
Business user connects the bot to their own account through Telegram's native
**Settings → Telegram Business → Chat Bots** screen. From then on the bot receives
that account's **incoming private customer messages** and answers them **on behalf
of the account**, from the owner's own content (quick answers + knowledge base).

It uses **only the official Telegram Bot API business features** — no Telethon /
Pyrogram userbot, no phone number / login code / 2FA / session string, no scraping.
The bot token comes from **@BotFather**.

> من هنا للنسخة العربية: [README.ar.md](README.ar.md)

---

## What it does

- 🤖 **Answers customers as you** — auto-reply, or **draft mode** where you tap
  **Send / Edit / Reject / Pause chat** first.
- ⚡ **Instant quick answers** (`/faq`): keyword-matched canned replies sent
  **verbatim** — the model never improvises your prices.
- 📚 **Knowledge base** (`/kb`): `.txt`, `.md`, `.pdf`, `.docx` with vector search
  (embeddings) and an automatic keyword-search fallback. Optional **strict KB
  mode** (answer only from the KB).
- 🧩 **18 AI providers**, switchable from inside Telegram — **12 of them usable at
  zero cost**: Google Gemini, Groq, Cerebras, OpenRouter, Mistral, NVIDIA NIM,
  SambaNova, Hugging Face, Pollinations (**no key at all**), Ollama / LM Studio
  (local), plus the paid ones (OpenAI, Anthropic, DeepSeek, xAI, Together) and any
  OpenAI-compatible endpoint or your **ChatGPT subscription via the Codex CLI**.
- 🆓 **`/freeai`** — a free-provider shortlist with each one's real limits, and a
  one-tap switch. No credit card and no balance needed anywhere on that list.
- 🩺 **Failures that explain themselves**: a rejected key, an account with no
  credit, a wrong model name, a free-tier rate limit and a region block are
  reported separately, each with the fix — plus **🔄 Load models**, which asks the
  provider which models your key can actually run.
- 🗣️ **Replies in the customer's language** (`reply_language=auto`), with tone and
  persona you configure (`assistant_name`, `business_name`, `tone`, `signature`).
- 🧠 **Per-customer memory**, isolated per conversation.
- 🙋 **Owner takeover**: the moment you reply yourself in a chat, the bot backs off
  for that chat (default 30 min).
- 🚦 **Per-customer rate limit** (default 20 msgs/hour) with automatic pause.
- 🛡️ **Safety routing**: sensitive topics (refunds, complaints, legal / medical /
  financial, personal data, credentials, all-caps anger) are forced to approval
  even in auto mode.
- 🧾 **Owner tools**: `/chats`, `/chat <id>`, `/reply`, `/takeover`, `/stats`,
  `/health`, `/export` (JSON backup, never contains keys).
- 🔐 **Owner-only control**, encrypted API keys at rest, secret redaction in logs,
  HTML-safe message sending, update de-duplication and burst batching.
- 🧭 **Guided setup** (`/setup`) with a live checklist, plus a **claim code** so you
  can go from "bot token" to a working assistant without looking up your user id.

### Normal bot vs. Business managed bot

| | Normal bot | **SmarTel (Business managed bot)** |
| --- | --- | --- |
| Who messages it | Users chat the bot directly | Customers message **your account**; the bot acts on your behalf |
| How it connects | Users press *Start* | You connect it in **Telegram Business → Chat Bots** |
| Update types | `message` | `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages` |
| Replies | from the bot | **from your business account** (via `business_connection_id`) |

If a non-owner messages the SmarTel bot **directly**, it simply explains that it is
a managed assistant — it does not chat there.

---

## Requirements

- **Python 3.10+** (or Docker — no Python needed).
- A **Telegram Business** account: Telegram Business features require **Telegram
  Premium** on the account that connects the bot.
- A bot created with **@BotFather**, with **Business Mode** enabled (some app
  versions call it **Secretary Mode**).
- One AI provider — **a paid one is not required**: a free-tier key (Google
  Gemini, Groq, Cerebras, Mistral, OpenRouter, …), a keyless endpoint
  (Pollinations), a **local model** (Ollama / LM Studio), a paid API key, or your
  ChatGPT plan via Codex CLI. Send `/freeai` inside Telegram for the shortlist.
- A machine that stays on (PC, Raspberry Pi, VPS) — the bot must keep running to
  answer.

---

## Quick start (7 steps)

### 1. Create the bot in BotFather
1. Open **@BotFather** → `/newbot` → pick a name and a `@username` ending in `bot`.
2. Copy the **token** (`123456789:AA...`).

### 2. Install and run
```bash
git clone <your-fork-url> && cd Tg-bot-ai
./start.sh          # Linux / macOS / WSL  — creates .venv, installs deps, runs
start.bat           # Windows
```
Or do it by hand:
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
The first launch runs a small wizard (it asks for the token; you can leave the
owner id empty) and then prints:

```
 OWNER CLAIM CODE (send this to your bot in Telegram):
     /start 7B31F90C
```

### 3. Claim ownership
Send `/start 7B31F90C` (your code) to the bot in Telegram. It replies
"You are now the owner" and remembers that forever.

### 4. Pick an AI provider — inside Telegram
`/ai` → choose a provider → paste the API key → pick a model → **Test connection**.
No credit card? Send **`/freeai`** (or tap **🆓 Free providers**) and pick one —
the bot switches to it and asks for its key in the same tap.

- 🆓 **Google Gemini** (`aistudio.google.com/app/apikey`) — the most generous free
  tier, a Google account is enough.
- 🆓 **Groq** (`console.groq.com/keys`) and **Cerebras** (`cloud.cerebras.ai`) —
  free with an email only, and by far the fastest.
- 🆓 **OpenRouter** (`openrouter.ai/keys`) — one key, hundreds of models; use a
  model whose name ends in `:free`.
- 🆓 **Mistral**, **NVIDIA NIM**, **SambaNova**, **Hugging Face** — more free tiers.
- 🔓 **Pollinations** — needs **no key at all** (slow and best effort: good to
  prove the bot works today, not for a busy shop).
- 💻 **Ollama** (`http://localhost:11434/v1`) / **LM Studio** — free, private,
  local; needs a decent machine.
- 💳 **OpenAI**, **Anthropic Claude**, **DeepSeek**, **xAI (Grok)**, **Together**,
  or **custom** for any OpenAI-compatible gateway. These need **credit on the API
  account** — a ChatGPT Plus or Claude subscription is *not* API credit, which is
  the usual reason a brand-new key "does not work".

Then press **🧪 Test connection**. If it fails the bot says exactly why (bad key ·
no credit · unknown model · rate limit · region) and offers a free provider to
switch to. If only the model name is wrong, use **🔄 Load models from the
provider** to see the names your key can run.

### 5. Turn on Business (Secretary) mode
1. **@BotFather** → `/mybots` → your bot.
2. **Bot Settings** → **Business Mode** (a.k.a. **Secretary Mode**) → **Turn on**.

Without this step Telegram refuses to connect the bot to your account.

### 6. Connect the bot in Telegram Business
On the account that will answer customers (needs Premium):
1. Telegram → **Settings**.
2. **Telegram Business** → **Chat Bots**.
3. Enter your bot's `@username`.
4. Choose the scope: **All private chats except…** (recommended) or selected chats.
5. Under **Bot Permissions** enable **"Allow bot to reply to messages"** — required;
   without it the bot can read but never answer.
6. **Save.**

The bot messages you as soon as the connection is live.

### 7. Teach it your content, then choose a mode
```
/faq_add سعر, كام, بكام, price :: Our prices start at 500 EGP; delivery is 50 EGP.
```
(one or more triggers separated by commas, then `::`, then the answer.)

**How quick answers match** — the triggers in one entry are *alternatives*, not a
checklist: any one of them is enough. A **direct** hit (the trigger appears in the
message, word-boundary for English, substring for Arabic — so «السعر» matches
«سعر») sends your text **verbatim**, with no model involved. A **word-form** hit
(deliver ↔ delivery, order ↔ orders) is only handed to the model as an
authoritative answer, so it still sounds natural; lower `faq_match_threshold` to
50 if you want those to be sent verbatim too. Test any wording with
`/faq_search` — it says whether a message would get an instant reply.

- Upload longer material with `/kb_upload` (`.txt`/`.md`/`.pdf`/`.docx`) or `/kb_add`.
- Describe yourself: `/settings` → **Persona & language**.
- Choose how replies are sent: `/mode`
  - `draft` — the bot writes the reply and waits for your tap (safest).
  - `auto` — it answers customers immediately.
  - `off` — silent; you only get notified.

**Test it** from a *different* Telegram account: message your business account and
watch the reply arrive from your own account. `/health` checks everything,
`/aitest` tests the model, `/status` shows the connection.

---

## Commands (owner only)

| Command | Action |
| --- | --- |
| `/start` | Control panel (inline buttons) |
| `/setup` | Guided 6-step checklist with live status |
| `/ai` (`/ai_setup`, `/connect_ai`, `/provider`) | Provider, API key, model, live model list, test |
| `/freeai` (`/freeproviders`) | Free providers only — no credit card, no balance |
| `/aitest` · `/aimodel <name>` | Test the connection · set any model |
| `/mode [auto\|draft\|off]` | How replies are sent |
| `/faq` (`/qa`) | Quick-answers menu (`/faq_add`, `/faq_list`, `/faq_del`, `/faq_search`, `/faq_import`, `/faq_export`, `/faq_clear`) |
| `/kb` | Knowledge base (`/kb_add`, `/kb_upload`, `/kb_list`, `/kb_search`, `/kb_delete`, `/kb_clear`) |
| `/settings` | All settings (grouped screens) |
| `/status` · `/health` · `/stats` | Status, health checks, statistics |
| `/chats` · `/chat <id>` | Recent chats · one transcript |
| `/reply <chat_id> <text>` | Send a message yourself from the business account (pauses the bot for that chat) |
| `/takeover <id>` · `/handback <id>` | Pause / resume the AI for one chat |
| `/instructions [text\|clear]` | Standing instruction added to every reply |
| `/memory_clear` · `/pause_chat` · `/resume_chat` | Memory and pause control |
| `/auto_on` `/auto_off` · `/approval_on` `/approval_off` | Coarse switches behind `/mode` |
| `/connections` · `/export` · `/reset` · `/cancel` · `/help` | Connections, JSON backup, cleanup, cancel input, help |

---

## Settings

Editable at runtime from `/settings` (booleans toggle in place; numbers/text/enums
open a sub-screen). Stored in SQLite; the `.env` `DEFAULT_*` values only seed it
once.

| Setting | Default | Meaning |
| --- | --- | --- |
| `auto_reply_enabled` | `false` | Send replies automatically |
| `approval_mode_enabled` | `true` | Draft mode: propose replies for approval |
| `sensitive_requires_approval` | `true` | Force approval for sensitive topics |
| `monitoring_mode` | `true` | Notify you about incoming / auto activity |
| `memory_enabled` | `true` | Per-customer conversation memory |
| `typing_indicator` | `true` | Keep the "typing…" bubble alive while generating |
| `reply_debounce_seconds` | `1.0` | Batch rapid-fire messages into one reply (0–8) |
| `process_nontext_enabled` | `false` | Treat media captions as messages |
| `nontext_ack_message` | *(empty)* | Auto-reply to a photo/voice with no text |
| `greet_new_customers` / `welcome_text` | `false` / *(empty)* | Welcome a first-time customer |
| `owner_takeover_pause_minutes` | `30` | Cool-down after you reply yourself |
| `max_messages_per_customer_per_hour` | `20` | Rate limit per customer |
| `assistant_name` / `business_name` / `business_description` | *(empty)* | Persona and business context |
| `tone` | `friendly` | `friendly`\|`professional`\|`casual`\|`concise`\|`warm` |
| `reply_language` | `auto` | `auto` mirrors the customer, or force `ar`/`en`/… |
| `signature` | *(empty)* | Appended to every reply |
| `max_reply_chars` | `900` | Target maximum reply length |
| `disclose_ai` | `false` | Whether it may say it is an AI when asked directly |
| `custom_instructions` | *(empty)* | Extra standing instructions (also `/instructions`) |
| `faq_enabled` / `faq_direct_reply` | `true` | Use quick answers / send exact matches verbatim |
| `faq_match_threshold` | `60` | Quick-answer match strictness (%) |
| `kb_enabled` / `strict_kb_mode` | `true` / `false` | Use the KB / answer only from the KB |
| `ai_base_url` | *(empty)* | Custom OpenAI-compatible base URL |
| `temperature` / `max_tokens` | `0.4` / `800` | Sampling temperature and output cap |
| `public_direct_bot_chat_enabled` | `false` | Safety flag for direct (non-business) DMs |

**Safe by default:** with `auto_reply_enabled=false` + `approval_mode_enabled=true`
nothing reaches a customer until you act.

---

## How a customer message flows

```
business_message ──► guards (bot echo, owner takeover)
                  ──► record + de-duplicate (Telegram retries can't double-reply)
                  ──► automation switches, pause state, rate limit
                  ──► batch a burst of messages into one turn
                  ──► quick answers: exact match ⇒ canned reply, verbatim
                  ──► otherwise prompt = persona + instructions + FAQ + KB + memory
                  ──► model (or Codex) ──► signature
                  ──► sensitive? ⇒ approval card, else auto-send (or draft)
                  ──► "typing…" keep-alive while generating
```

Edited / deleted customer messages invalidate the matching pending approvals, so
you never send a reply to a message that no longer exists.

---

## AI providers

| Provider id | Label | Cost | Key required | Embeddings |
| --- | --- | --- | --- | --- |
| `google` | Google Gemini | 🆓 free tier | yes | ✅ `text-embedding-004` |
| `groq` | Groq | 🆓 free tier | yes | — |
| `cerebras` | Cerebras | 🆓 free tier | yes | — |
| `openrouter` | OpenRouter | 🆓 `:free` models | yes | — |
| `mistral` | Mistral AI | 🆓 free tier | yes | — |
| `nvidia` | NVIDIA NIM | 🆓 signup credits | yes | — |
| `sambanova` | SambaNova | 🆓 free tier | yes | — |
| `huggingface` | Hugging Face | 🆓 small allowance | yes | — |
| `pollinations` | Pollinations | 🆓 no key needed | **no** | — |
| `ollama` | Ollama (local) | 💻 free, local | no | ✅ `nomic-embed-text` |
| `lmstudio` | LM Studio (local) | 💻 free, local | no | — |
| `codex` | ChatGPT plan via Codex CLI | 💻 your subscription | no | — |
| `openai` | OpenAI (ChatGPT API) | 💳 credit needed | yes | ✅ `text-embedding-3-small` |
| `anthropic` | Anthropic (Claude) | 💳 credit needed | yes | — |
| `deepseek` | DeepSeek | 💳 top-up needed | yes | — |
| `xai` | xAI (Grok) | 💳 credit needed | yes | — |
| `together` | Together AI | 💳 credit needed | yes | — |
| `custom` | Any OpenAI-compatible endpoint | depends | optional | maybe |

Providers without embeddings still use the knowledge base through keyword search.
Keys set in `.env` win over keys stored from Telegram; keys stored from Telegram are
encrypted at rest when `SMARTEL_FERNET_KEY` is set.

### 🆓 Free providers (no credit card, no balance)

`/freeai` prints this list inside Telegram with the current limits, and one tap
switches the bot to any of them. Where to get each key:

| Provider | Free key from | What you get free | Notes |
| --- | --- | --- | --- |
| **Google Gemini** | `aistudio.google.com/app/apikey` | Hundreds of requests/day on the Flash models, 1M-token context | The most generous tier; only a Google account is needed. Also powers KB embeddings. |
| **Groq** | `console.groq.com/keys` | ~30 requests/min, thousands/day on small models | Fastest replies of all; email signup only. |
| **Cerebras** | `cloud.cerebras.ai` → API Keys | ~1M tokens/day | Very fast; the free model catalogue rotates, so use 🔄 Load models. |
| **OpenRouter** | `openrouter.ai/keys` | ~50 free requests/day | Use a model ending in `:free`; any other model needs credit. |
| **Mistral** | `console.mistral.ai/api-keys` | Free "Experiment" plan, ~1 request/s | No card, but phone verification; prompts may train their models unless you opt out. |
| **NVIDIA NIM** | `build.nvidia.com` | Free API credits at signup | Credits run out instead of refreshing daily; copy model names exactly (`meta/llama-3.1-8b-instruct`). |
| **SambaNova** | `community.sambanova.ai` | Free developer key | Fast open models, rate limited. |
| **Hugging Face** | `huggingface.co/settings/tokens` | Small monthly allowance | A "Read" token is enough; gated models must be accepted on their page once. |
| **Pollinations** | — (no key) | Unlimited-ish but throttled | ⚠️ Community endpoint: ~1 request per 30s per IP, no uptime promise, customer text goes to a third party. Fine for a first test, not for a busy shop. |
| **Ollama / LM Studio** | — (local) | Everything, forever | 💻 100% free and private; the bot must run on the same machine. |

Free tiers are **rate limited** (per minute / per day) and reset on their own —
that is not a broken key. Stack two or three providers and switch with `/ai` if
you hit a ceiling.

### "My key does not work" — what the bot now tells you

Every failure is classified, so the message says what to do instead of a bare
"not accepted":

| What you see | What it means | Fix |
| --- | --- | --- |
| `the account has no credit left or its free quota is used up` | The key is valid but there is no money/quota behind it. Common with OpenAI, Anthropic, DeepSeek, Together — a ChatGPT/Claude **subscription is not API credit**. | Add credit, or tap a 🆓 free provider the bot offers in the same message (`/freeai`). |
| `That is your Telegram bot token (from @BotFather), not an AI API key` | The `123456789:AA…` token was pasted into the AI-key field. | Nothing to fix in Telegram — paste the **AI provider's** key instead (the bot recognises the shape and says this before sending any request). |
| `This looks like a key for <provider>, but you are adding it to <other>` | A key from another provider (e.g. a Gemini `AIza…` key while Groq is selected). | Switch to the provider the key belongs to, or get a key for the selected one. |
| `rejected this API key (HTTP 401/403)` | The key itself is wrong, expired, revoked, pasted with spaces, or from a **different provider**. | Copy it again from the right console; the message names the exact URL. |
| `Finish the account verification first` | The provider still wants email/phone verification (e.g. Mistral). | Verify the account, then re-send the key. |
| `rejected the model name` | The key cannot run that model, or the name differs on this provider. | `/ai` → 🧠 Change model → **🔄 Load models from the provider**. |
| `hit a rate/quota limit` / `rate limiting the bot right now` | Free-tier ceiling (per minute/day). **Nothing is broken** — it resets by itself. | Wait a moment; or move to Gemini/Groq/Cerebras for a bigger daily quota. |
| `refused the request because of your country/region` | The provider does not serve your region. | Switch provider — the free ones above all work widely. |
| `404 — the base URL or the endpoint path is wrong` | Wrong endpoint (usually missing `/v1`). | Fix the base URL (`/ai` → 🌐 Set base URL for `custom`). |
| `Could not reach the provider` | Network/DNS/firewall on the machine running the bot. | Check internet access from that machine. |

The same diagnosis appears in `/health`, in `python main.py --check`, and in the
notification sent when a customer reply could not be generated.

### ChatGPT subscription via the Codex CLI (optional)
```bash
npm install -g @openai/codex      # or: brew install --cask codex
codex login                       # choose "Sign in with ChatGPT"
```
Then set `MODEL_BACKEND=codex` in `.env`, or pick **Codex** in `/ai`.

Caveats: it is slower than an API call, ChatGPT-plan rate limits apply, and
embeddings are unavailable (keyword search is used instead). The mechanism is
legitimate, but automating a personal subscription for a customer-facing service is
a usage-policy gray area — review OpenAI's terms.

---

## Configuration (.env)

Everything below is optional if you configure the bot from Telegram.

```env
BOT_TOKEN=123456789:AA...          # from @BotFather
OWNER_USER_ID=                     # optional; empty ⇒ use the printed claim code
ALLOW_OWNER_CLAIM=true             # set false to forbid claiming

AI_PROVIDER=google                 # free: google|groq|cerebras|openrouter|mistral|
                                   #       nvidia|sambanova|huggingface|pollinations|
                                   #       ollama|lmstudio
                                   # paid: openai|anthropic|deepseek|xai|together
                                   # other: custom|codex
AI_API_KEY=                        # or GEMINI_API_KEY / GROQ_API_KEY /
                                   # CEREBRAS_API_KEY / OPENAI_API_KEY / …
                                   # (pollinations, ollama, lmstudio need no key)
AI_MODEL=                          # empty ⇒ the provider's default model
AI_BASE_URL=                       # required for `custom`, useful for local models

SMARTEL_FERNET_KEY=                # encrypts stored API keys (optional, recommended)
DEFAULT_MODEL=gpt-4.1-mini         # seeds the settings table on first run
DEFAULT_AUTO_REPLY=false
DEFAULT_APPROVAL_MODE=true

DB_PATH=storage/smartel.db
UPLOADS_DIR=storage/uploads
VECTOR_STORE_DIR=storage/vector_store
WORKER_THREADS=4
DEBUG=false
```

Generate a Fernet key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

CLI: `python main.py` · `--debug` (verbose logs) · `--check` (verify config + live
AI/Telegram connectivity without polling) · `--reset` (re-run the wizard / wipe
runtime state).

---

## Running it 24/7

**Docker (easiest):**
```bash
cp .env.example .env     # fill in BOT_TOKEN and the provider key
docker compose up -d --build
docker compose logs -f   # the claim code appears here on first run
```

**systemd on a VPS:**
```ini
# /etc/systemd/system/smartel.service
[Unit]
Description=SmarTel Telegram Business assistant
After=network-online.target

[Service]
WorkingDirectory=/opt/Tg-bot-ai
ExecStart=/opt/Tg-bot-ai/.venv/bin/python main.py
Restart=always
RestartSec=5
User=smartel

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now smartel && journalctl -u smartel -f
```

⚠️ Never run two instances with the same token — Telegram stops both with
`409 Conflict`.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| No customer messages arrive | Business Mode off in BotFather, bot not connected under **Telegram Business → Chat Bots**, or the account is not Premium. |
| The bot reads but never replies | Enable **"Allow bot to reply to messages"** in the bot's Business permissions; verify with `/status`. |
| Replies are generic / the bot apologises | Key invalid or out of quota: `/ai` → **Test connection**, or `/health`. |
| "The key was not accepted" although I just created it | The bot now says *why*: no credit on the account, key from another provider, verification pending, wrong model name, rate limit or region block. Read the **How to fix it** bullets under the error, and see ["My key does not work"](#my-key-does-not-work--what-the-bot-now-tells-you). |
| I have no credit card / no balance | `/freeai` → pick **Google Gemini**, **Groq** or **Cerebras** (free with an email/Google account), or **Pollinations** which needs no key at all. One tap switches the bot and asks for the new key. |
| The model name is refused | `/ai` → 🧠 Change model → **🔄 Load models from the provider**: it lists what your key can actually run. |
| Nothing happens in one chat | That chat is paused (earlier takeover or rate limit): `/chats`, `/handback <chat_id>`. |
| `409 Conflict` in the logs | Another instance is polling with the same token — stop it. |
| It doesn't know my info | Add content: `/faq_add` for frequent questions, `/kb_upload` for documents; consider `strict_kb_mode`. |
| Replies are cut or oddly formatted | Raise `max_reply_chars` in `/settings`, or try a stronger model via `/ai`. |
| Lost the claim code | Restart the bot — a new code is printed (until ownership is claimed). |
| `python-telegram`/token errors on start | Run `python main.py --check` for a precise diagnosis. |

---

## Security & privacy

- Official Bot API only: no phone login, no login codes, no userbot sessions.
- Messages are stored locally in `storage/smartel.db`. Only the AI provider you
  choose receives message text, and only to generate the reply.
- API keys are encrypted at rest (Fernet) when `SMARTEL_FERNET_KEY` is set, are
  masked in logs, and are never included in `/export`.
- Only the owner (configured id or the claimed account) can control the bot; direct
  DMs from anyone else get a short explanatory notice.
- Outgoing model text is converted/escaped to valid Telegram HTML before sending, so
  a stray `<` or `**markdown**` can never make a reply fail.

---

## Tests & CI

```bash
pip install -r requirements-dev.txt
pytest -q                       # full suite (unit + integration)
pytest -q tests/integration     # registration → claim → business reply, end to end
python main.py --check          # configuration + connectivity check
```
`.github/workflows/tests.yml` runs the suite (and coverage, when configured) on each
push and pull request.

---

## Tech notes

- Pure-Python Telegram layer (`pyTelegramBotAPI`) plus raw HTTP helpers for
  `getBusinessConnection` / `getFile` so behaviour doesn't depend on the library
  version.
- SQLite with a small typed settings layer (`SETTINGS_SCHEMA`), WAL-friendly
  write transactions, and claim-based approval delivery states
  (`pending → sending → sent` / `delivery_uncertain`) so a crash can never silently
  double-send.
- Sending is chunked to Telegram's 4096-char limit, retried on transient network
  errors, and retried as plain text if Telegram rejects the entities.
- Duplicate updates are ignored, bursts are batched, and typing state is refreshed
  while the model works.

---

## License

MIT — see `LICENSE`. Based on the original **SmarTel** project by AliZakaee, with
substantial extensions (multi-provider AI layer, quick answers, persona controls,
reply modes, owner tools, guided setup, provider-agnostic embeddings and a much
larger test suite).

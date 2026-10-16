"""Entrypoint.

Lifecycle: parse CLI -> configure logging -> (--reset) -> load/wizard config ->
init DB & services -> init bot -> validate token -> clear any stale webhook ->
register handlers (order matters) -> notify owner -> long-poll with the business
update types in ``allowed_updates`` (omitting them is THE classic pitfall —
business handlers would silently never fire).

Run:
    python main.py            # normal run (first launch shows the wizard)
    python main.py --reset    # reconfigure / wipe runtime state
    python main.py --debug    # verbose logging
    python main.py --check    # verify config + AI + Telegram, then exit
"""

from __future__ import annotations

import logging
import sys
import time

import telebot

import config
import database
import handlers
import i18n
import keyboards
import security
import telegram_api
import utils
from handlers import (
    ai_setup,
    approvals,
    business_updates,
    direct_messages,
    faq as faq_handler,
    knowledge_base,
    owner_commands,
    owner_tools,
    settings as settings_handler,
)
from services import ai_service, file_service, providers

log = logging.getLogger("smartel")

VERSION = "2.0.0"

# The single source of truth for which updates we receive. Business types MUST
# be present or the corresponding handlers never fire.
ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]

_redaction_filter = utils.SecretRedactionFilter()


# =============================================================================
# Logging
# =============================================================================
def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    handler.addFilter(_redaction_filter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("smartel").setLevel(level)
    # Quiet noisy third-party loggers unless debugging.
    if not debug:
        logging.getLogger("TeleBot").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


# =============================================================================
# Bot setup
# =============================================================================
def build_bot(cfg: config.Config) -> telebot.TeleBot:
    return telebot.TeleBot(
        cfg.bot_token,
        parse_mode="HTML",
        threaded=True,
        num_threads=max(4, cfg.worker_threads),
    )


_NETWORK_ERROR_HINTS = ("ssl", "connection", "timed out", "timeout", "resolve",
                         "proxyerror", "network", "unreachable")


def validate_bot(bot: telebot.TeleBot, attempts: int = 2) -> dict:
    """Authenticate the token, with one retry and a diagnosis that names the
    actual problem (bad token vs. no network) instead of a bare exception name."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            me = bot.get_me()
            return {"id": me.id, "username": me.username}
        except Exception as e:
            last_error = e
            text = str(e)
            unauthorized = "unauthorized" in text.lower() or "401" in text
            if unauthorized:
                log.error(
                    "Telegram rejected the BOT_TOKEN (Unauthorized). Copy the token again "
                    "from @BotFather (/mybots → API Token) or run: python main.py --reset"
                )
                raise SystemExit(2)
            if attempt < attempts:
                log.warning("Telegram API call failed (%s); retrying in 3s…", type(e).__name__)
                time.sleep(3)

    text = str(last_error)
    if any(hint in text.lower() for hint in _NETWORK_ERROR_HINTS):
        log.error(
            "Could not reach api.telegram.org (%s). Check the internet connection, "
            "firewall or proxy — the token was not verified.",
            type(last_error).__name__,
        )
    else:
        log.error("Could not authenticate with Telegram (check BOT_TOKEN): %s — %s",
                  type(last_error).__name__, text[:200])
    raise SystemExit(2)


def clear_webhook(bot: telebot.TeleBot) -> None:
    """Polling and a registered webhook are mutually exclusive: a leftover
    webhook makes long polling fail with 409 Conflict."""
    try:
        bot.remove_webhook()
        log.debug("webhook cleared (safe no-op when none was set)")
    except Exception:
        log.debug("remove_webhook failed (ignored)", exc_info=True)


def register_handlers(bot: telebot.TeleBot, cfg: config.Config) -> None:
    # Order = match priority for `message` updates.
    #   1. the claim handler (only active while the bot has no owner)
    #   2. owner commands / settings / approvals (pending-input catcher)
    #   3. feature menus (AI, FAQ, KB, tools)
    #   4. the business pipeline
    #   5. the catch-all fallback (last)
    security.register_claim_handler(bot)
    owner_commands.register(bot, cfg)
    settings_handler.register(bot, cfg)
    approvals.register(bot, cfg)
    ai_setup.register(bot, cfg)
    faq_handler.register(bot, cfg)
    owner_tools.register(bot, cfg)
    knowledge_base.register(bot, cfg)
    business_updates.register(bot, cfg)
    # Private messages addressed to the bot itself (no Telegram Business needed).
    direct_messages.register(bot, cfg)
    owner_commands.register_fallback(bot, cfg)


# (command, i18n key of its description) — published per language below.
BOT_COMMANDS = [
    ("start", "main.cmd.start"),
    ("setup", "main.cmd.setup"),
    ("mode", "main.cmd.mode"),
    ("direct", "main.cmd.direct"),
    ("ai", "main.cmd.ai"),
    ("freeai", "main.cmd.freeai"),
    ("aitest", "main.cmd.aitest"),
    ("faq", "main.cmd.faq"),
    ("kb", "main.cmd.kb"),
    ("status", "main.cmd.status"),
    ("health", "main.cmd.health"),
    ("settings", "main.cmd.settings"),
    ("language", "main.cmd.language"),
    ("chats", "main.cmd.chats"),
    ("stats", "main.cmd.stats"),
    ("instructions", "main.cmd.instructions"),
    ("help", "main.cmd.help"),
]


def set_bot_commands(bot: telebot.TeleBot) -> None:
    """Publish the command menu, translated per Telegram client language.

    Telegram picks the list matching the user's app language, so an Arabic user
    sees Arabic descriptions while an English user sees English ones.
    """
    default_lang = i18n.language()
    for language_code in (None, "ar", "en"):
        code = default_lang if language_code is None else language_code
        catalog = i18n.catalog(code)
        commands = [
            telebot.types.BotCommand(command, catalog.get(key, i18n.t(key)))
            for command, key in BOT_COMMANDS
        ]
        try:
            bot.set_my_commands(commands, language_code=language_code)
        except TypeError:
            # Older pyTelegramBotAPI without language_code: publish the default
            # list once and stop trying.
            if language_code is None:
                try:
                    bot.set_my_commands(commands)
                except Exception:
                    log.debug("set_my_commands failed", exc_info=True)
            break
        except Exception:
            log.debug("set_my_commands failed for %s", language_code or "default",
                      exc_info=True)
    try:
        bot.set_my_description(i18n.t("main.description"))
        bot.set_my_short_description(i18n.t("main.description_short"))
    except Exception:
        log.debug("set_my_description failed", exc_info=True)


# =============================================================================
# Polling
# =============================================================================
def start_polling(bot: telebot.TeleBot) -> None:
    log.info("Polling started. Allowed updates: %s", ", ".join(ALLOWED_UPDATES))
    while True:
        try:
            bot.infinity_polling(allowed_updates=ALLOWED_UPDATES,
                                 timeout=30, long_polling_timeout=30)
            break  # clean exit
        except KeyboardInterrupt:
            log.info("Interrupted; shutting down.")
            break
        except Exception as e:
            if "Conflict" in str(e) or "terminated by other" in str(e):
                log.error("Another instance of this bot is already polling (409 Conflict). "
                          "Stop the other instance — Telegram allows only one.")
            log.exception("Polling crashed; restarting in 5s.")
            time.sleep(5)


# =============================================================================
# Startup helpers
# =============================================================================
def seed_api_key(cfg: config.Config) -> None:
    """Mirror a key from .env into the encrypted at-rest store on first run."""
    key = cfg.ai_api_key or (cfg.openai_api_key if cfg.ai_provider == "openai" else "")
    provider_id = cfg.ai_provider if cfg.ai_api_key else "openai"
    if not key or database.get_api_key_row(provider_id):
        return
    try:
        ai_service.store_api_key(key, provider_id)
    except Exception:
        log.debug("could not seed api_keys table", exc_info=True)


def apply_env_ai_selection(cfg: config.Config) -> None:
    """Let .env values win on first run (the DB setting is the runtime source)."""
    try:
        has_rows = bool(database.list_business_connections()) or database.get_setting("ai_provider")
        current = database.get_str("ai_provider")
        if cfg.ai_provider and cfg.ai_provider != "openai" and current in ("", "openai"):
            database.set_setting("ai_provider", cfg.ai_provider)
        if cfg.ai_model and not ai_service.has_explicit_model(cfg.ai_provider):
            ai_service.set_model(cfg.ai_model, cfg.ai_provider)
        if cfg.ai_base_url and not database.get_str("ai_base_url").strip():
            database.set_setting("ai_base_url", cfg.ai_base_url)
        if cfg.model_backend == "codex" and current in ("", "openai"):
            database.set_setting("ai_provider", "codex")
        _ = has_rows
    except Exception:
        log.debug("could not apply .env AI selection", exc_info=True)


def _check_backend_ready(cfg: config.Config) -> None:
    provider = ai_service.active_provider()
    if provider.kind == "codex":
        from services import codex_service
        if not codex_service.is_available():
            log.warning("Provider is 'codex' but the Codex CLI was not found on PATH. "
                        "Install it (npm i -g @openai/codex) and run `codex login`, "
                        "or pick another provider from Telegram with /ai.")
        elif not codex_service.is_logged_in():
            log.warning("Codex CLI found but not logged in — run `codex login`.")
        return
    if not ai_service.is_ready():
        log.warning("No AI key configured for provider '%s'. Open the bot in Telegram "
                    "and use /ai to add one (or set AI_API_KEY in .env).",
                    ai_service.active_provider_id())
    if providers.needs_credit(provider.id):
        log.info("'%s' is a paid provider: its key only works while the account has "
                 "credit. Free alternatives (no card): /freeai in Telegram, or "
                 "AI_PROVIDER=google|groq|cerebras in .env.", provider.id)


def _notify_startup(bot: telebot.TeleBot, cfg: config.Config, me: dict,
                    interrupted_deliveries: int = 0, claim_code: str | None = None) -> None:
    owner = security.owner_id()
    if owner is None:
        return  # nothing to notify yet; the claim code is printed in the terminal
    try:
        from handlers import owner_tools
        text = i18n.t(
            "main.online",
            version=VERSION,
            username=utils.escape(me["username"]),
            mode=keyboards.mode_label(owner_tools.current_mode()),
            ai_state=i18n.t("own.ai.ready") if ai_service.is_ready()
            else i18n.t("own.ai.not_ready_short"),
            backend=utils.escape(ai_service.backend_label()),
            cost=utils.escape(ai_service.cost_label()),
        )
        text += i18n.t(
            "main.online.direct_hint",
            state=i18n.t("main.online.on") if database.get_bool("direct_reply_enabled")
            else i18n.t("main.online.off"),
        )
        text += i18n.t("main.online.setup_hint")
        if not ai_service.is_ready():
            text += i18n.t("main.online.freeai")
        if interrupted_deliveries:
            text += i18n.t("main.online.interrupted", count=interrupted_deliveries)
        bot.send_message(owner, text, parse_mode="HTML")
    except Exception:
        log.warning("Could not message the owner at startup "
                    "(send /start to the bot once, and verify OWNER_USER_ID).")


def _print_banner(cfg: config.Config, me: dict, claim_code: str | None) -> None:
    from handlers import owner_tools
    print("\n" + "=" * 64)
    print(f" Alfiqi Ai {VERSION} — Telegram Business AI assistant")
    print("=" * 64)
    print(f" Bot:          @{me['username']}")
    print(f" Owner ID:     {utils.mask_id(cfg.owner_user_id) if cfg.owner_user_id else '<claim from Telegram>'}")
    print(f" AI provider:  {ai_service.backend_label()}")
    print(f" Model:        {ai_service.active_model_label()}")
    print(f" Mode:         {owner_tools.current_mode()}")
    print(f" DB:           {cfg.db_path}")
    print("-" * 64)
    if claim_code:
        print(" OWNER CLAIM CODE (send this to your bot in Telegram):")
        print(f"     /start {claim_code}")
        print(" This code is shown only in this terminal. It changes on restart")
        print(" until the owner has been claimed.")
        print("-" * 64)
    print(f" Cost:         {ai_service.cost_label()}")
    print(" Next steps in Telegram:  /setup  →  /ai  →  /faq  →  /mode")
    if not ai_service.is_ready() or providers.needs_credit(ai_service.active_provider_id()):
        print(" No card / no credit?   /freeai lists the free AI providers")
    print(" Press Ctrl-C to stop.\n")


def run_check(cfg: config.Config) -> int:
    """--check: verify configuration and connectivity without polling."""
    print(f"Alfiqi Ai {VERSION} — configuration check\n")
    print(cfg.masked_summary())
    database.init_db(cfg)
    apply_env_ai_selection(cfg)
    provider = ai_service.active_provider()
    print(f"\nProvider:   {provider.label} ({provider.id}, kind={provider.kind})")
    print(f"Model:      {ai_service.active_model_label()}")
    print(f"Base URL:   {ai_service.active_base_url() or '<none>'}")
    print(f"Key:        {ai_service.masked_active_key()} (source: {ai_service.key_source()})")
    print(f"Ready:      {ai_service.is_ready()}")
    print(f"Cost:       {ai_service.cost_label(provider)}")
    print(f"Embeddings: {ai_service.supports_embeddings()}")
    result = ai_service.check_connection()
    print(f"Live test:  {'OK' if result.ok else 'FAILED'} — {result.message}")
    for hint in result.hints:
        print(f"            • {hint}")
    if result.suggestions:
        print("            Free alternatives: "
              + ", ".join(p.label for p in result.suggestions)
              + "  (or /freeai in Telegram)")
    return 0 if result.ok else 1


# =============================================================================
# Entry
# =============================================================================
def main(argv: list[str]) -> int:
    do_reset = "--reset" in argv
    debug_flag = "--debug" in argv
    do_check = "--check" in argv

    if do_reset:
        configure_logging(debug=debug_flag)
        config.run_reset_wizard()
        return 0

    cfg = config.load_or_run_wizard()
    configure_logging(debug=cfg.debug or debug_flag)

    # Defense-in-depth: never let secrets appear in logs.
    _redaction_filter.add_secret(cfg.bot_token)
    _redaction_filter.add_secret(cfg.ai_api_key)
    _redaction_filter.add_secret(cfg.openai_api_key)

    log.info("Starting Alfiqi Ai %s (token %s, owner %s)",
             VERSION, utils.mask_token(cfg.bot_token),
             utils.mask_id(cfg.owner_user_id) if cfg.owner_user_id else "<claim>")

    interrupted_deliveries = database.init_db(cfg)
    if interrupted_deliveries:
        log.warning("%s interrupted approval delivery claim(s) require manual review",
                    interrupted_deliveries)
    file_service.init(cfg.uploads_dir)
    telegram_api.init(cfg.bot_token)

    seed_api_key(cfg)
    apply_env_ai_selection(cfg)

    if do_check:
        return run_check(cfg)

    bot = build_bot(cfg)
    me = validate_bot(bot)
    log.info("Authenticated as @%s (id %s)", me["username"], utils.mask_id(me["id"]))
    try:
        bot.set_my_name("Alfiqi Ai")
    except Exception as e:
        log.warning("Could not set Telegram display name to Alfiqi Ai (%s); set it in @BotFather if needed.",
                    type(e).__name__)
    clear_webhook(bot)

    claim_code = None
    if not cfg.owner_user_id:
        if not cfg.allow_owner_claim:
            log.error("OWNER_USER_ID is not set and ALLOW_OWNER_CLAIM is false — "
                      "run `python main.py --reset` to configure an owner.")
            return 2
        claim_code = security.generate_claim_code()

    security.init(bot, cfg.owner_user_id or None, claim_code=claim_code)
    handlers.init(bot, cfg)
    register_handlers(bot, cfg)
    set_bot_commands(bot)
    _check_backend_ready(cfg)

    _notify_startup(bot, cfg, me, interrupted_deliveries, claim_code)
    _print_banner(cfg, me, claim_code)

    start_polling(bot)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)

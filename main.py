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
import security
import telegram_api
import utils
from handlers import (
    ai_setup,
    approvals,
    business_updates,
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


def validate_bot(bot: telebot.TeleBot) -> dict:
    try:
        me = bot.get_me()
        return {"id": me.id, "username": me.username}
    except Exception as e:
        log.error("Could not authenticate with Telegram (check BOT_TOKEN): %s", type(e).__name__)
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
    owner_commands.register_fallback(bot, cfg)


def set_bot_commands(bot: telebot.TeleBot) -> None:
    cmds = [
        ("start", "Control panel"),
        ("setup", "Guided setup checklist"),
        ("mode", "Auto-reply / draft / off"),
        ("ai", "AI provider, key, model"),
        ("aitest", "Test the AI connection"),
        ("faq", "Quick answers (canned replies)"),
        ("kb", "Knowledge base menu"),
        ("status", "Bot, AI & connection status"),
        ("health", "Run system checks"),
        ("settings", "All settings"),
        ("chats", "Recent customer chats"),
        ("stats", "Statistics"),
        ("instructions", "Standing instructions (tone/language)"),
        ("help", "Usage guide"),
    ]
    try:
        bot.set_my_commands([telebot.types.BotCommand(c, d) for c, d in cmds])
    except Exception:
        log.debug("set_my_commands failed", exc_info=True)


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


def _notify_startup(bot: telebot.TeleBot, cfg: config.Config, me: dict,
                    interrupted_deliveries: int = 0, claim_code: str | None = None) -> None:
    owner = security.owner_id()
    if owner is None:
        return  # nothing to notify yet; the claim code is printed in the terminal
    try:
        from handlers import owner_tools
        text = (
            f"✅ <b>SmarTel {VERSION} is online</b> as @{utils.escape(me['username'])}.\n"
            f"Mode: <b>{owner_tools.current_mode()}</b>\n"
            f"AI: <b>{'ready' if ai_service.is_ready() else 'not configured — open /ai'}</b> "
            f"({utils.escape(ai_service.backend_label())})\n\n"
            "First time? Run /setup for the checklist "
            "(BotFather Business Mode + Telegram Business → Chatbots)."
        )
        if interrupted_deliveries:
            text += (
                "\n\n⚠️ <b>Manual review required:</b> "
                f"{interrupted_deliveries} approval delivery attempt(s) were interrupted. "
                "Check the customer chat before sending another reply."
            )
        bot.send_message(owner, text, parse_mode="HTML")
    except Exception:
        log.warning("Could not message the owner at startup "
                    "(send /start to the bot once, and verify OWNER_USER_ID).")


def _print_banner(cfg: config.Config, me: dict, claim_code: str | None) -> None:
    from handlers import owner_tools
    print("\n" + "=" * 64)
    print(f" SmarTel {VERSION} — Telegram Business AI assistant")
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
    print(" Next steps in Telegram:  /setup  →  /ai  →  /faq  →  /mode")
    print(" Press Ctrl-C to stop.\n")


def run_check(cfg: config.Config) -> int:
    """--check: verify configuration and connectivity without polling."""
    print(f"SmarTel {VERSION} — configuration check\n")
    print(cfg.masked_summary())
    database.init_db(cfg)
    apply_env_ai_selection(cfg)
    provider = ai_service.active_provider()
    print(f"\nProvider:   {provider.label} ({provider.id}, kind={provider.kind})")
    print(f"Model:      {ai_service.active_model_label()}")
    print(f"Base URL:   {ai_service.active_base_url() or '<none>'}")
    print(f"Key:        {ai_service.masked_active_key()} (source: {ai_service.key_source()})")
    print(f"Ready:      {ai_service.is_ready()}")
    print(f"Embeddings: {ai_service.supports_embeddings()}")
    ok, message = ai_service.test_connection()
    print(f"Live test:  {'OK' if ok else 'FAILED'} — {message}")
    return 0 if ok else 1


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

    log.info("Starting SmarTel %s (token %s, owner %s)",
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

"""Configuration: .env schema, the Config dataclass, validation, and the
first-launch terminal wizard.

Two-tier model:
  * Bootstrap secrets/identity (BOT_TOKEN, OWNER_USER_ID, OPENAI_API_KEY, ...)
    live in ``.env`` only and are changed via the terminal (wizard / --reset).
  * Behavioral settings (auto-reply, approval mode, model, temperature, ...)
    live in the SQLite ``settings`` table and are changed at runtime from inside
    Telegram. The DEFAULT_* values here only SEED that table on first run.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Token format: <digits>:<35+ url-safe chars>. Loose but catches obvious typos.
_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}
_BOOL_FALSE = {"0", "false", "no", "off", "n", ""}


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    return default


def _resolve_path(value: str, fallback: str) -> Path:
    raw = (value or fallback).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_user_id: int
    openai_api_key: str
    openai_base_url: str
    model_backend: str          # "openai" | "codex"
    codex_model: str            # optional model override for the Codex backend
    fernet_key: str
    default_model: str
    default_auto_reply: bool
    default_approval_mode: bool
    db_path: Path
    uploads_dir: Path
    vector_store_dir: Path
    worker_threads: int
    debug: bool
    # --- provider-agnostic AI layer (services/ai_service.py) ------------------
    ai_provider: str = "openai"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""
    # When OWNER_USER_ID is not set, allow claiming ownership from Telegram
    # with the code printed in the terminal (see security.py).
    allow_owner_claim: bool = True

    @staticmethod
    def from_env() -> "Config":
        return Config(
            bot_token=(os.environ.get("BOT_TOKEN") or "").strip(),
            owner_user_id=_to_int(os.environ.get("OWNER_USER_ID")),
            openai_api_key=(os.environ.get("OPENAI_API_KEY") or "").strip(),
            openai_base_url=(os.environ.get("OPENAI_BASE_URL") or "").strip(),
            model_backend=((os.environ.get("MODEL_BACKEND") or "openai").strip().lower() or "openai"),
            codex_model=(os.environ.get("CODEX_MODEL") or "").strip(),
            fernet_key=(os.environ.get("SMARTEL_FERNET_KEY") or "").strip(),
            default_model=(os.environ.get("DEFAULT_MODEL") or "gpt-4.1-mini").strip(),
            default_auto_reply=_parse_bool(os.environ.get("DEFAULT_AUTO_REPLY"), False),
            default_approval_mode=_parse_bool(os.environ.get("DEFAULT_APPROVAL_MODE"), True),
            db_path=_resolve_path(os.environ.get("DB_PATH", ""), "storage/smartel.db"),
            uploads_dir=_resolve_path(os.environ.get("UPLOADS_DIR", ""), "storage/uploads"),
            vector_store_dir=_resolve_path(os.environ.get("VECTOR_STORE_DIR", ""), "storage/vector_store"),
            worker_threads=max(1, _to_int(os.environ.get("WORKER_THREADS"), 4)),
            debug=_parse_bool(os.environ.get("DEBUG"), False),
            ai_provider=_resolve_provider(),
            ai_api_key=(os.environ.get("AI_API_KEY") or "").strip(),
            ai_model=(os.environ.get("AI_MODEL") or "").strip(),
            ai_base_url=(os.environ.get("AI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "").strip(),
            allow_owner_claim=_parse_bool(os.environ.get("ALLOW_OWNER_CLAIM"), True),
        )

    def validate(self) -> None:
        if not self.bot_token:
            raise ConfigError("BOT_TOKEN is missing. Get it from @BotFather.")
        if not _TOKEN_RE.match(self.bot_token):
            raise ConfigError(
                "BOT_TOKEN does not look like a valid token "
                "(expected '123456789:AA...'). Check it in @BotFather."
            )
        if self.owner_user_id <= 0 and not self.allow_owner_claim:
            raise ConfigError(
                "OWNER_USER_ID is missing or invalid. It must be your positive "
                "numeric Telegram user ID (get it from @userinfobot), or set "
                "ALLOW_OWNER_CLAIM=true to claim ownership from Telegram with the "
                "code printed at startup."
            )
        # OpenAI key is NOT required to boot — the bot can run and report a clear
        # error / let the owner connect a key later via /connect_openai.

    def masked_summary(self) -> str:
        from utils import mask_id, mask_key, mask_token
        return (
            f"  Bot token:        {mask_token(self.bot_token)}\n"
            f"  Owner user ID:    {mask_id(self.owner_user_id) if self.owner_user_id else '<claim from Telegram>'}\n"
            f"  AI provider:      {self.ai_provider}\n"
            f"  AI key:           {mask_key(self.ai_api_key) if self.ai_api_key else '<not set>'}\n"
            f"  AI model:         {self.ai_model or '<provider default>'}\n"
            f"  AI base URL:      {self.ai_base_url or '<provider default>'}\n"
            f"  Legacy backend:   {self.model_backend}\n"
            f"  OpenAI key:       {mask_key(self.openai_api_key) if self.openai_api_key else '<not set>'}\n"
            f"  OpenAI base URL:  {self.openai_base_url or '<default OpenAI>'}\n"
            f"  Codex model:      {self.codex_model or '<Codex default>'}\n"
            f"  Fernet key:       {'set' if self.fernet_key else '<not set>'}\n"
            f"  Default model:    {self.default_model}\n"
            f"  Auto-reply:       {self.default_auto_reply}\n"
            f"  Approval mode:    {self.default_approval_mode}\n"
            f"  DB path:          {self.db_path}\n"
            f"  Debug:            {self.debug}"
        )


def _resolve_provider() -> str:
    """Which AI provider to use, honouring the legacy OPENAI_*/MODEL_BACKEND keys."""
    explicit = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit
    if (os.environ.get("MODEL_BACKEND") or "").strip().lower() == "codex":
        return "codex"
    if (os.environ.get("OPENAI_BASE_URL") or "").strip():
        return "custom"
    if (os.environ.get("AI_BASE_URL") or "").strip():
        return "custom"
    return "openai"


def _to_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# =============================================================================
# .env loading / writing
# =============================================================================
def env_exists() -> bool:
    return ENV_PATH.exists()


def load_env() -> None:
    """Load .env into os.environ (does not override already-set vars by default)."""
    load_dotenv(ENV_PATH, override=True)


def _env_values_from_config(cfg: Config) -> dict[str, str]:
    return {
        "BOT_TOKEN": cfg.bot_token,
        "OWNER_USER_ID": str(cfg.owner_user_id or ""),
        "ALLOW_OWNER_CLAIM": "true" if cfg.allow_owner_claim else "false",
        "AI_PROVIDER": cfg.ai_provider,
        "AI_API_KEY": cfg.ai_api_key,
        "AI_MODEL": cfg.ai_model,
        "AI_BASE_URL": cfg.ai_base_url,
        # Legacy keys kept in sync so older code/docs keep working.
        "OPENAI_API_KEY": cfg.openai_api_key or (cfg.ai_api_key if cfg.ai_provider == "openai" else ""),
        "OPENAI_BASE_URL": cfg.openai_base_url,
        "MODEL_BACKEND": cfg.model_backend,
        "CODEX_MODEL": cfg.codex_model,
        "SMARTEL_FERNET_KEY": cfg.fernet_key,
        "DEFAULT_MODEL": cfg.default_model,
        "DEFAULT_AUTO_REPLY": "true" if cfg.default_auto_reply else "false",
        "DEFAULT_APPROVAL_MODE": "true" if cfg.default_approval_mode else "false",
        "DB_PATH": os.environ.get("DB_PATH", "storage/smartel.db"),
        "UPLOADS_DIR": os.environ.get("UPLOADS_DIR", "storage/uploads"),
        "VECTOR_STORE_DIR": os.environ.get("VECTOR_STORE_DIR", "storage/vector_store"),
        "WORKER_THREADS": str(cfg.worker_threads),
        "DEBUG": "true" if cfg.debug else "false",
    }


def write_env(cfg: Config) -> None:
    """Atomically write the .env file from a Config (tempfile + os.replace)."""
    values = _env_values_from_config(cfg)
    lines = [
        "# SmarTel configuration (managed by main.py wizard / --reset).",
        "# Do not commit this file. Secrets are stored here.",
        "",
    ]
    for key, val in values.items():
        lines.append(f"{key}={val}")
    content = "\n".join(lines) + "\n"

    fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, ENV_PATH)
        try:
            os.chmod(ENV_PATH, 0o600)  # best-effort: restrict to owner
        except OSError:
            pass
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# =============================================================================
# Terminal prompts (wizard)
# =============================================================================
def _prompt_text(label: str, default: str | None = None, secret: bool = False,
                 required: bool = True, validator=None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        prompt = f"{label}{suffix}: "
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if not value and default is not None:
            value = default
        if not value and not required:
            return ""
        if not value:
            print("  ! This value is required.")
            continue
        if validator:
            ok, msg = validator(value)
            if not ok:
                print(f"  ! {msg}")
                continue
        return value


def _prompt_bool(label: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"{label} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in _BOOL_TRUE:
            return True
        if value in _BOOL_FALSE:
            return False
        print("  ! Please answer y or n.")


def _validate_token(value: str):
    if _TOKEN_RE.match(value):
        return True, ""
    return False, "Token must look like '123456789:AA...' (from @BotFather)."


def _validate_owner_id(value: str):
    if not value:
        return True, ""  # claim from Telegram later
    try:
        if int(value) > 0:
            return True, ""
    except ValueError:
        pass
    return False, ("Owner ID must be a positive number (from @userinfobot) — "
                   "or press Enter to claim ownership from Telegram with a code.")


def _setup_codex_backend() -> None:
    """Guide the owner through Codex CLI install/login for the ChatGPT-subscription
    backend. Best-effort: never aborts the wizard if Codex isn't ready yet."""
    from services import codex_service

    # Install the Codex CLI if it isn't already present.
    if not codex_service.is_available():
        print("\n   Codex CLI not found on PATH.")
        if _prompt_bool("   Install it now (npm i -g @openai/codex, or Homebrew)?", default=True):
            codex_service.install()
        if not codex_service.is_available():
            print("   ! Codex still isn't available. Install it manually, then run "
                  "`codex login`.")
            print("     The bot will warn at startup until Codex is ready.")
            return  # continue the wizard; backend stays configured as codex

    # Codex is available — handle login.
    if codex_service.is_logged_in():
        print("   ✓ Codex CLI ready and appears logged in.")
        if not _prompt_bool("   Re-run `codex login` anyway?", default=False):
            return
    else:
        print("   ✓ Codex CLI ready (not logged in yet).")

    if _prompt_bool("   Run `codex login` now (choose 'Sign in with ChatGPT')?", default=True):
        device = _prompt_bool("   Use device-code login (for headless/remote machines)?", default=False)
        ok = codex_service.login(device_auth=device)
        print("   ✓ Codex login completed." if ok else
              "   ! Codex login did not complete; run `codex login` manually later.")


def _maybe_generate_fernet_key() -> str:
    """Generate a Fernet key if the cryptography lib is available (enables
    encrypted at-rest storage of the API key out of the box)."""
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except Exception:
        return ""


def _choose_provider() -> tuple[str, str, str, str, str, str]:
    """Interactive provider picker.

    Returns ``(provider_id, api_key, model, base_url, model_backend, codex_model)``.
    """
    from services import providers as _providers

    ordered = _providers.ordered()
    print("\n3) AI provider — who should generate the replies?")
    for index, provider in enumerate(ordered, start=1):
        flags = []
        if provider.free_tier:
            flags.append("free tier")
        if provider.local:
            flags.append("runs on this machine")
        suffix = f"  ({', '.join(flags)})" if flags else ""
        print(f"     {index:2d}) {provider.label}{suffix}")
    print("      0) Configure later from Telegram with /ai  (recommended)")
    raw = input(f"   Select [0-{len(ordered)}] (default 0): ").strip() or "0"

    if raw == "0":
        return ("openai", "", "", "", "", "")

    try:
        provider = ordered[int(raw) - 1]
    except (ValueError, IndexError):
        print("   ! Unrecognised choice — you can configure it later with /ai.")
        return ("openai", "", "", "", "", "")

    api_key = ""
    base_url = ""
    model = provider.default_model
    codex_model = ""

    if provider.kind == "codex":
        _setup_codex_backend()
        codex_model = _prompt_text("   Codex model (blank = Codex default)", required=False)
        model = codex_model
        return ("codex", "", model, "", "codex", codex_model)

    if provider.id == "custom":
        base_url = _prompt_text("   Base URL (e.g. http://localhost:1234/v1)")
        model = _prompt_text("   Model name")
    # Self-hosted endpoints (OmniRoute, Ollama, LM Studio) come with a working
    # default; tell the owner how to move them instead of prompting for it.
    for env_name in _providers.base_url_env_names(provider.id):
        print(f"   Endpoint: {provider.base_url}  "
              f"(override with {env_name} in .env if it runs elsewhere)")
    if provider.key_required:
        hint = f" (get one at {provider.key_url})" if provider.key_url else ""
        print(f"   {provider.label}: API key{hint}")
        api_key = _prompt_text("   API key (blank = add it later in Telegram)",
                               secret=True, required=False)
    if provider.models and provider.id != "custom":
        model = _prompt_text("   Model", default=provider.default_model)
    model_backend = "codex" if provider.kind == "codex" else "openai"
    return (provider.id, api_key, model, base_url, model_backend, codex_model)


def run_wizard() -> Config:
    print("\n" + "=" * 60)
    print(" SmarTel — first-launch configuration")
    print("=" * 60)
    print("This sets up your .env file. Press Ctrl-C to abort.\n")

    bot_token = _prompt_text("1) Telegram bot token (from @BotFather)",
                             secret=True, validator=_validate_token)
    owner_raw = _prompt_text(
        "2) Owner Telegram user ID (from @userinfobot); press Enter to claim it "
        "from Telegram with a code", required=False, validator=_validate_owner_id)
    owner_user_id = int(owner_raw) if owner_raw else 0

    provider_id, ai_api_key, ai_model, ai_base_url, model_backend, codex_model = _choose_provider()
    openai_api_key = ai_api_key if provider_id == "openai" else ""
    openai_base_url = ai_base_url if provider_id in ("custom", "ollama", "lmstudio") else ""
    default_model = ai_model or "gpt-4.1-mini"

    default_auto_reply = _prompt_bool("4) Enable automatic replies by default?", default=False)
    default_approval_mode = _prompt_bool("5) Require approval before sending by default?",
                                         default=True)

    # Preserve an existing Fernet key if present, else generate one when possible.
    fernet_key = (os.environ.get("SMARTEL_FERNET_KEY") or "").strip() or _maybe_generate_fernet_key()

    cfg = Config(
        bot_token=bot_token,
        owner_user_id=owner_user_id,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        model_backend=model_backend,
        codex_model=codex_model,
        fernet_key=fernet_key,
        default_model=default_model,
        default_auto_reply=default_auto_reply,
        default_approval_mode=default_approval_mode,
        db_path=_resolve_path(os.environ.get("DB_PATH", ""), "storage/smartel.db"),
        uploads_dir=_resolve_path(os.environ.get("UPLOADS_DIR", ""), "storage/uploads"),
        vector_store_dir=_resolve_path(os.environ.get("VECTOR_STORE_DIR", ""), "storage/vector_store"),
        worker_threads=max(1, _to_int(os.environ.get("WORKER_THREADS"), 4)),
        debug=_parse_bool(os.environ.get("DEBUG"), False),
        ai_provider=provider_id,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
        ai_base_url=ai_base_url,
        allow_owner_claim=True,
    )
    cfg.validate()
    write_env(cfg)
    if not owner_user_id:
        print("\nOwner: not set — start the bot and claim it from Telegram with the\n"
              "code printed in the terminal (send /start <code> to your bot).")
    # Make the freshly written values visible to the rest of the process.
    load_env()
    print(f"\nConfiguration saved to {ENV_PATH}\n")
    return cfg


#: Printed when there is no .env and no interactive terminal to ask questions in.
NO_TERMINAL_HELP = (
    "\nNo .env file was found and no terminal is available to ask questions.\n"
    "Create one from the template and fill it in:\n"
    "    cp .env.example .env      (Windows: copy .env.example .env)\n"
    "then set BOT_TOKEN (from @BotFather). AI keys can also be added later\n"
    "from inside Telegram with /ai.\n"
)


def _load_config_gracefully() -> Config:
    """Run the wizard, but fail with advice instead of a traceback when there is
    no interactive stdin (docker, systemd, cron, `python main.py < /dev/null`)."""
    try:
        return run_wizard()
    # EOFError: stdin closed (docker/systemd/systemd). OSError: stdin exists but
    # is not readable (piped-closed, pytest capture). Both mean "no terminal".
    except (EOFError, OSError, KeyboardInterrupt):
        print("\n" + NO_TERMINAL_HELP)
        sys.exit(2)


def load_or_run_wizard() -> Config:
    """Load config from .env if present & valid, else run the first-launch wizard.

    Hosted platforms (Railway, Render, Fly, Docker `-e`, …) inject configuration
    as real environment variables and usually have no .env file. If BOT_TOKEN is
    already in the environment, use it directly instead of trying to open an
    interactive wizard that can never be answered there.
    """
    if not env_exists() and (os.environ.get("BOT_TOKEN") or "").strip():
        cfg = Config.from_env()
        try:
            cfg.validate()
        except ConfigError as e:
            print(f"\nInvalid configuration in environment variables: {e}")
            sys.exit(2)
        return cfg

    if env_exists():
        load_env()
        cfg = Config.from_env()
        try:
            cfg.validate()
            return cfg
        except ConfigError as e:
            print(f"\nExisting .env is invalid: {e}")
            try:
                rerun = _prompt_bool("Re-run the configuration wizard?", default=True)
            except (EOFError, OSError, KeyboardInterrupt):
                print("\n" + NO_TERMINAL_HELP)
                sys.exit(2)
            if rerun:
                return _load_config_gracefully()
            sys.exit(2)
    else:
        return _load_config_gracefully()


# =============================================================================
# Reset (terminal-only)
# =============================================================================
def run_reset_wizard() -> None:
    """Interactive configuration reset. Never invoked from Telegram."""
    if not sys.stdin or not sys.stdin.isatty():
        print(NO_TERMINAL_HELP)
        return
    print("\n" + "=" * 60)
    print(" SmarTel — configuration reset")
    print("=" * 60)

    if env_exists():
        load_env()
        try:
            current = Config.from_env()
            print("\nCurrent configuration:")
            print(current.masked_summary())
        except Exception:
            print("\n(Existing .env could not be parsed.)")
    else:
        print("\nNo .env found yet.")

    print("\nOptions:")
    print("  1) Re-run the full wizard (overwrite all settings)")
    print("  2) Wipe runtime DB state (settings -> defaults, clear pauses & pending approvals)")
    print("  3) Cancel")
    choice = input("Select [1/2/3]: ").strip()

    if choice == "1":
        if env_exists():
            _backup_env()
        run_wizard()
        print("Done. Restart the bot with `python main.py`.")
    elif choice == "2":
        if not env_exists():
            print("No .env found; nothing to load. Run option 1 first.")
            return
        if not _prompt_bool("This clears settings, pauses and pending approvals. Continue?", default=False):
            print("Cancelled.")
            return
        load_env()
        cfg = Config.from_env()
        import database
        database.init_db(cfg)
        database.reset_runtime_state()
        print("Runtime DB state reset to defaults.")
    else:
        print("Cancelled.")


def _backup_env() -> None:
    from utils import now_ts
    backup = BASE_DIR / f".env.bak.{now_ts()}"
    try:
        backup.write_text(ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backed up existing .env to {backup.name}")
    except OSError as e:
        print(f"! Could not back up .env: {e}. Aborting reset to avoid data loss.")
        raise SystemExit(2)

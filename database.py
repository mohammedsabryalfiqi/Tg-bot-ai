"""SQLite persistence: thread-safe connection management, schema creation, a
typed settings layer with coercion, and the data-access layer (DAL).

Threading: pyTelegramBotAPI dispatches updates on worker threads, so we use one
connection per thread (``threading.local``) with WAL mode, plus a module-level
write lock that serializes write transactions. Reads are lock-free (WAL lets
readers proceed alongside the single writer).
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Iterator

import utils

log = logging.getLogger("smartel.db")

_local = threading.local()
_WRITE_LOCK = threading.Lock()
_DB_PATH: Path | None = None
_SEED_DEFAULTS: dict[str, object] = {}
_ACTIVE_TENANT = contextvars.ContextVar("active_tenant", default=0)


def tenant_id() -> int:
    return int(_ACTIVE_TENANT.get() or 0)


@contextlib.contextmanager
def tenant_scope(value: int | None):
    token = _ACTIVE_TENANT.set(int(value or 0))
    try:
        yield
    finally:
        _ACTIVE_TENANT.reset(token)


def _setting_key(key: str) -> str:
    tenant = tenant_id()
    return f"tenant:{tenant}:{key}" if tenant else key


# =============================================================================
# Settings schema: key -> (python type, default value)
# =============================================================================
SETTINGS_SCHEMA: dict[str, tuple[type, object]] = {
    "openai_model": (str, "gpt-4.1-mini"),   # legacy key, still read for provider=openai
    "temperature": (float, 0.4),
    "max_tokens": (int, 800),
    "auto_reply_enabled": (bool, False),
    "approval_mode_enabled": (bool, True),
    "kb_enabled": (bool, True),
    "strict_kb_mode": (bool, False),
    "memory_enabled": (bool, True),
    "owner_takeover_pause_minutes": (int, 30),
    "sensitive_requires_approval": (bool, True),
    "monitoring_mode": (bool, True),
    "max_messages_per_customer_per_hour": (int, 20),
    "public_direct_bot_chat_enabled": (bool, False),
    # Answer the private messages people send to the BOT's own chat (no Telegram
    # Business account needed). Gated by the same auto_reply/approval switches.
    "direct_reply_enabled": (bool, True),
    # Interface language of the bot itself: ar (default) | en. See i18n.py.
    "ui_language": (str, "ar"),
    # Internal extra (not in the original spec list): allow processing of
    # non-text business messages. Off by default per spec ("text by default").
    "process_nontext_enabled": (bool, False),
    # Free-text instruction always added to the AI system prompt (language, tone,
    # persona). Empty by default. Set via /instructions.
    "custom_instructions": (str, ""),
    "reply_priorities": (str, ""),
    "never_reply_rules": (str, ""),

    # --- AI provider layer (see services/ai_service.py) -----------------------
    # Which provider generates replies: openai | anthropic | google | groq |
    # openrouter | deepseek | mistral | xai | together | ollama | lmstudio |
    # custom | codex. Keys live (encrypted) in the api_keys table.
    "ai_provider": (str, "openai"),
    "ai_base_url": (str, ""),                # only for custom/local endpoints
    "ai_model_by_provider": (str, "{}"),     # JSON: {provider_id: model_name}
    "ai_validation_message": (str, "ping"),  # probe text used by "Test connection"

    # --- Persona / business profile (injected into the system prompt) ---------
    "assistant_name": (str, ""),             # how the assistant refers to itself
    "business_name": (str, ""),
    "business_description": (str, ""),
    "reply_language": (str, "auto"),         # auto | ar | en | fr | es | de | tr | fa | ur | ru | id | hi
    "tone": (str, "friendly"),               # friendly | professional | casual | concise | warm
    "signature": (str, ""),                  # appended verbatim to every reply
    "max_reply_chars": (int, 900),
    "disclose_ai": (bool, False),            # may volunteer that it is an AI

    # --- FAQ / canned answers (services/faq_service.py) -----------------------
    "faq_enabled": (bool, True),
    "faq_direct_reply": (bool, True),        # exact match -> send the canned answer as-is
    "faq_match_threshold": (int, 60),        # 1-100: minimum score for a fuzzy match

    # --- Message handling -----------------------------------------------------
    "reply_debounce_seconds": (float, 1.0),  # batch rapid-fire messages from one customer
    "typing_indicator": (bool, True),        # keep "typing…" alive while generating
    "greet_new_customers": (bool, False),    # send welcome_text on a customer's first message
    "welcome_text": (str, ""),
    # Optional canned acknowledgement for non-text messages (photo, voice, …).
    # Empty (default) = only notify the owner, never answer automatically.
    "nontext_ack_message": (str, ""),

    # --- Topic rules (what the assistant must know and do) --------------------
    # Natural-language instructions typed by the owner are turned into small,
    # reviewable "topic rules" that are injected into every system prompt.
    "rules_enabled": (bool, True),
    # --- Resources the assistant may search / point people to -----------------
    "resources_enabled": (bool, True),
    # --- Unanswered questions (the assistant learns from what it missed) ------
    "unanswered_enabled": (bool, True),
    # --- Entry gates (admin toggles; both OFF by default) ---------------------
    # Join-check: everyone must be a member of the required channels first.
    "require_subscription_enabled": (bool, False),
    # Telegram Stars: one paid message unlocks one answer (+ owner copy).
    "paid_messages_enabled": (bool, False),
    "paid_message_stars": (int, 0),         # 0 = not priced yet -> gate stays shut
    "paid_message_free_count": (int, 0),    # free messages per user before paying
    "gate_copy_to_owner": (bool, True),     # send the owner a copy of gated chats

    # --- Owner identity (claim flow when OWNER_USER_ID is not set) -------------
    "claimed_owner_user_id": (int, 0),
}

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off", ""}


# =============================================================================
# Connection management
# =============================================================================
def init_db(cfg) -> int:
    """Initialise storage and quarantine delivery claims from an earlier process.

    Returns the number of interrupted approval deliveries that require manual
    review.
    """
    global _DB_PATH, _SEED_DEFAULTS
    # Drop handles from a previous init (unit tests may re-init the same path).
    for old in getattr(_local, "connections", {}).values():
        try:
            old.close()
        except Exception:
            pass
    _local.connections = {}
    if hasattr(_local, "conn"):
        del _local.conn
    _DB_PATH = Path(cfg.db_path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.uploads_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.vector_store_dir).mkdir(parents=True, exist_ok=True)

    # Behavioral defaults seeded from .env DEFAULT_* (only the three the wizard asks for).
    _SEED_DEFAULTS = {k: v for k, (_t, v) in SETTINGS_SCHEMA.items()}
    _SEED_DEFAULTS["openai_model"] = cfg.default_model
    _SEED_DEFAULTS["auto_reply_enabled"] = cfg.default_auto_reply
    _SEED_DEFAULTS["approval_mode_enabled"] = cfg.default_approval_mode

    _create_schema()
    seed_default_settings()
    interrupted_deliveries = mark_interrupted_approval_deliveries_uncertain()
    log.info("database initialised at %s", _DB_PATH)
    return interrupted_deliveries


def _get_conn() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("Database not initialised. Call init_db(cfg) first.")
    tenant = tenant_id()
    path = _DB_PATH if tenant == 0 else _DB_PATH.with_name(
        f"{_DB_PATH.stem}.tenant-{tenant}{_DB_PATH.suffix or '.sqlite3'}")
    connections = getattr(_local, "connections", None)
    if connections is None:
        connections = {}
        _local.connections = connections
    key = str(path)
    conn = connections.get(key)
    if conn is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=5.0, check_same_thread=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        connections[key] = conn
        if tenant == 0:
            _local.conn = conn  # compatibility with existing tests/diagnostics
        else:
            _create_schema()
            seed_default_settings()
    return conn


@contextlib.contextmanager
def read_cursor() -> Iterator[sqlite3.Cursor]:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()


@contextlib.contextmanager
def write_tx() -> Iterator[sqlite3.Cursor]:
    conn = _get_conn()
    with _WRITE_LOCK:
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def _create_schema() -> None:
    with write_tx() as cur:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS assistant_admins (
                user_id INTEGER PRIMARY KEY,
                added_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS business_connections (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT UNIQUE NOT NULL,
                business_user_id       INTEGER,
                is_enabled             INTEGER DEFAULT 1,
                can_reply              INTEGER DEFAULT 1,
                created_at             TEXT,
                updated_at             TEXT
            );

            CREATE TABLE IF NOT EXISTS customers (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                first_name             TEXT,
                last_name              TEXT,
                username               TEXT,
                created_at             TEXT,
                updated_at             TEXT,
                UNIQUE(business_connection_id, customer_chat_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                telegram_message_id    INTEGER,
                direction              TEXT,
                role                   TEXT,
                content                TEXT,
                created_at             TEXT
            );

            CREATE TABLE IF NOT EXISTS conversation_memory (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                role                   TEXT,
                content                TEXT,
                created_at             TEXT
            );

            CREATE TABLE IF NOT EXISTS paused_chats (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                reason                 TEXT,
                paused_until           TEXT,
                created_at             TEXT,
                UNIQUE(business_connection_id, customer_chat_id)
            );

            CREATE TABLE IF NOT EXISTS pending_approvals (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                customer_message_id    INTEGER,
                customer_message_text  TEXT,
                ai_reply_text          TEXT,
                status                 TEXT DEFAULT 'pending',
                created_at             TEXT,
                decided_at             TEXT
            );

            CREATE TABLE IF NOT EXISTS kb_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id   INTEGER NOT NULL DEFAULT 0,
                title       TEXT,
                source_type TEXT,
                filename    TEXT,
                created_at  TEXT,
                chunk_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS kb_chunks (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id        INTEGER,
                chunk_index    INTEGER,
                content        TEXT,
                embedding_json TEXT,
                created_at     TEXT,
                FOREIGN KEY(item_id) REFERENCES kb_items(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                provider                        TEXT UNIQUE,
                masked_key                      TEXT,
                encrypted_key_or_plain_local_key TEXT,
                created_at                      TEXT,
                updated_at                      TEXT
            );

            CREATE TABLE IF NOT EXISTS owner_pending_input (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER UNIQUE,
                kind          TEXT,
                context_json  TEXT,
                created_at    TEXT,
                expires_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS faq_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id   INTEGER NOT NULL DEFAULT 0,
                keywords    TEXT NOT NULL DEFAULT '',
                question    TEXT,
                answer      TEXT NOT NULL DEFAULT '',
                enabled     INTEGER DEFAULT 1,
                hits        INTEGER DEFAULT 0,
                last_hit_at TEXT,
                created_at  TEXT,
                updated_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS topic_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id   INTEGER NOT NULL DEFAULT 0,
                topic       TEXT NOT NULL DEFAULT '',
                rule        TEXT NOT NULL DEFAULT '',
                priority    INTEGER NOT NULL DEFAULT 100,
                enabled     INTEGER NOT NULL DEFAULT 0,
                source      TEXT NOT NULL DEFAULT 'owner',
                batch       TEXT NOT NULL DEFAULT '',
                hits        INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT,
                updated_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS unanswered_questions (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id              INTEGER NOT NULL DEFAULT 0,
                business_connection_id TEXT,
                customer_chat_id       INTEGER,
                question               TEXT NOT NULL DEFAULT '',
                answer                 TEXT,
                status                 TEXT NOT NULL DEFAULT 'open',
                created_at             TEXT,
                answered_at            TEXT
            );

            CREATE TABLE IF NOT EXISTS resources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id   INTEGER NOT NULL DEFAULT 0,
                kind        TEXT NOT NULL DEFAULT 'link',
                title       TEXT NOT NULL DEFAULT '',
                url         TEXT NOT NULL DEFAULT '',
                notes       TEXT NOT NULL DEFAULT '',
                enabled     INTEGER NOT NULL DEFAULT 1,
                chars       INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS required_channels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id   INTEGER NOT NULL DEFAULT 0,
                chat_ref    TEXT NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                invite_link TEXT NOT NULL DEFAULT '',
                kind        TEXT NOT NULL DEFAULT 'channel',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS gate_checks (
                customer_chat_id INTEGER PRIMARY KEY,
                all_ok           INTEGER NOT NULL DEFAULT 0,
                checked_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS paid_messages (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id         INTEGER NOT NULL DEFAULT 0,
                customer_chat_id  INTEGER NOT NULL,
                user_id           INTEGER,
                payload           TEXT NOT NULL DEFAULT '',
                charge_id         TEXT NOT NULL DEFAULT '',
                stars             INTEGER NOT NULL DEFAULT 0,
                message_text      TEXT NOT NULL DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'pending',
                delivered         INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT,
                paid_at           TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_bc_chat_time
                ON messages(business_connection_id, customer_chat_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_memory_bc_chat_time
                ON conversation_memory(business_connection_id, customer_chat_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_paused_bc_chat
                ON paused_chats(business_connection_id, customer_chat_id);
            CREATE INDEX IF NOT EXISTS idx_pending_status
                ON pending_approvals(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_kb_chunks_item
                ON kb_chunks(item_id);
            CREATE INDEX IF NOT EXISTS idx_customers_bc_chat
                ON customers(business_connection_id, customer_chat_id);
            CREATE INDEX IF NOT EXISTS idx_faq_enabled
                ON faq_entries(enabled, id);
            CREATE INDEX IF NOT EXISTS idx_topic_rules_lookup
                ON topic_rules(tenant_id, enabled, priority);
            CREATE INDEX IF NOT EXISTS idx_unanswered_status
                ON unanswered_questions(tenant_id, status, id);
            CREATE INDEX IF NOT EXISTS idx_required_channels_ref
                ON required_channels(tenant_id, chat_ref);
            CREATE INDEX IF NOT EXISTS idx_paid_messages_chat
                ON paid_messages(customer_chat_id, status, id);
            """
        )
        # Upgrade databases created before per-account isolation.
        for table in ("faq_entries", "kb_items"):
            columns = {row["name"] for row in cur.execute(f"PRAGMA table_info({table})")}
            if "tenant_id" not in columns:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 0")
        admin_columns = {row["name"] for row in cur.execute("PRAGMA table_info(assistant_admins)")}
        if "enabled" not in admin_columns:
            cur.execute("ALTER TABLE assistant_admins ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")


# =============================================================================
# Settings: typed get/set with coercion
# =============================================================================
def _coerce(value: str, typ: type):
    if typ is bool:
        s = str(value).strip().lower()
        if s in _BOOL_TRUE:
            return True
        if s in _BOOL_FALSE:
            return False
        raise ValueError(f"not a bool: {value!r}")
    if typ is int:
        return int(value)
    if typ is float:
        return float(value)
    return str(value)


def _serialize(value, typ) -> str:
    if typ is bool:
        return "true" if value else "false"
    return str(value)


def get_setting(key: str):
    """Return a setting coerced to its declared type, falling back to default."""
    if key not in SETTINGS_SCHEMA:
        raise KeyError(f"unknown setting: {key}")
    typ, default = SETTINGS_SCHEMA[key]
    default = _SEED_DEFAULTS.get(key, default)
    with read_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = ?", (_setting_key(key),))
        row = cur.fetchone()
    if row is None or row["value"] is None or str(row["value"]).strip() == "":
        return default
    try:
        return _coerce(row["value"], typ)
    except (ValueError, TypeError):
        log.warning("setting %s has invalid stored value %r; using default", key, row["value"])
        return default


def get_bool(key: str) -> bool:
    return bool(get_setting(key))


def get_int(key: str) -> int:
    return int(get_setting(key))


def get_float(key: str) -> float:
    return float(get_setting(key))


def get_str(key: str) -> str:
    return str(get_setting(key))


def set_setting(key: str, value) -> None:
    if key not in SETTINGS_SCHEMA:
        raise KeyError(f"unknown setting: {key}")
    typ, _default = SETTINGS_SCHEMA[key]
    serialized = _serialize(value, typ)
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (_setting_key(key), serialized, utils.now_iso()),
        )


def _tenant_db_key(value: str) -> str:
    tenant = tenant_id()
    return f"{tenant}:{value}" if tenant else value


def add_assistant_admin(user_id: int) -> bool:
    with tenant_scope(0):
        with write_tx() as cur:
            cur.execute("INSERT INTO assistant_admins(user_id, added_at, enabled) VALUES (?,?,1) "
                        "ON CONFLICT(user_id) DO UPDATE SET enabled=1, added_at=excluded.added_at "
                        "WHERE assistant_admins.enabled=0",
                        (int(user_id), utils.now_iso()))
            return cur.rowcount > 0


def remove_assistant_admin(user_id: int) -> bool:
    with tenant_scope(0):
        with write_tx() as cur:
            cur.execute("UPDATE assistant_admins SET enabled=0 WHERE user_id=? AND enabled=1", (int(user_id),))
            return cur.rowcount > 0


def is_assistant_admin(user_id: int) -> bool:
    with tenant_scope(0):
        with read_cursor() as cur:
            cur.execute("SELECT 1 FROM assistant_admins WHERE user_id=? AND enabled=1", (int(user_id),))
            return cur.fetchone() is not None


def list_assistant_admins() -> list[int]:
    with tenant_scope(0):
        with read_cursor() as cur:
            cur.execute("SELECT user_id FROM assistant_admins WHERE enabled=1 ORDER BY user_id")
            return [int(row["user_id"]) for row in cur.fetchall()]


def multi_admin_enabled() -> bool:
    """Permanent safety latch: once delegation is configured, unknown accounts
    can never silently fall back to the primary owner's profile."""
    with tenant_scope(0):
        with read_cursor() as cur:
            cur.execute("SELECT 1 FROM assistant_admins LIMIT 1")
            return cur.fetchone() is not None


def get_all_settings() -> dict[str, object]:
    return {key: get_setting(key) for key in SETTINGS_SCHEMA}


def seed_default_settings() -> None:
    now = utils.now_iso()
    tenant = tenant_id()
    shared_model_defaults = {}
    if tenant:
        # The primary admin chooses the provider/model; delegated accounts use
        # that approved model by default but keep their own API key and content.
        with tenant_scope(0):
            shared_model_defaults = {
                key: get_setting(key)
                for key in ("ai_provider", "ai_model_by_provider", "ai_base_url")
            }
    with write_tx() as cur:
        for key, (typ, default) in SETTINGS_SCHEMA.items():
            value = shared_model_defaults.get(key, _SEED_DEFAULTS.get(key, default))
            cur.execute(
                "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?,?,?)",
                (_setting_key(key), _serialize(value, typ), now),
            )


# =============================================================================
# DAL — business_connections
# =============================================================================
def upsert_business_connection(business_connection_id: str, business_user_id: int | None,
                               is_enabled: bool, can_reply: bool) -> None:
    with tenant_scope(0):
        now = utils.now_iso()
        with write_tx() as cur:
            cur.execute(
                """
                INSERT INTO business_connections
                    (business_connection_id, business_user_id, is_enabled, can_reply, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(business_connection_id) DO UPDATE SET
                    business_user_id = excluded.business_user_id,
                    is_enabled       = excluded.is_enabled,
                    can_reply        = excluded.can_reply,
                    updated_at       = excluded.updated_at
                """,
                (business_connection_id, business_user_id, 1 if is_enabled else 0,
                 1 if can_reply else 0, now, now),
            )


def get_business_connection(business_connection_id: str) -> sqlite3.Row | None:
    with tenant_scope(0):
        with read_cursor() as cur:
            cur.execute(
                "SELECT * FROM business_connections WHERE business_connection_id = ?",
                (business_connection_id,),
            )
            return cur.fetchone()


def get_business_connection_for_user(user_id: int) -> sqlite3.Row | None:
    with tenant_scope(0):
        with read_cursor() as cur:
            cur.execute("SELECT * FROM business_connections WHERE business_user_id=? AND is_enabled=1 "
                        "ORDER BY id DESC LIMIT 1", (int(user_id),))
            return cur.fetchone()


def set_bc_enabled(business_connection_id: str, enabled: bool) -> None:
    with tenant_scope(0):
        with write_tx() as cur:
            cur.execute(
                "UPDATE business_connections SET is_enabled=?, updated_at=? WHERE business_connection_id=?",
                (1 if enabled else 0, utils.now_iso(), business_connection_id),
            )


def list_business_connections() -> list[sqlite3.Row]:
    requested_tenant = tenant_id()
    with tenant_scope(0):
        with read_cursor() as cur:
            if requested_tenant:
                cur.execute("SELECT * FROM business_connections WHERE business_user_id=? ORDER BY id",
                            (requested_tenant,))
            else:
                cur.execute("SELECT * FROM business_connections ORDER BY id")
            return cur.fetchall()


# =============================================================================
# DAL — customers
# =============================================================================
def upsert_customer(business_connection_id: str, customer_chat_id: int,
                    first_name: str | None, last_name: str | None,
                    username: str | None) -> None:
    now = utils.now_iso()
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO customers
                (business_connection_id, customer_chat_id, first_name, last_name, username, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(business_connection_id, customer_chat_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                username   = excluded.username,
                updated_at = excluded.updated_at
            """,
            (business_connection_id, customer_chat_id, first_name, last_name, username, now, now),
        )


def get_customer(business_connection_id: str, customer_chat_id: int) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM customers WHERE business_connection_id=? AND customer_chat_id=?",
            (business_connection_id, customer_chat_id),
        )
        return cur.fetchone()


def find_bcid_for_chat(customer_chat_id: int) -> str | None:
    """Best-effort: the most recently seen connection that has this customer.
    Falls back to the sole connection if exactly one exists."""
    with read_cursor() as cur:
        cur.execute(
            "SELECT business_connection_id FROM customers WHERE customer_chat_id=? "
            "ORDER BY updated_at DESC LIMIT 1",
            (customer_chat_id,),
        )
        row = cur.fetchone()
    if row is not None:
        return row["business_connection_id"]
    conns = list_business_connections()
    return conns[0]["business_connection_id"] if len(conns) == 1 else None


# =============================================================================
# DAL — messages
# =============================================================================
def insert_message(business_connection_id: str, customer_chat_id: int,
                   telegram_message_id: int | None, direction: str, role: str,
                   content: str) -> int:
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO messages
                (business_connection_id, customer_chat_id, telegram_message_id, direction, role, content, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (business_connection_id, customer_chat_id, telegram_message_id, direction, role,
             content, utils.now_iso()),
        )
        return cur.lastrowid


def count_messages_in_window(business_connection_id: str, customer_chat_id: int,
                             since_iso: str, direction: str = "in") -> int:
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM messages "
            "WHERE business_connection_id=? AND customer_chat_id=? AND direction=? AND created_at >= ?",
            (business_connection_id, customer_chat_id, direction, since_iso),
        )
        return int(cur.fetchone()["n"])


def oldest_message_in_window(business_connection_id: str, customer_chat_id: int,
                             since_iso: str, direction: str = "in") -> str | None:
    with read_cursor() as cur:
        cur.execute(
            "SELECT MIN(created_at) AS t FROM messages "
            "WHERE business_connection_id=? AND customer_chat_id=? AND direction=? AND created_at >= ?",
            (business_connection_id, customer_chat_id, direction, since_iso),
        )
        row = cur.fetchone()
        return row["t"] if row else None


def message_exists(business_connection_id: str, customer_chat_id: int,
                   telegram_message_id: int, direction: str = "in") -> bool:
    """Dedupe guard: has this exact Telegram message already been recorded?

    Telegram can redeliver updates (restart mid-poll, network retries), and a
    redelivered customer message must not trigger a second AI reply.
    """
    if telegram_message_id is None:
        return False
    with read_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM messages WHERE business_connection_id=? AND customer_chat_id=? "
            "AND telegram_message_id=? AND direction=? LIMIT 1",
            (business_connection_id, customer_chat_id, telegram_message_id, direction),
        )
        return cur.fetchone() is not None


def get_recent_messages(business_connection_id: str, customer_chat_id: int,
                        limit: int = 20) -> list[sqlite3.Row]:
    """Newest-last slice of the recorded transcript for one customer chat."""
    with read_cursor() as cur:
        cur.execute(
            "SELECT direction, role, content, created_at FROM messages "
            "WHERE business_connection_id=? AND customer_chat_id=? "
            "ORDER BY id DESC LIMIT ?",
            (business_connection_id, customer_chat_id, limit),
        )
        rows = cur.fetchall()
    return list(reversed(rows))


def list_recent_customer_chats(limit: int = 15) -> list[sqlite3.Row]:
    """Most recently active customer chats across all connections."""
    with read_cursor() as cur:
        cur.execute(
            """
            SELECT c.business_connection_id, c.customer_chat_id, c.first_name, c.last_name,
                   c.username, c.updated_at,
                   (SELECT COUNT(*) FROM messages m
                     WHERE m.business_connection_id = c.business_connection_id
                       AND m.customer_chat_id = c.customer_chat_id) AS message_count
            FROM customers c
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def count_messages(direction: str | None = None, since_iso: str | None = None,
                   role: str | None = None) -> int:
    """Count rows in ``messages`` with optional direction/role/since filters."""
    sql = "SELECT COUNT(*) AS n FROM messages WHERE 1=1"
    params: list = []
    if direction:
        sql += " AND direction=?"
        params.append(direction)
    if role:
        sql += " AND role=?"
        params.append(role)
    if since_iso:
        sql += " AND created_at >= ?"
        params.append(since_iso)
    with read_cursor() as cur:
        cur.execute(sql, tuple(params))
        return int(cur.fetchone()["n"])


def count_customers() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM customers")
        return int(cur.fetchone()["n"])


def count_ai_replies(since_iso: str | None = None) -> int:
    """Assistant-role outbound messages (i.e. replies produced by the bot)."""
    return count_messages(direction="out", role="assistant", since_iso=since_iso)


def count_approvals(status: str | None = None) -> int:
    sql = "SELECT COUNT(*) AS n FROM pending_approvals"
    params: tuple = ()
    if status:
        sql += " WHERE status=?"
        params = (status,)
    with read_cursor() as cur:
        cur.execute(sql, params)
        return int(cur.fetchone()["n"])


# =============================================================================
# DAL — faq_entries (canned answers, see services/faq_service.py)
# =============================================================================
def insert_faq_entry(keywords: str, answer: str, question: str = "",
                     enabled: bool = True) -> int:
    now = utils.now_iso()
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO faq_entries(tenant_id, keywords, question, answer, enabled, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (tenant_id(), keywords, question, answer, 1 if enabled else 0, now, now),
        )
        return cur.lastrowid


def update_faq_entry(entry_id: int, *, keywords: str | None = None,
                     answer: str | None = None, question: str | None = None,
                     enabled: bool | None = None) -> bool:
    fields: list[str] = []
    params: list = []
    if keywords is not None:
        fields.append("keywords=?")
        params.append(keywords)
    if answer is not None:
        fields.append("answer=?")
        params.append(answer)
    if question is not None:
        fields.append("question=?")
        params.append(question)
    if enabled is not None:
        fields.append("enabled=?")
        params.append(1 if enabled else 0)
    if not fields:
        return False
    fields.append("updated_at=?")
    params.append(utils.now_iso())
    params.extend((entry_id, tenant_id()))
    with write_tx() as cur:
        cur.execute(f"UPDATE faq_entries SET {', '.join(fields)} WHERE id=? AND tenant_id=?", tuple(params))
        return cur.rowcount > 0


def get_faq_entry(entry_id: int) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM faq_entries WHERE id=? AND tenant_id=?", (entry_id, tenant_id()))
        return cur.fetchone()


def list_faq_entries(only_enabled: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM faq_entries WHERE tenant_id=?"
    params: tuple = (tenant_id(),)
    if only_enabled:
        sql += " AND enabled=1"
    sql += " ORDER BY id"
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def delete_faq_entry(entry_id: int) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM faq_entries WHERE id=? AND tenant_id=?", (entry_id, tenant_id()))
        return cur.rowcount


def clear_faq() -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM faq_entries WHERE tenant_id=?", (tenant_id(),))
        return cur.rowcount


def touch_faq_hit(entry_id: int) -> None:
    with write_tx() as cur:
        cur.execute(
            "UPDATE faq_entries SET hits = hits + 1, last_hit_at=? WHERE id=? AND tenant_id=?",
            (utils.now_iso(), entry_id, tenant_id()),
        )


def replace_faq_entries(rows: list[dict]) -> int:
    """Import helper: replace the whole FAQ set with ``rows`` (dicts with
    keywords/answer/question/enabled). Returns the number inserted."""
    with write_tx() as cur:
        cur.execute("DELETE FROM faq_entries WHERE tenant_id=?", (tenant_id(),))
        now = utils.now_iso()
        for row in rows:
            cur.execute(
                "INSERT INTO faq_entries(tenant_id, keywords, question, answer, enabled, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    tenant_id(),
                    str(row.get("keywords", "")).strip(),
                    str(row.get("question", "") or ""),
                    str(row.get("answer", "") or ""),
                    1 if row.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
        return len(rows)


# =============================================================================
# DAL — conversation_memory
# =============================================================================
def insert_memory(business_connection_id: str, customer_chat_id: int, role: str,
                  content: str) -> int:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO conversation_memory(business_connection_id, customer_chat_id, role, content, created_at) "
            "VALUES (?,?,?,?,?)",
            (business_connection_id, customer_chat_id, role, content, utils.now_iso()),
        )
        return cur.lastrowid


def get_recent_memory(business_connection_id: str, customer_chat_id: int,
                      limit: int) -> list[sqlite3.Row]:
    """Newest-first; caller reverses for chronological order."""
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM conversation_memory "
            "WHERE business_connection_id=? AND customer_chat_id=? ORDER BY id DESC LIMIT ?",
            (business_connection_id, customer_chat_id, limit),
        )
        return cur.fetchall()


def trim_memory(business_connection_id: str, customer_chat_id: int, keep: int) -> None:
    with write_tx() as cur:
        cur.execute(
            """
            DELETE FROM conversation_memory
            WHERE business_connection_id=? AND customer_chat_id=?
              AND id NOT IN (
                SELECT id FROM conversation_memory
                WHERE business_connection_id=? AND customer_chat_id=?
                ORDER BY id DESC LIMIT ?
              )
            """,
            (business_connection_id, customer_chat_id, business_connection_id, customer_chat_id, keep),
        )


def delete_memory_for_chat(business_connection_id: str, customer_chat_id: int) -> None:
    with write_tx() as cur:
        cur.execute(
            "DELETE FROM conversation_memory WHERE business_connection_id=? AND customer_chat_id=?",
            (business_connection_id, customer_chat_id),
        )


def clear_all_memory() -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM conversation_memory")
        return cur.rowcount


# =============================================================================
# DAL — paused_chats
# =============================================================================
def upsert_pause(business_connection_id: str, customer_chat_id: int, reason: str,
                 paused_until: str | None) -> None:
    now = utils.now_iso()
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO paused_chats(business_connection_id, customer_chat_id, reason, paused_until, created_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(business_connection_id, customer_chat_id) DO UPDATE SET
                reason = excluded.reason,
                paused_until = excluded.paused_until,
                created_at = excluded.created_at
            """,
            (business_connection_id, customer_chat_id, reason, paused_until, now),
        )


def get_pause(business_connection_id: str, customer_chat_id: int) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM paused_chats WHERE business_connection_id=? AND customer_chat_id=?",
            (business_connection_id, customer_chat_id),
        )
        return cur.fetchone()


def delete_pause(business_connection_id: str, customer_chat_id: int) -> int:
    with write_tx() as cur:
        cur.execute(
            "DELETE FROM paused_chats WHERE business_connection_id=? AND customer_chat_id=?",
            (business_connection_id, customer_chat_id),
        )
        return cur.rowcount


def list_active_pauses() -> list[sqlite3.Row]:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM paused_chats ORDER BY id")
        rows = cur.fetchall()
    return [row for row in rows if not utils.is_expired(row["paused_until"])]


def clear_all_pauses() -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM paused_chats")
        return cur.rowcount


# =============================================================================
# DAL — pending_approvals
# =============================================================================
def insert_pending_approval(business_connection_id: str, customer_chat_id: int,
                            customer_message_id: int | None, customer_message_text: str,
                            ai_reply_text: str) -> int:
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO pending_approvals
                (business_connection_id, customer_chat_id, customer_message_id,
                 customer_message_text, ai_reply_text, status, created_at)
            VALUES (?,?,?,?,?, 'pending', ?)
            """,
            (business_connection_id, customer_chat_id, customer_message_id,
             customer_message_text, ai_reply_text, utils.now_iso()),
        )
        return cur.lastrowid


def get_approval(approval_id: int) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM pending_approvals WHERE id=?", (approval_id,))
        return cur.fetchone()


def find_open_approval(business_connection_id: str, customer_chat_id: int,
                       customer_message_id: int | None) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM pending_approvals "
            "WHERE business_connection_id=? AND customer_chat_id=? AND customer_message_id IS ? "
            "AND status='pending' ORDER BY id DESC LIMIT 1",
            (business_connection_id, customer_chat_id, customer_message_id),
        )
        return cur.fetchone()


def mark_approval(approval_id: int, status: str) -> bool:
    """Atomically transition a pending approval. Returns True iff this call won
    the transition (rowcount==1), guarding against double-taps."""
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status=?, decided_at=? WHERE id=? AND status='pending'",
            (status, utils.now_iso(), approval_id),
        )
        return cur.rowcount == 1


def claim_approval_delivery(approval_id: int) -> bool:
    """Atomically reserve a pending approval for delivery.

    The transient ``sending`` state preserves double-tap protection without
    claiming that Telegram accepted the message before the network call. The
    timestamp lets an interrupted process leave an auditable claim behind.
    """
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='sending', decided_at=? "
            "WHERE id=? AND status='pending'",
            (utils.now_iso(), approval_id),
        )
        return cur.rowcount == 1


def complete_approval_delivery(approval_id: int, status: str) -> bool:
    """Finalize a claimed delivery after Telegram accepts the message."""
    if status not in {"sent", "sent_edited"}:
        raise ValueError(f"invalid delivery status: {status}")
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status=?, decided_at=? "
            "WHERE id=? AND status='sending'",
            (status, utils.now_iso(), approval_id),
        )
        return cur.rowcount == 1


def release_approval_delivery(approval_id: int) -> bool:
    """Return a failed delivery claim to pending so the owner can retry."""
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='pending', decided_at=NULL "
            "WHERE id=? AND status='sending'",
            (approval_id,),
        )
        return cur.rowcount == 1


def mark_approval_delivery_uncertain(approval_id: int) -> bool:
    """Stop retries when Telegram may have accepted some or all content."""
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='delivery_uncertain', decided_at=? "
            "WHERE id=? AND status='sending'",
            (utils.now_iso(), approval_id),
        )
        return cur.rowcount == 1


def mark_interrupted_approval_deliveries_uncertain() -> int:
    """Recover claims left by a previous process without risking duplicates.

    A process restart makes every remaining ``sending`` row ambiguous: Telegram
    may have accepted the message immediately before the process stopped. Mark
    those rows for manual review instead of automatically retrying them.
    """
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='delivery_uncertain', decided_at=? "
            "WHERE status='sending'",
            (utils.now_iso(),),
        )
        return cur.rowcount


def update_approval_reply(approval_id: int, ai_reply_text: str) -> None:
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET ai_reply_text=? WHERE id=?",
            (ai_reply_text, approval_id),
        )


def list_pending_approvals(status: str = "pending") -> list[sqlite3.Row]:
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM pending_approvals WHERE status=? ORDER BY created_at",
            (status,),
        )
        return cur.fetchall()


def count_pending_approvals() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM pending_approvals WHERE status='pending'")
        return int(cur.fetchone()["n"])


def invalidate_approvals_for_messages(business_connection_id: str, customer_chat_id: int,
                                      message_ids: list[int]) -> int:
    if not message_ids:
        return 0
    placeholders = ",".join("?" for _ in message_ids)
    with write_tx() as cur:
        cur.execute(
            f"UPDATE pending_approvals SET status='invalidated', decided_at=? "
            f"WHERE business_connection_id=? AND customer_chat_id=? "
            f"AND customer_message_id IN ({placeholders}) AND status='pending'",
            (utils.now_iso(), business_connection_id, customer_chat_id, *message_ids),
        )
        return cur.rowcount


def expire_stale_approvals(max_age_minutes: int) -> int:
    cutoff = utils.future_iso(-max_age_minutes)
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='expired', decided_at=? "
            "WHERE status='pending' AND created_at < ?",
            (utils.now_iso(), cutoff),
        )
        return cur.rowcount


def cancel_all_pending_approvals() -> int:
    with write_tx() as cur:
        cur.execute(
            "UPDATE pending_approvals SET status='cancelled', decided_at=? WHERE status='pending'",
            (utils.now_iso(),),
        )
        return cur.rowcount


# =============================================================================
# DAL — kb_items / kb_chunks
# =============================================================================
def insert_kb_item(title: str, source_type: str, filename: str | None) -> int:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO kb_items(tenant_id, title, source_type, filename, created_at, chunk_count) "
            "VALUES (?,?,?,?,?,0)",
            (tenant_id(), title, source_type, filename, utils.now_iso()),
        )
        return cur.lastrowid


def set_kb_item_chunk_count(item_id: int, chunk_count: int) -> None:
    with write_tx() as cur:
        cur.execute("UPDATE kb_items SET chunk_count=? WHERE id=? AND tenant_id=?", (chunk_count, item_id, tenant_id()))


def get_kb_item(item_id: int) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM kb_items WHERE id=? AND tenant_id=?", (item_id, tenant_id()))
        return cur.fetchone()


def list_kb_items() -> list[sqlite3.Row]:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM kb_items WHERE tenant_id=? ORDER BY id", (tenant_id(),))
        return cur.fetchall()


def delete_kb_item(item_id: int) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM kb_items WHERE id=? AND tenant_id=?", (item_id, tenant_id()))
        return cur.rowcount


def clear_kb() -> None:
    with write_tx() as cur:
        cur.execute("DELETE FROM kb_chunks WHERE item_id IN (SELECT id FROM kb_items WHERE tenant_id=?)", (tenant_id(),))
        cur.execute("DELETE FROM kb_items WHERE tenant_id=?", (tenant_id(),))


def _kb_item_belongs_to_tenant(cur, item_id: int) -> bool:
    cur.execute("SELECT 1 FROM kb_items WHERE id=? AND tenant_id=?", (item_id, tenant_id()))
    return cur.fetchone() is not None


def insert_kb_chunks_bulk(rows: list[tuple[int, int, str, str | None]]) -> None:
    """rows: list of (item_id, chunk_index, content, embedding_json)."""
    now = utils.now_iso()
    with write_tx() as cur:
        cur.executemany(
            "INSERT INTO kb_chunks(item_id, chunk_index, content, embedding_json, created_at) "
            "VALUES (?,?,?,?,?)",
            [(r[0], r[1], r[2], r[3], now) for r in rows if _kb_item_belongs_to_tenant(cur, r[0])],
        )


def get_all_chunks() -> list[sqlite3.Row]:
    with read_cursor() as cur:
        cur.execute("SELECT c.id, c.item_id, c.chunk_index, c.content, c.embedding_json FROM kb_chunks c JOIN kb_items i ON i.id=c.item_id WHERE i.tenant_id=?", (tenant_id(),))
        return cur.fetchall()


def count_kb_chunks() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM kb_chunks c JOIN kb_items i ON i.id=c.item_id WHERE i.tenant_id=?", (tenant_id(),))
        return int(cur.fetchone()["n"])


# =============================================================================
# DAL — api_keys
# =============================================================================
def upsert_api_key(provider: str, masked_key: str, stored_key: str) -> None:
    now = utils.now_iso()
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO api_keys(provider, masked_key, encrypted_key_or_plain_local_key, created_at, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(provider) DO UPDATE SET
                masked_key = excluded.masked_key,
                encrypted_key_or_plain_local_key = excluded.encrypted_key_or_plain_local_key,
                updated_at = excluded.updated_at
            """,
            (_tenant_db_key(provider), masked_key, stored_key, now, now),
        )


def get_api_key_row(provider: str) -> sqlite3.Row | None:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM api_keys WHERE provider=?", (_tenant_db_key(provider),))
        return cur.fetchone()


def delete_api_key(provider: str) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM api_keys WHERE provider=?", (_tenant_db_key(provider),))
        return cur.rowcount


# =============================================================================
# DAL — owner_pending_input (single active row per owner)
# =============================================================================
def set_owner_pending_input(owner_user_id: int, kind: str, context: dict,
                            ttl_minutes: float) -> None:
    with write_tx() as cur:
        cur.execute(
            """
            INSERT INTO owner_pending_input(owner_user_id, kind, context_json, created_at, expires_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(owner_user_id) DO UPDATE SET
                kind = excluded.kind,
                context_json = excluded.context_json,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            """,
            (owner_user_id, kind, json.dumps(context), utils.now_iso(), utils.future_iso(ttl_minutes)),
        )


def get_owner_pending_input(owner_user_id: int) -> dict | None:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM owner_pending_input WHERE owner_user_id=?", (owner_user_id,))
        row = cur.fetchone()
    if row is None:
        return None
    if utils.is_expired(row["expires_at"]):
        clear_owner_pending_input(owner_user_id)
        return None
    try:
        context = json.loads(row["context_json"]) if row["context_json"] else {}
    except json.JSONDecodeError:
        context = {}
    return {"kind": row["kind"], "context": context}


def has_owner_pending_input(owner_user_id: int) -> bool:
    return get_owner_pending_input(owner_user_id) is not None


def clear_owner_pending_input(owner_user_id: int) -> None:
    with write_tx() as cur:
        cur.execute("DELETE FROM owner_pending_input WHERE owner_user_id=?", (owner_user_id,))


# =============================================================================
# Maintenance
# =============================================================================
def reset_runtime_state() -> None:
    """Reset behavioral settings to defaults and clear transient tables.
    Does NOT touch business connections, customers, KB, or message history."""
    with write_tx() as cur:
        cur.execute("DELETE FROM settings")
        cur.execute("DELETE FROM paused_chats")
        cur.execute("DELETE FROM owner_pending_input")
        cur.execute(
            "UPDATE pending_approvals SET status='cancelled', decided_at=? WHERE status='pending'",
            (utils.now_iso(),),
        )
    seed_default_settings()


# =============================================================================
# DAL — topic rules (owner instructions the assistant must follow)
# =============================================================================
def insert_topic_rule(topic: str, rule: str, *, priority: int = 100, enabled: bool = False,
                      source: str = "owner", batch: str = "") -> int:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO topic_rules(tenant_id, topic, rule, priority, enabled, source, "
            "batch, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (tenant_id(), topic, rule, int(priority), 1 if enabled else 0, source, batch,
             utils.now_iso(), utils.now_iso()),
        )
        return int(cur.lastrowid)


def list_topic_rules(*, enabled_only: bool = False, batch: str | None = None) -> list:
    sql = "SELECT * FROM topic_rules WHERE tenant_id=?"
    params: list = [tenant_id()]
    if enabled_only:
        sql += " AND enabled=1"
    if batch is not None:
        sql += " AND batch=?"
        params.append(batch)
    sql += " ORDER BY priority, id"
    with read_cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.fetchall()


def get_topic_rule(rule_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM topic_rules WHERE id=? AND tenant_id=?",
                    (rule_id, tenant_id()))
        return cur.fetchone()


def update_topic_rule(rule_id: int, **fields) -> bool:
    allowed = {"topic", "rule", "priority", "enabled"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    sets = ", ".join(f"{key}=?" for key in updates)
    with write_tx() as cur:
        cur.execute(
            f"UPDATE topic_rules SET {sets}, updated_at=? WHERE id=? AND tenant_id=?",
            (*updates.values(), utils.now_iso(), rule_id, tenant_id()),
        )
        return cur.rowcount > 0


def set_topic_rules_enabled(batch: str, enabled: bool) -> int:
    with write_tx() as cur:
        cur.execute(
            "UPDATE topic_rules SET enabled=?, updated_at=? WHERE tenant_id=? AND batch=?",
            (1 if enabled else 0, utils.now_iso(), tenant_id(), batch),
        )
        return cur.rowcount


def delete_topic_rule(rule_id: int) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM topic_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id()))
        return cur.rowcount


def delete_topic_rules_batch(batch: str) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM topic_rules WHERE tenant_id=? AND batch=?",
                    (tenant_id(), batch))
        return cur.rowcount


def clear_topic_rules() -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM topic_rules WHERE tenant_id=?", (tenant_id(),))
        return cur.rowcount


def count_topic_rules(*, enabled_only: bool = True) -> int:
    sql = "SELECT COUNT(*) AS n FROM topic_rules WHERE tenant_id=?"
    if enabled_only:
        sql += " AND enabled=1"
    with read_cursor() as cur:
        cur.execute(sql, (tenant_id(),))
        return int(cur.fetchone()["n"])


def touch_topic_rule(rule_id: int) -> None:
    with write_tx() as cur:
        cur.execute("UPDATE topic_rules SET hits = hits + 1 WHERE id=? AND tenant_id=?",
                    (rule_id, tenant_id()))


# =============================================================================
# DAL — unanswered questions (what the assistant could not answer)
# =============================================================================
def insert_unanswered(business_connection_id: str | None, customer_chat_id: int | None,
                      question: str) -> int:
    text = (question or "").strip()[:2000]
    with write_tx() as cur:
        cur.execute(
            "SELECT id FROM unanswered_questions WHERE tenant_id=? AND "
            "customer_chat_id IS ? AND question=? AND status='open' LIMIT 1",
            (tenant_id(), customer_chat_id, text),
        )
        row = cur.fetchone()
        if row is not None:
            return int(row["id"])
        cur.execute(
            "INSERT INTO unanswered_questions(tenant_id, business_connection_id, "
            "customer_chat_id, question, status, created_at) VALUES (?,?,?,?,'open',?)",
            (tenant_id(), business_connection_id, customer_chat_id, text, utils.now_iso()),
        )
        return int(cur.lastrowid)


def list_unanswered(status: str = "open", limit: int = 20) -> list:
    with read_cursor() as cur:
        cur.execute(
            "SELECT * FROM unanswered_questions WHERE tenant_id=? AND status=? "
            "ORDER BY id DESC LIMIT ?",
            (tenant_id(), status, int(limit)),
        )
        return cur.fetchall()


def get_unanswered(question_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM unanswered_questions WHERE id=? AND tenant_id=?",
                    (question_id, tenant_id()))
        return cur.fetchone()


def answer_unanswered(question_id: int, answer: str) -> bool:
    with write_tx() as cur:
        cur.execute(
            "UPDATE unanswered_questions SET answer=?, status='answered', answered_at=? "
            "WHERE id=? AND tenant_id=?",
            (answer, utils.now_iso(), question_id, tenant_id()),
        )
        return cur.rowcount > 0


def set_unanswered_status(question_id: int, status: str) -> bool:
    with write_tx() as cur:
        cur.execute(
            "UPDATE unanswered_questions SET status=? WHERE id=? AND tenant_id=?",
            (status, question_id, tenant_id()),
        )
        return cur.rowcount > 0


def count_unanswered(status: str = "open") -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM unanswered_questions WHERE tenant_id=? AND status=?",
                    (tenant_id(), status))
        return int(cur.fetchone()["n"])


def clear_unanswered(status: str | None = None) -> int:
    sql = "DELETE FROM unanswered_questions WHERE tenant_id=?"
    params: list = [tenant_id()]
    if status:
        sql += " AND status=?"
        params.append(status)
    with write_tx() as cur:
        cur.execute(sql, tuple(params))
        return cur.rowcount


# =============================================================================
# DAL — resources (links / channels the assistant may search and share)
# =============================================================================
def insert_resource(kind: str, title: str, url: str = "", notes: str = "",
                    *, chars: int = 0) -> int:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO resources(tenant_id, kind, title, url, notes, enabled, chars, "
            "created_at) VALUES (?,?,?,?,?,1,?,?)",
            (tenant_id(), kind, title, url, notes, int(chars), utils.now_iso()),
        )
        return int(cur.lastrowid)


def list_resources(*, enabled_only: bool = False) -> list:
    sql = "SELECT * FROM resources WHERE tenant_id=?"
    if enabled_only:
        sql += " AND enabled=1"
    sql += " ORDER BY id"
    with read_cursor() as cur:
        cur.execute(sql, (tenant_id(),))
        return cur.fetchall()


def get_resource(resource_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM resources WHERE id=? AND tenant_id=?",
                    (resource_id, tenant_id()))
        return cur.fetchone()


def set_resource_enabled(resource_id: int, enabled: bool) -> bool:
    with write_tx() as cur:
        cur.execute("UPDATE resources SET enabled=? WHERE id=? AND tenant_id=?",
                    (1 if enabled else 0, resource_id, tenant_id()))
        return cur.rowcount > 0


def delete_resource(resource_id: int) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM resources WHERE id=? AND tenant_id=?", (resource_id, tenant_id()))
        return cur.rowcount


def count_resources() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM resources WHERE tenant_id=? AND enabled=1",
                    (tenant_id(),))
        return int(cur.fetchone()["n"])


def clear_resources() -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM resources WHERE tenant_id=?", (tenant_id(),))
        return cur.rowcount


# =============================================================================
# DAL — required channels + membership cache (the subscription gate)
# =============================================================================
def add_required_channel(chat_ref: str, *, title: str = "", invite_link: str = "",
                         kind: str = "channel") -> int:
    ref = (chat_ref or "").strip()
    with write_tx() as cur:
        cur.execute("SELECT id FROM required_channels WHERE tenant_id=? AND chat_ref=?",
                    (tenant_id(), ref))
        row = cur.fetchone()
        if row is not None:
            cur.execute(
                "UPDATE required_channels SET title=?, invite_link=?, kind=?, enabled=1 "
                "WHERE id=?",
                (title, invite_link, kind, int(row["id"])),
            )
            return int(row["id"])
        cur.execute(
            "INSERT INTO required_channels(tenant_id, chat_ref, title, invite_link, kind, "
            "enabled, created_at) VALUES (?,?,?,?,?,1,?)",
            (tenant_id(), ref, title, invite_link, kind, utils.now_iso()),
        )
        return int(cur.lastrowid)


def list_required_channels(*, enabled_only: bool = False) -> list:
    sql = "SELECT * FROM required_channels WHERE tenant_id=?"
    if enabled_only:
        sql += " AND enabled=1"
    sql += " ORDER BY id"
    with read_cursor() as cur:
        cur.execute(sql, (tenant_id(),))
        return cur.fetchall()


def get_required_channel(channel_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM required_channels WHERE id=? AND tenant_id=?",
                    (channel_id, tenant_id()))
        return cur.fetchone()


def set_required_channel_enabled(channel_id: int, enabled: bool) -> bool:
    with write_tx() as cur:
        cur.execute("UPDATE required_channels SET enabled=? WHERE id=? AND tenant_id=?",
                    (1 if enabled else 0, channel_id, tenant_id()))
        return cur.rowcount > 0


def delete_required_channel(channel_id: int) -> int:
    with write_tx() as cur:
        cur.execute("DELETE FROM required_channels WHERE id=? AND tenant_id=?",
                    (channel_id, tenant_id()))
        return cur.rowcount


def count_required_channels() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM required_channels WHERE tenant_id=? AND enabled=1",
                    (tenant_id(),))
        return int(cur.fetchone()["n"])


def set_gate_check(customer_chat_id: int, all_ok: bool) -> None:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO gate_checks(customer_chat_id, all_ok, checked_at) VALUES (?,?,?) "
            "ON CONFLICT(customer_chat_id) DO UPDATE SET all_ok=excluded.all_ok, "
            "checked_at=excluded.checked_at",
            (int(customer_chat_id), 1 if all_ok else 0, utils.now_iso()),
        )


def get_gate_check(customer_chat_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM gate_checks WHERE customer_chat_id=?", (int(customer_chat_id),))
        return cur.fetchone()


def clear_gate_checks() -> None:
    with write_tx() as cur:
        cur.execute("DELETE FROM gate_checks")


# =============================================================================
# DAL — paid messages (Telegram Stars)
# =============================================================================
def create_paid_message(customer_chat_id: int, user_id: int | None, payload: str, stars: int,
                        message_text: str, *, status: str = "pending") -> int:
    with write_tx() as cur:
        cur.execute(
            "INSERT INTO paid_messages(tenant_id, customer_chat_id, user_id, payload, stars, "
            "message_text, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (tenant_id(), int(customer_chat_id), user_id, payload, int(stars), message_text,
             status, utils.now_iso()),
        )
        return int(cur.lastrowid)


def get_paid_message(message_id: int):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM paid_messages WHERE id=? AND tenant_id=?",
                    (int(message_id), tenant_id()))
        return cur.fetchone()


def get_paid_message_by_payload(payload: str):
    with read_cursor() as cur:
        cur.execute("SELECT * FROM paid_messages WHERE payload=? AND tenant_id=? "
                    "ORDER BY id DESC LIMIT 1", (payload, tenant_id()))
        return cur.fetchone()


def mark_paid_message_paid(payload: str, charge_id: str = "") -> bool:
    with write_tx() as cur:
        cur.execute(
            "UPDATE paid_messages SET status='paid', charge_id=?, paid_at=? "
            "WHERE payload=? AND tenant_id=? AND status='pending'",
            (charge_id, utils.now_iso(), payload, tenant_id()),
        )
        return cur.rowcount > 0


def mark_paid_message_delivered(message_id: int) -> None:
    with write_tx() as cur:
        cur.execute("UPDATE paid_messages SET delivered=1 WHERE id=? AND tenant_id=?",
                    (int(message_id), tenant_id()))


def set_paid_message_status(message_id: int, status: str) -> bool:
    with write_tx() as cur:
        cur.execute("UPDATE paid_messages SET status=? WHERE id=? AND tenant_id=?",
                    (status, int(message_id), tenant_id()))
        return cur.rowcount > 0


def count_paid_messages(*, status: str | None = None, free: bool | None = None) -> int:
    sql = "SELECT COUNT(*) AS n FROM paid_messages WHERE tenant_id=?"
    params: list = [tenant_id()]
    if status:
        sql += " AND status=?"
        params.append(status)
    if free is True:
        sql += " AND stars=0"
    elif free is False:
        sql += " AND stars>0"
    with read_cursor() as cur:
        cur.execute(sql, tuple(params))
        return int(cur.fetchone()["n"])


def count_free_messages_used(customer_chat_id: int) -> int:
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM paid_messages WHERE tenant_id=? AND "
            "customer_chat_id=? AND stars=0 AND status IN ('free','paid')",
            (tenant_id(), int(customer_chat_id)),
        )
        return int(cur.fetchone()["n"])


def sum_stars_earned() -> int:
    with read_cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(stars), 0) AS total FROM paid_messages "
                    "WHERE tenant_id=? AND status='paid' AND stars>0", (tenant_id(),))
        return int(cur.fetchone()["total"])


def list_paid_messages(limit: int = 20) -> list:
    with read_cursor() as cur:
        cur.execute("SELECT * FROM paid_messages WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                    (tenant_id(), int(limit)))
        return cur.fetchall()

"""Owner access control: guards for commands and callbacks, the first-run
"claim" flow, and the polite notice shown to non-owner users who message the bot
directly.

Claim flow
----------
If ``OWNER_USER_ID`` is not set in ``.env``, the bot prints a random claim code
in the terminal at startup. The person who sends ``/start <code>`` in Telegram
becomes the owner; the choice is stored in the database and survives restarts.
This lets you go from "bot token" to "working assistant" without looking up your
numeric user id — while keeping the bot unusable by anyone who cannot see the
terminal.

Note: customer messages arrive as *business_message* updates (a different handler
path) — they never reach these command/DM handlers.
"""

from __future__ import annotations

import functools
import contextlib
import hmac
import logging
import secrets
import threading
import time

import database
import utils

log = logging.getLogger("smartel.security")

_owner_id: int | None = None          # from config (OWNER_USER_ID), if set
_claimed_cache: int | None = None     # owner id claimed from Telegram
_bot = None
_claim_code: str | None = None
_claim_lock = threading.Lock()
_failed_claims: list[float] = []      # timestamps of failed attempts
_CLAIM_WINDOW_SECONDS = 600
_MAX_FAILED_CLAIMS = 10

# Throttle the non-owner notice so the bot can't be used as a reflector.
_notice_lock = threading.Lock()
_last_notice: dict[int, float] = {}
_NOTICE_COOLDOWN_SECONDS = 600

NON_OWNER_NOTICE = (
    "👋 This is a <b>managed Telegram Business assistant</b>. It does not chat "
    "directly here.\n\n"
    "To reach the business, please message them through their Telegram Business "
    "profile. The owner connects this bot via <b>Telegram Settings → Business → "
    "Chatbots</b>."
)

CLAIM_NOTICE = (
    "🔐 This assistant is not activated yet.\n\n"
    "If you are the owner, open the terminal where the bot is running and send: "
    "<code>/start &lt;claim-code&gt;</code> with the code printed there."
)


def init(bot, owner_id: int | None = None, claim_code: str | None = None) -> None:
    global _owner_id, _bot, _claim_code
    _bot = bot
    _owner_id = int(owner_id) if owner_id else None
    _claim_code = claim_code or None
    if _claim_code:
        log.info("owner claim code generated (visible in the terminal banner)")


# =============================================================================
# Owner resolution
# =============================================================================
def owner_id() -> int | None:
    """Configured owner, else the owner claimed from Telegram, else None."""
    global _claimed_cache
    if _owner_id:
        return _owner_id
    if _claimed_cache:
        return _claimed_cache
    try:
        claimed = int(database.get_int("claimed_owner_user_id"))
    except Exception:
        return None
    if claimed and claimed > 0:
        _claimed_cache = claimed
        return claimed
    return None


def is_owner(user_id) -> bool:
    oid = owner_id()
    return oid is not None and user_id == oid


def operator_id() -> int | None:
    """Current account administrator (primary owner for tenant zero)."""
    tenant = database.tenant_id()
    return tenant or owner_id()


def tenant_for_user(user_id: int | None) -> int | None:
    """Resolve a user's private assistant namespace, or deny access."""
    if user_id is None:
        return None
    if is_owner(user_id):
        return 0
    try:
        return int(user_id) if database.is_assistant_admin(int(user_id)) else None
    except Exception:
        return None


@contextlib.contextmanager
def operator_scope(user_id: int | None):
    tenant = tenant_for_user(user_id)
    if tenant is None:
        raise PermissionError("not an assistant administrator")
    with database.tenant_scope(tenant):
        yield tenant


def run_as_operator(message, function):
    user = getattr(message, "from_user", None)
    with operator_scope(getattr(user, "id", None)):
        return function()


def is_operator_msg(message) -> bool:
    user = getattr(message, "from_user", None)
    return bool(user) and tenant_for_user(user.id) is not None


def is_operator_call(call) -> bool:
    user = getattr(call, "from_user", None)
    return bool(user) and tenant_for_user(user.id) is not None


def has_pending_operator_input(message) -> bool:
    user = getattr(message, "from_user", None)
    if not user or tenant_for_user(user.id) is None:
        return False
    with operator_scope(user.id):
        return database.has_owner_pending_input(operator_id())


def is_owner_msg(message) -> bool:
    user = getattr(message, "from_user", None)
    return bool(user) and is_owner(user.id)


def is_owner_call(call) -> bool:
    user = getattr(call, "from_user", None)
    return bool(user) and is_owner(user.id)


def claim_pending() -> bool:
    """True while the bot still needs its owner (claim code active)."""
    return owner_id() is None and bool(_claim_code)


def claim_code() -> str | None:
    return _claim_code


# =============================================================================
# Claim handling
# =============================================================================
def generate_claim_code() -> str:
    return secrets.token_hex(4).upper()      # 8 hex chars, e.g. "6F3A91C2"


def _too_many_failures() -> bool:
    now = time.time()
    with _claim_lock:
        _failed_claims[:] = [t for t in _failed_claims if now - t < _CLAIM_WINDOW_SECONDS]
        return len(_failed_claims) >= _MAX_FAILED_CLAIMS


def _register_failure() -> None:
    with _claim_lock:
        _failed_claims.append(time.time())


def register_claim_handler(bot) -> None:
    """Register the /start handler used only while the bot is unclaimed."""
    @bot.message_handler(commands=["start"], func=lambda m: claim_pending())
    def _claim(message):
        try:
            handle_claim(message)
        except Exception:
            log.exception("claim handler failed")


def handle_claim(message) -> None:
    global _owner_id, _claim_code
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split()
    supplied = parts[1].strip() if len(parts) > 1 else ""

    if uid is None:
        return
    if _too_many_failures():
        log.warning("too many failed claim attempts; ignoring claim for uid=%s", utils.mask_id(uid))
        return

    with _claim_lock:
        # Re-check under the lock: a configured owner (or a claim that just won
        # the race) must never be replaced.
        if owner_id() is not None or _claim_code is None:
            log.info("claim attempt ignored (an owner already exists)")
            return
        if not supplied or not hmac.compare_digest(supplied.upper(), _claim_code):
            _failed_claims.append(time.time())
            log.info("claim attempt from uid=%s rejected", utils.mask_id(uid))
            try:
                _bot.send_message(message.chat.id, CLAIM_NOTICE, parse_mode="HTML")
            except Exception:
                log.debug("could not send the claim notice", exc_info=True)
            return

        database.set_setting("claimed_owner_user_id", int(uid))
        _owner_id = int(uid)
        _claim_code = None
    log.info("owner claimed from Telegram: uid=%s", utils.mask_id(uid))
    try:
        _bot.send_message(
            message.chat.id,
            "✅ <b>You are now the owner of this assistant.</b>\n\n"
            "Next: /setup walks you through connecting it to your Telegram Business "
            "account, /ai picks the AI provider, /faq adds your answers, /mode chooses "
            "how replies are sent.",
            parse_mode="HTML",
        )
    except Exception:
        log.debug("could not send the claim confirmation", exc_info=True)
    # Follow up with the control panel so the owner lands on the UI immediately.
    try:
        from handlers import owner_commands
        owner_commands.cmd_start(message)
    except Exception:
        log.debug("could not send the control panel after claiming", exc_info=True)


# =============================================================================
# Guards
# =============================================================================
def owner_only(handler):
    """Decorator for message handlers registered WITHOUT a func predicate."""
    @functools.wraps(handler)
    def wrapper(message, *args, **kwargs):
        user = getattr(message, "from_user", None)
        if not user or tenant_for_user(user.id) is None:
            handle_non_owner_dm(message)
            return None
        with operator_scope(user.id):
            return handler(message, *args, **kwargs)
    return wrapper


def owner_only_callback(handler):
    """Decorator for callback-query handlers."""
    @functools.wraps(handler)
    def wrapper(call, *args, **kwargs):
        user = getattr(call, "from_user", None)
        if not user or tenant_for_user(user.id) is None:
            try:
                _bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
            except Exception:
                pass
            return None
        with operator_scope(user.id):
            return handler(call, *args, **kwargs)
    return wrapper


def handle_non_owner_dm(message) -> None:
    """Send the managed-assistant notice to a non-owner (throttled)."""
    user = getattr(message, "from_user", None)
    uid = user.id if user else None
    if uid is None:
        return
    now = utils.now_ts()
    with _notice_lock:
        last = _last_notice.get(uid, 0)
        if now - last < _NOTICE_COOLDOWN_SECONDS:
            return
        _last_notice[uid] = now
    log.info("non-owner DM from uid=%s", utils.mask_id(uid))
    try:
        _bot.send_message(message.chat.id, NON_OWNER_NOTICE, parse_mode="HTML")
    except Exception:
        log.debug("could not send non-owner notice", exc_info=True)
    # public_direct_bot_chat_enabled is a safety flag: when False (default) the
    # bot does nothing beyond this notice (never acts as a public chatbot).
    _ = database.get_bool("public_direct_bot_chat_enabled")

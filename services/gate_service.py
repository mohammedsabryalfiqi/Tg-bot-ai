"""Entry gates: forced subscription and Telegram Stars paid messages.

Both gates are **admin switches** (``/gate``, or `/settings → 🚪 الدخول`), both
ship **off**, and both are enforced only on the direct-message pipeline (people
writing to the bot itself) — a real Telegram Business customer chat is never
gated, so nothing that works today can suddenly stop answering.

Subscription gate
-----------------
``require_subscription_enabled``: every message from a chat is checked with
``getChatMember`` against the channels/groups in ``required_channels``. The
result is cached in ``gate_checks`` for :data:`CHECK_TTL_MINUTES` so a chatty
user does not hammer the Telegram API.

Stars gate
----------
``paid_messages_enabled`` + ``paid_message_stars`` (the price the admin types):
the first ``paid_message_free_count`` messages per chat are free; after that the
bot answers with an invoice and only delivers the parked message once Telegram
confirms the payment (``successful_payment``). One star = one unit (XTR).
"""

from __future__ import annotations

import logging
import secrets

import database
import i18n
import utils
import telegram_api

log = logging.getLogger("smartel.gate")

CHECK_TTL_MINUTES = 5
_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}
MAX_STARS = 100000


def _now() -> str:
    return utils.now_iso()


# =============================================================================
# Subscription gate
# =============================================================================
def subscription_enabled() -> bool:
    return database.get_bool("require_subscription_enabled")


def channels() -> list:
    return database.list_required_channels(enabled_only=True)


def add_channel(chat_ref: str, *, title: str = "", invite_link: str = "",
                kind: str | None = None) -> int:
    """Register a required channel/group.

    ``chat_ref`` is an ``@username`` or a numeric chat id; ``invite_link`` (a
    private invite, or a "t.me/…" link) is what the join buttons use.
    """
    ref = (chat_ref or "").strip()
    if ref and not ref.startswith("@") and not ref.lstrip("-").isdigit():
        ref = "@" + ref.lstrip("@")
    link = (invite_link or "").strip()
    if not link and ref.startswith("@"):
        link = f"https://t.me/{ref.lstrip('@')}"
    guessed = kind or ("group" if "joinchat" in link or "+" in link else "channel")
    channel_id = database.add_required_channel(ref, title=title, invite_link=link, kind=guessed)
    database.clear_gate_checks()
    return channel_id


def remove_channel(channel_id: int) -> bool:
    removed = bool(database.delete_required_channel(channel_id))
    if removed:
        database.clear_gate_checks()
    return removed


def toggle_channel(channel_id: int) -> bool | None:
    row = database.get_required_channel(channel_id)
    if row is None:
        return None
    enabled = not bool(row["enabled"])
    database.set_required_channel_enabled(channel_id, enabled)
    database.clear_gate_checks()
    return enabled


def _join_buttons() -> list[list]:
    """Inline rows for every required channel, each with its own URL button."""
    from telebot import types

    rows = []
    for row in channels():
        url = (row["invite_link"] or "").strip()
        if not url and row["chat_ref"].startswith("@"):
            url = f"https://t.me/{row['chat_ref'].lstrip('@')}"
        if not url:
            continue
        rows.append([types.InlineKeyboardButton(text=row["title"] or row["chat_ref"], url=url)])
    return rows


def join_rows() -> list[list]:
    """One URL button per required channel (no verify button)."""
    return _join_buttons()


def join_keyboard():
    """Keyboard with a join button per channel; None when nothing to show."""
    from telebot import types

    rows = _join_buttons()
    if not rows:
        return None
    return types.InlineKeyboardMarkup(rows)


def _cache_fresh(checked_at: str | None) -> bool:
    """True while a cached membership answer is still trustworthy."""
    moment = utils.parse_iso(checked_at)
    if moment is None:
        return False
    age_minutes = (utils.now() - moment).total_seconds() / 60.0
    return age_minutes < CHECK_TTL_MINUTES


def _is_member(chat_ref: str, user_id: int) -> bool:
    try:
        info = telegram_api.get_chat_member(chat_ref, user_id)
    except Exception:
        log.debug("getChatMember blew up for %s", chat_ref, exc_info=True)
        return False                           # unverified => keep gate closed
    if not info:
        return False
    status = str(info.get("status", "")).lower()
    if status == "restricted":
        return bool(info.get("is_member", False))
    return status in _MEMBER_STATUSES


def missing_channels(user_id: int, *, force: bool = False) -> list:
    """Channels the user has not joined yet (cached for ``CHECK_TTL_MINUTES``)."""
    if not subscription_enabled():
        return []
    cached = None if force else database.get_gate_check(user_id)
    if cached is not None and _cache_fresh(cached["checked_at"]) and cached["all_ok"]:
        return []
    missing = [row for row in channels() if not _is_member(row["chat_ref"], user_id)]
    try:
        database.set_gate_check(user_id, not missing)
    except Exception:                      # pragma: no cover - cache is best effort
        log.debug("could not cache the membership check", exc_info=True)
    return missing


def was_verified_before(user_id: int) -> bool:
    """True when a cached membership check already passed for this user.

    Used to copy only the *first* message of a chat that just joined, instead of
    forwarding every later message to the owner.
    """
    try:
        cached = database.get_gate_check(user_id)
    except Exception:                      # pragma: no cover - cache is best effort
        return False
    return bool(cached is not None and cached["all_ok"] and _cache_fresh(cached["checked_at"]))


def subscription_ok(user_id: int) -> bool:
    if not subscription_enabled():
        return True
    return bool(channels()) and not missing_channels(user_id)


# =============================================================================
# Stars gate
# =============================================================================
def stars_price() -> int:
    try:
        price = database.get_int("paid_message_stars")
    except Exception:                      # pragma: no cover - uninitialised DB
        return 0
    return max(0, min(int(price), MAX_STARS))


def payments_enabled() -> bool:
    """The enabled switch is authoritative, even during incomplete setup."""
    return database.get_bool("paid_messages_enabled")


def free_quota() -> int:
    try:
        return max(0, database.get_int("paid_message_free_count"))
    except Exception:                      # pragma: no cover
        return 0


def free_left(user_id: int) -> int:
    quota = free_quota()
    if quota <= 0:
        return 0
    try:
        used = database.count_free_messages_used(user_id)
    except Exception:                      # pragma: no cover
        used = 0
    return max(0, quota - used)


def free_last_notice(stars: int | None = None) -> str:
    """Localised "that was your last free message" notice."""
    return i18n.t("gate.user.free_last", stars=stars if stars is not None else stars_price())


def payment_required(user_id: int) -> bool:
    if not payments_enabled():
        return False
    return free_left(user_id) <= 0


def new_payload(user_id: int) -> str:
    """Opaque payload that ties an invoice back to the parked message."""
    return f"pm:{int(user_id)}:{secrets.token_hex(6)}"


def park_message(user_id: int, chat_id: int, text: str, *, stars: int | None = None,
                 free: bool = False) -> dict | None:
    """Store the message until the payment lands (or record a free use)."""
    payload = new_payload(user_id)
    amount = 0 if free else int(stars if stars is not None else stars_price())
    if free:
        if not database.reserve_free_message(chat_id, user_id, payload, text, free_quota()):
            return None
    else:
        database.create_paid_message(chat_id, user_id, payload, amount, text, status="pending")
    row = database.get_paid_message_by_payload(payload)
    if free:
        log.info("free message %s/%s used by chat=%s", free_quota(), free_quota(),
                 utils.mask_id(chat_id))
    return dict(row) if row is not None else None


def confirm_payment(payload: str, charge_id: str = "") -> dict | None:
    """Mark the parked message as paid and return it (None when unknown)."""
    row = database.get_paid_message_by_payload(payload)
    if row is None or row["status"] not in ("pending",):
        return None
    if not database.mark_paid_message_paid(payload, charge_id):
        return None
    fresh = database.get_paid_message_by_payload(payload)
    log.info("stars payment confirmed (%s stars, chat=%s)",
             row["stars"], utils.mask_id(row["customer_chat_id"]))
    return dict(fresh) if fresh is not None else None


def mark_delivered(message_id: int) -> None:
    database.mark_paid_message_delivered(message_id)


def refund(message_id: int, status: str = "refunded") -> bool:
    return database.set_paid_message_status(message_id, status)


# =============================================================================
# Reporting
# =============================================================================
def summary() -> dict:
    return {
        "subscription_on": subscription_enabled(),
        "channels": len(channels()),
        "payments_on": payments_enabled(),
        "price": stars_price(),
        "free": free_quota(),
        "paid": database.count_paid_messages(status="paid"),
        "stars": database.sum_stars_earned(),
    }


def summary_lines() -> list[str]:
    data = summary()
    lines = [
        i18n.t("gate.status.subscription",
               state=i18n.t("set.value.on") if data["subscription_on"]
               else i18n.t("set.value.off"),
               count=data["channels"]),
        i18n.t("gate.status.payments",
               state=i18n.t("set.value.on") if data["payments_on"]
               else i18n.t("set.value.off")),
        i18n.t("gate.status.price", stars=data["price"]),
        i18n.t("gate.status.free", count=data["free"]),
        i18n.t("gate.status.earned", count=data["paid"], stars=data["stars"]),
    ]
    return lines

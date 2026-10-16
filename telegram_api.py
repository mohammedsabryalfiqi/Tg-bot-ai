"""Telegram Bot API access.

Two layers:
  * Raw HTTP functions (``raw_*`` + ``get_business_connection``/file helpers)
    built on ``requests`` — used for endpoints TeleBot may not expose across
    versions (notably ``getBusinessConnection``) and as a fallback/escape hatch.
  * A thin send adapter (``send_reply`` / ``chat_action`` / ``answer_callback``)
    that handlers use. It prefers TeleBot (which natively supports
    ``business_connection_id``), applies message chunking, and falls back to raw
    HTTP if a TeleBot call raises.

Business replies pass ``business_connection_id``; owner/admin messages do not.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time

import requests

import utils

log = logging.getLogger("smartel.telegram")

_TOKEN: str | None = None
_API_BASE: str | None = None
_FILE_BASE: str | None = None
_TIMEOUT = (5, 30)  # (connect, read)

# Synthetic "business connection" that represents the bot's own private chats.
# Direct messages need no Telegram Business rights, so every call that would
# carry this id must be sent WITHOUT business_connection_id (Telegram rejects an
# unknown id with "business connection not found").
DIRECT_CONNECTION_ID = "direct"


def api_connection_id(business_connection_id: str | None) -> str | None:
    """The ``business_connection_id`` to put on the wire (None for direct chats)."""
    if business_connection_id in (None, "", DIRECT_CONNECTION_ID):
        return None
    return business_connection_id


def is_direct_connection(business_connection_id: str | None) -> bool:
    return business_connection_id == DIRECT_CONNECTION_ID


class TelegramAPIError(Exception):
    def __init__(self, description: str, error_code: int | None = None):
        super().__init__(description)
        self.description = description
        self.error_code = error_code


class TelegramPartialSendError(TelegramAPIError):
    """Raised when a chunked message fails after at least one chunk was sent."""

    def __init__(self, sent_count: int, total_count: int):
        super().__init__(
            f"partial Telegram delivery ({sent_count} of {total_count} chunks sent)"
        )
        self.sent_count = sent_count
        self.total_count = total_count


def init(token: str) -> None:
    global _TOKEN, _API_BASE, _FILE_BASE
    _TOKEN = token
    _API_BASE = f"https://api.telegram.org/bot{token}"
    _FILE_BASE = f"https://api.telegram.org/file/bot{token}"


def _require_init() -> None:
    if not _API_BASE:
        raise RuntimeError("telegram_api not initialised; call init(token).")


def _serialize_markup(reply_markup):
    if reply_markup is None:
        return None
    if hasattr(reply_markup, "to_dict"):
        return json.dumps(reply_markup.to_dict())
    if isinstance(reply_markup, (dict, list)):
        return json.dumps(reply_markup)
    return reply_markup  # already a JSON string


def _post(method: str, data: dict, *, retry_429: bool = True) -> dict:
    _require_init()
    payload = {k: v for k, v in data.items() if v is not None}
    try:
        resp = requests.post(f"{_API_BASE}/{method}", data=payload, timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise TelegramAPIError(f"network error calling {method}: {e}") from e

    try:
        body = resp.json()
    except ValueError:
        raise TelegramAPIError(f"{method}: non-JSON response (HTTP {resp.status_code})")

    if body.get("ok"):
        return body.get("result")

    error_code = body.get("error_code")
    description = body.get("description", "unknown error")
    if error_code == 429 and retry_429:
        retry_after = (body.get("parameters") or {}).get("retry_after", 1)
        time.sleep(min(int(retry_after) + 1, 30))
        return _post(method, data, retry_429=False)
    raise TelegramAPIError(description, error_code)


# =============================================================================
# Raw HTTP functions (spec signatures)
# =============================================================================
def send_message(chat_id, text, business_connection_id=None, reply_to_message_id=None,
                 parse_mode="HTML", reply_markup=None) -> dict:
    business_connection_id = api_connection_id(business_connection_id)
    return _post("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "business_connection_id": business_connection_id,
        "reply_to_message_id": reply_to_message_id,
        "reply_markup": _serialize_markup(reply_markup),
    })


def send_chat_action(chat_id, action, business_connection_id=None) -> dict:
    business_connection_id = api_connection_id(business_connection_id)
    return _post("sendChatAction", {
        "chat_id": chat_id,
        "action": action,
        "business_connection_id": business_connection_id,
    })


def answer_callback_query(callback_query_id, text=None, show_alert=False) -> dict:
    return _post("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": "true" if show_alert else None,
    })


def get_business_connection(business_connection_id) -> dict | None:
    """Fetch a business connection via the raw API (TeleBot lacks a stable
    wrapper across versions). Returns the result dict or None on failure."""
    try:
        return _post("getBusinessConnection",
                     {"business_connection_id": business_connection_id})
    except TelegramAPIError as e:
        log.warning("getBusinessConnection failed: %s", e.description)
        return None


def get_file(file_id) -> dict:
    return _post("getFile", {"file_id": file_id})


def get_chat_member(chat_id, user_id) -> dict | None:
    """Membership lookup for the subscription gate (None when unknown)."""
    try:
        return _post("getChatMember", {"chat_id": chat_id, "user_id": user_id})
    except TelegramAPIError as e:
        log.info("getChatMember failed for %s: %s", chat_id, e.description)
        return None


def get_chat(chat_id) -> dict | None:
    """Chat metadata (used to turn an @username into a title/kind)."""
    try:
        return _post("getChat", {"chat_id": chat_id})
    except TelegramAPIError as e:
        log.info("getChat failed for %s: %s", chat_id, e.description)
        return None


def download_file(file_path, dest_path) -> None:
    _require_init()
    url = f"{_FILE_BASE}/{file_path}"
    resp = requests.get(url, timeout=_TIMEOUT, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


# Telegram bots may download files up to 20 MB; refuse bigger ones explicitly
# instead of pulling them into memory and failing later.
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def download_file_bytes(file_id, *, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
    """Download a Telegram file into memory (used by KB upload and FAQ import).

    Guards against oversized files and retries once on a transient network error.
    """
    info = get_file(file_id) or {}
    file_path = info.get("file_path")
    if not file_path:
        raise TelegramAPIError("Telegram did not return a downloadable path for that file.")
    declared = info.get("file_size")
    if declared and int(declared) > max_bytes:
        raise TelegramAPIError(
            f"file too large ({int(declared)} bytes > {max_bytes} bytes)"
        )
    _require_init()
    url = f"{_FILE_BASE}/{file_path}"
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with requests.get(url, timeout=_TIMEOUT, stream=True) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise TelegramAPIError(f"file too large (> {max_bytes} bytes)")
                    chunks.append(chunk)
                return b"".join(chunks)
        except TelegramAPIError:
            raise
        except requests.RequestException as e:
            last_error = e
            if attempt == 0:
                continue
    raise TelegramAPIError(f"could not download the file: {type(last_error).__name__}")


# =============================================================================
# Telegram Stars invoices (the paid-message gate)
# =============================================================================
def send_star_invoice(chat_id, *, title: str, description: str, payload: str, stars: int,
                      label: str = "", reply_markup=None) -> dict | None:
    """Send a Telegram Stars invoice (currency ``XTR``: 1 star = 1 unit).

    Uses the raw API because Stars invoices must not carry a provider token, and
    older TeleBot wrappers insist on one. Returns the sent message or None.
    """
    data = {
        "chat_id": chat_id,
        "title": title[:32],
        "description": description[:255],
        "payload": payload,
        "currency": "XTR",
        "prices": json.dumps([{"label": (label or title)[:32], "amount": int(stars)}]),
        "start_parameter": "paid-message",
    }
    if reply_markup is not None:
        data["reply_markup"] = reply_markup.to_json() if hasattr(reply_markup, "to_json") \
            else reply_markup
    try:
        return _post("sendInvoice", data)
    except TelegramAPIError as e:
        log.warning("sendInvoice failed: %s", e.description)
        return None


def refund_star_payment(user_id: int, charge_id: str) -> bool:
    """Refund a Stars payment (the bot must be the one that received it)."""
    try:
        _post("refundStarPayment",
              {"user_id": int(user_id), "telegram_payment_charge_id": charge_id})
        return True
    except TelegramAPIError as e:
        log.warning("refundStarPayment failed: %s", e.description)
        return False


def answer_pre_checkout_query(query_id: str, ok: bool, error_message: str | None = None) -> bool:
    """Approve/decline a Stars payment before it is charged."""
    data = {"pre_checkout_query_id": query_id, "ok": ok}
    if error_message and not ok:
        data["error_message"] = error_message[:200]
    try:
        _post("answerPreCheckoutQuery", data)
        return True
    except TelegramAPIError as e:
        log.warning("answerPreCheckoutQuery failed: %s", e.description)
        return False


# =============================================================================
# Send adapter (TeleBot-first, raw fallback) — what handlers call
# =============================================================================
def send_reply(bot, chat_id, text, *, business_connection_id=None,
               reply_to_message_id=None, reply_markup=None, parse_mode="HTML",
               sanitize=True) -> list:
    """Send a (possibly long) message, split into <=4096-char chunks.

    * ``sanitize`` (default) converts Markdown to Telegram HTML and escapes
      anything else, so model output can never break the send with
      "can't parse entities".
    * Only the first chunk carries reply_to_message_id and reply_markup.
    * Transient network failures are retried; if Telegram still rejects the
      entities, the chunk is re-sent as plain text (no parse_mode) so the
      customer always gets an answer.
    """
    chunks = utils.split_message(text)
    sent = []
    for i, chunk in enumerate(chunks):
        rtm = reply_to_message_id if i == 0 else None
        markup = reply_markup if i == 0 else None
        body = utils.to_telegram_html(chunk) if (sanitize and parse_mode == "HTML") else chunk
        try:
            sent.append(
                _send_one(
                    bot, chat_id, body, business_connection_id, rtm, markup, parse_mode
                )
            )
        except Exception as exc:
            if _is_entity_error(exc):
                log.warning("Telegram rejected message entities; retrying as plain text.")
                try:
                    sent.append(_send_one(bot, chat_id, utils.plain_text(body) or body,
                                          business_connection_id, rtm, markup, None))
                    continue
                except Exception as inner:
                    exc = inner
            if sent:
                raise TelegramPartialSendError(len(sent), len(chunks)) from exc
            raise
    return sent


def _is_entity_error(exc: Exception) -> bool:
    """True when Telegram complained about HTML/markdown entities."""
    text = str(exc)
    return any(
        marker in text
        for marker in ("can't parse entities", "can't find end", "unsupported start tag",
                       "Unsupported start tag", "entity", "Can't parse entities")
    )


def _send_one(bot, chat_id, text, business_connection_id, reply_to_message_id,
              reply_markup, parse_mode, attempts: int = 2):
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            kwargs = {}
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            business_connection_id = api_connection_id(business_connection_id)
            if business_connection_id is not None:
                kwargs["business_connection_id"] = business_connection_id
            if reply_to_message_id is not None:
                kwargs["reply_to_message_id"] = reply_to_message_id
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:  # noqa: PERF203 - retry only transient failures
            last_error = e
            if _is_entity_error(e):
                # Retrying the raw-HTTP fallback with the same parse_mode would
                # fail identically; let the caller re-send as plain text.
                raise
            if attempt < attempts and _is_transient(e):
                time.sleep(1.0)
                continue
            break
    log.warning("TeleBot send failed (%s); falling back to raw HTTP.",
                type(last_error).__name__)
    return send_message(chat_id, text,
                        business_connection_id=api_connection_id(business_connection_id),
                        reply_to_message_id=reply_to_message_id, parse_mode=parse_mode,
                        reply_markup=reply_markup)


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__
    return name in ("ApiTelegramException", "ReadTimeout", "ConnectTimeout", "ConnectionError",
                    "Timeout", "TelegramAPIError")


@contextlib.contextmanager
def typing_keepalive(bot, chat_id, business_connection_id=None, enabled: bool = True,
                     interval: float = 4.0):
    """Keep the "typing…" bubble alive while the model generates a reply.

    Telegram clears the indicator after ~5 s, so slow models need a refresher.
    """
    if not enabled:
        yield
        return
    stop = threading.Event()

    def _loop():
        while not stop.is_set():
            chat_action(bot, chat_id, "typing", business_connection_id=business_connection_id)
            stop.wait(interval)

    thread = threading.Thread(target=_loop, name="typing-keepalive", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()


def send_document(bot, chat_id, document_path, caption: str = "", reply_markup=None):
    """Send a local file to the owner (used by /export, /faq_export, …)."""
    try:
        with open(document_path, "rb") as handle:
            return bot.send_document(chat_id, handle, caption=utils.plain_text(caption)[:1024],
                                     reply_markup=reply_markup)
    except Exception as e:
        log.warning("send_document failed (%s)", type(e).__name__)
        raise


def chat_action(bot, chat_id, action, business_connection_id=None) -> None:
    """Best-effort typing indicator; never raises."""
    try:
        kwargs = {}
        business_connection_id = api_connection_id(business_connection_id)
        if business_connection_id is not None:
            kwargs["business_connection_id"] = business_connection_id
        bot.send_chat_action(chat_id, action, **kwargs)
    except Exception:
        try:
            send_chat_action(chat_id, action, business_connection_id=business_connection_id)
        except Exception:
            pass


def answer_callback(bot, callback_query_id, text=None, show_alert=False) -> None:
    """Best-effort callback acknowledgement; never raises."""
    try:
        bot.answer_callback_query(callback_query_id, text=text, show_alert=show_alert)
    except Exception:
        try:
            answer_callback_query(callback_query_id, text=text, show_alert=show_alert)
        except Exception:
            pass

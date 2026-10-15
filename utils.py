"""Shared utilities: HTML escaping, Markdown→Telegram-HTML conversion, message
splitting, sensitive-content detection, secret masking + a logging redaction
filter, per-key locks and time helpers.

This module intentionally has no project-internal dependencies so it can be
imported from anywhere without creating import cycles.
"""

from __future__ import annotations

import html
import logging
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

# --- Telegram message length limit -------------------------------------------
TELEGRAM_MAX_MESSAGE_LEN = 4096

# Optional reuse of pyTelegramBotAPI helpers. Fall back to stdlib equivalents so
# this module never hard-fails if the library layout changes between versions.
try:  # pragma: no cover - exercised indirectly
    from telebot.util import smart_split as _smart_split
except Exception:  # pragma: no cover
    _smart_split = None

try:  # pragma: no cover
    from telebot.formatting import escape_html as _tb_escape_html
except Exception:  # pragma: no cover
    _tb_escape_html = None


# =============================================================================
# HTML escaping
# =============================================================================
def escape(text) -> str:
    """Escape user-generated content for safe insertion into Telegram HTML.

    Escapes ``& < >`` (and quotes) so customer text can never inject markup.
    """
    if text is None:
        return ""
    s = str(text)
    if _tb_escape_html is not None:
        try:
            return _tb_escape_html(s)
        except Exception:
            pass
    return html.escape(s, quote=False)


# =============================================================================
# Message splitting (Telegram caps messages at 4096 chars)
# =============================================================================
def split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Split ``text`` into chunks no longer than ``limit`` characters.

    Prefers pyTelegramBotAPI's ``smart_split`` (splits on natural boundaries);
    falls back to a safe hard splitter.
    """
    if text is None:
        return [""]
    text = str(text)
    if len(text) <= limit:
        return [text] if text else [""]

    if _smart_split is not None:
        try:
            parts = list(_smart_split(text, chars_per_string=limit))
            # smart_split can, in rare cases, still produce an oversized piece;
            # defensively re-split any such piece.
            out: list[str] = []
            for p in parts:
                if len(p) <= limit:
                    out.append(p)
                else:
                    out.extend(_hard_split(p, limit))
            return out or [""]
        except Exception:
            pass
    return _hard_split(text, limit)


def _hard_split(text: str, limit: int) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)] or [""]


# =============================================================================
# Outgoing-text safety: Markdown -> Telegram HTML, with a strict whitelist
# =============================================================================
# Why this exists: replies are sent with parse_mode="HTML". Model output is
# arbitrary text, so a single bare "<" (e.g. "price < 100" or a stray "<b>")
# makes Telegram reject the whole message with "can't parse entities" and the
# customer never gets an answer. This converts common Markdown to tags
# Telegram understands, escapes everything else, and falls back to plain
# escaped text whenever the result would not be well-formed.
_ALLOWED_TAGS = (
    "b", "strong", "i", "em", "u", "s", "strike", "del", "code", "pre",
    "blockquote", "tg-spoiler", "a",
)
_ALLOWED_TAG_RE = re.compile(
    r"</?(?:" + "|".join(_ALLOWED_TAGS) + r")(?:\s+href=\"[^\"]*\")?\s*/?>",
    re.IGNORECASE,
)
_ANY_TAG_RE = re.compile(r"</?[A-Za-z][^>]{0,200}>")
_OPEN_TAG_RE = re.compile(r"<(?!/)([A-Za-z-]+)[^>]*>")
_CLOSE_TAG_RE = re.compile(r"</([A-Za-z-]+)\s*>")
# Escape "&" only when it does not already start a known entity (avoids
# double-escaping text that was escaped by the caller via utils.escape()).
_AMP_RE = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)")

_CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_+.-]*\n?(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|tg://[^\s)]+)\)")
_BOLD_STAR_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDER_RE = re.compile(r"__(.+?)__", re.DOTALL)
_STRIKE_RE = re.compile(r"~~(.+?)~~", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_ITALIC_UNDER_RE = re.compile(r"(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])")
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[ \t]{0,4}[-*+][ \t]+", re.MULTILINE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")


def _escape_amp(text: str) -> str:
    text = _AMP_RE.sub("&amp;", text)
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _escape_outside_tags(text: str) -> str:
    """Escape ``&``/``<``/``>`` but keep already-valid whitelisted tags."""
    out: list[str] = []
    pos = 0
    for match in _ALLOWED_TAG_RE.finditer(text):
        out.append(_escape_amp(text[pos:match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(_escape_amp(text[pos:]))
    return "".join(out)


def _is_balanced(html_text: str) -> bool:
    """True when every whitelisted open tag has a matching close tag in order."""
    stack: list[str] = []
    for match in re.finditer(r"</?[A-Za-z][^>]{0,200}>", html_text):
        token = match.group(0)
        closing = token.startswith("</")
        name = token[2 if closing else 1:].split()[0].rstrip("/>").lower()
        if name not in _ALLOWED_TAGS:
            continue
        if closing:
            if not stack or stack.pop() != name:
                return False
        elif not token.endswith("/>"):
            stack.append(name)
    return not stack


def strip_html(text: str) -> str:
    """Remove all tags and unescape entities (plain-text fallback)."""
    if not text:
        return ""
    return html.unescape(_ANY_TAG_RE.sub("", str(text)))


def to_telegram_html(text: str) -> str:
    """Convert model/customer text into safe Telegram HTML.

    * Markdown (``**bold**``, ``` `code` ```, ``` ```blocks``` ```, ``[link](url)``,
      ``~~strike~~``, headings, bullets) becomes the equivalent whitelisted tag.
    * Every other ``<``/``&`` is escaped, so no stray markup can break a send.
    * If the converted result is not well-formed HTML, all tags are dropped and
      the text is returned fully escaped (Telegram never sees bad entities).
    """
    if text is None:
        return ""
    src = str(text).replace("\x00", "")  # placeholders use \x00 internally
    fragments: list[str] = []

    def protect(fragment: str) -> str:
        fragments.append(fragment)
        return f"\x00{len(fragments) - 1}\x00"

    def code_block(match: re.Match) -> str:
        body = match.group(1).strip("\n")
        return protect("<pre>" + _escape_amp(body) + "</pre>")

    def inline_code(match: re.Match) -> str:
        return protect("<code>" + _escape_amp(match.group(1)) + "</code>")

    def link(match: re.Match) -> str:
        label = _escape_outside_tags(match.group(1))
        url = match.group(2).replace('"', "%22")
        return protect(f'<a href="{url}">{label}</a>')

    def wrap(tag: str, match: re.Match) -> str:
        return protect(f"<{tag}>" + _escape_outside_tags(match.group(1)) + f"</{tag}>")

    src = _CODE_BLOCK_RE.sub(code_block, src)
    src = _INLINE_CODE_RE.sub(inline_code, src)
    src = _LINK_RE.sub(link, src)
    src = _BOLD_STAR_RE.sub(lambda m: wrap("b", m), src)
    src = _BOLD_UNDER_RE.sub(lambda m: wrap("b", m), src)
    src = _STRIKE_RE.sub(lambda m: wrap("s", m), src)
    src = _ITALIC_STAR_RE.sub(lambda m: wrap("i", m), src)
    src = _ITALIC_UNDER_RE.sub(lambda m: wrap("i", m), src)

    src = _escape_outside_tags(src)

    # Line-level niceties (safe: the text is already escaped).
    src = _HEADING_RE.sub(lambda m: "<b>" + m.group(1) + "</b>", src)
    src = _BULLET_RE.sub("• ", src)
    src = _BLANK_LINES_RE.sub("\n\n", src)

    # Restore protected fragments, innermost (created earliest) last.
    for index in range(len(fragments) - 1, -1, -1):
        placeholder = f"\x00{index}\x00"
        if placeholder in src:
            src = src.replace(placeholder, fragments[index])
    # A fragment may itself contain an earlier placeholder that was already
    # substituted into src, so run one final sweep for anything still left.
    if _PLACEHOLDER_RE.search(src):
        src = _PLACEHOLDER_RE.sub(lambda m: fragments[int(m.group(1))], src)

    if not _is_balanced(src):
        return _escape_amp(strip_html(src).replace("\x00", ""))
    return src


def plain_text(text: str) -> str:
    """Best-effort plain text for logging/fallbacks (entities decoded)."""
    return html.unescape(_ANY_TAG_RE.sub("", str(text or "")))


# =============================================================================
# Per-key locks (serialize work for the same chat without blocking others)
# =============================================================================
class KeyedLock:
    """A dict of locks keyed by an arbitrary (hashable) key.

    Used to make sure two rapid messages from the *same* customer are processed
    one after another, while different customers are handled in parallel.
    """

    def __init__(self, max_keys: int = 512):
        self._guard = threading.Lock()
        self._locks: dict = {}
        self._max_keys = max_keys

    def _lock_for(self, key):
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                if len(self._locks) >= self._max_keys:
                    # Drop locks nobody is holding (bounded memory).
                    for k in [k for k, l in self._locks.items() if not l.locked()]:
                        del self._locks[k]
                        if len(self._locks) < self._max_keys:
                            break
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    @contextmanager
    def hold(self, key):
        lock = self._lock_for(key)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def locked(self, key) -> bool:
        with self._guard:
            lock = self._locks.get(key)
        return bool(lock and lock.locked())


# =============================================================================
# Sensitive-content detection (conservative heuristic, NOT a classifier)
# =============================================================================
# Category -> list of regex patterns (compiled case-insensitively below).
_SENSITIVE_PATTERNS: dict[str, list[str]] = {
    "legal": [r"\blawsuit\b", r"\battorney\b", r"\blawyer\b", r"\bsue\b",
              r"\bsuing\b", r"\bliabilit", r"\blegal action\b", r"\bcourt\b"],
    "medical": [r"\bdiagnos", r"\bprescri", r"\bdosage\b", r"\bsymptom",
                r"\bmedication\b", r"\bmedical advice\b", r"\btreatment\b"],
    "financial": [r"\binvest", r"\bfinancial advice\b", r"\btax advice\b",
                  r"\bchargeback\b", r"\bmoney back\b"],
    "refund": [r"\brefund", r"\breimburs", r"\bcancel.* (order|subscription)\b",
               r"\bdispute\b"],
    "anger_threat": [r"\bi('?| wi)ll sue\b", r"\breport you\b", r"\bscam\b",
                     r"\bfraud\b", r"\bawful\b", r"\bterrible service\b",
                     r"\bthreat", r"\blawyer up\b"],
    "personal_data": [r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",            # email
                      r"\b(?:\+?\d[\s-]?){10,}\b",                 # phone-ish
                      r"\b\d{3}-\d{2}-\d{4}\b",                    # SSN-like
                      r"\b(?:\d[ -]?){13,16}\b"],                  # card-like
    "credentials": [r"\bpassword\b", r"\bpasscode\b", r"\bone[- ]?time code\b",
                    r"\botp\b", r"\baccount access\b", r"\bapi[- ]?key\b",
                    r"\blog ?in (details|credentials)\b", r"\b2fa\b"],
}

_COMPILED_SENSITIVE = {
    cat: [re.compile(p, re.IGNORECASE) for p in pats]
    for cat, pats in _SENSITIVE_PATTERNS.items()
}


def detect_sensitive_categories(text: str) -> list[str]:
    """Return the list of sensitive categories matched in ``text`` (possibly empty)."""
    if not text:
        return []
    matched: list[str] = []
    for cat, patterns in _COMPILED_SENSITIVE.items():
        if any(p.search(text) for p in patterns):
            matched.append(cat)
    # Heuristic: shouting (lots of caps + exclamation) reads as an angry customer.
    letters = [c for c in text if c.isalpha()]
    if letters:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if len(letters) >= 12 and caps_ratio > 0.7 and "!" in text:
            if "anger_threat" not in matched:
                matched.append("anger_threat")
    return matched


def detect_sensitive(text: str) -> bool:
    """True if the message touches any sensitive category."""
    return bool(detect_sensitive_categories(text))


# =============================================================================
# Secret masking + logging redaction
# =============================================================================
def mask_token(token: str | None) -> str:
    if not token:
        return "<none>"
    token = str(token)
    return f"...{token[-4:]}" if len(token) > 4 else "****"


def mask_key(key: str | None) -> str:
    if not key:
        return "<none>"
    key = str(key)
    return f"{key[:3]}...{key[-4:]}" if len(key) > 8 else "****"


def mask_id(value) -> str:
    """Mask a numeric id (chat/user) for non-debug logs, keeping the last 3 digits."""
    if value is None:
        return "<none>"
    s = str(value)
    return f"***{s[-3:]}" if len(s) > 3 else "***"


def mask_connection(bcid: str | None) -> str:
    if not bcid:
        return "<none>"
    bcid = str(bcid)
    if len(bcid) <= 6:
        return "****"
    return f"{bcid[:4]}..{bcid[-2:]}"


class SecretRedactionFilter(logging.Filter):
    """Defense-in-depth: redact known secrets if they ever reach a log record."""

    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 8]

    def add_secret(self, secret: str | None) -> None:
        if secret and len(secret) >= 8 and secret not in self._secrets:
            self._secrets.append(secret)

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            try:
                msg = record.getMessage()
                redacted = msg
                for s in self._secrets:
                    if s in redacted:
                        redacted = redacted.replace(s, "***REDACTED***")
                if redacted != msg:
                    record.msg = redacted
                    record.args = ()
            except Exception:
                pass
        return True


# =============================================================================
# Time helpers (UTC everywhere)
# =============================================================================
def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """UTC ISO-8601 timestamp string, used for all DB ``*_at`` columns."""
    return now().isoformat()


def now_ts() -> int:
    """Epoch seconds (Telegram uses epoch seconds)."""
    return int(now().timestamp())


def future_iso(minutes: float) -> str:
    return (now() + timedelta(minutes=minutes)).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def is_expired(iso_value: str | None) -> bool:
    """True if ``iso_value`` is a timestamp in the past. None/blank => not expired."""
    dt = parse_iso(iso_value)
    if dt is None:
        return False
    return dt <= now()


def seconds_until(iso_value: str | None) -> int:
    dt = parse_iso(iso_value)
    if dt is None:
        return 0
    return max(0, int((dt - now()).total_seconds()))


def fmt_dt(iso_value: str | None) -> str:
    dt = parse_iso(iso_value)
    if dt is None:
        return "n/a"
    return dt.strftime("%Y-%m-%d %H:%M UTC")

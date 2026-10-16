"""Resources: websites, platforms, Telegram groups and channels to search/share.

The owner adds a link (or pastes text) and the assistant gets it two ways:

* **searchable content** — an http(s) page is fetched, converted to text and
  stored in the knowledge base, so retrieval can quote real facts from it;
* **shareable reference** — the title/url/short note is added to a *resources*
  block in the system prompt, so the assistant can hand the right link to the
  right person (a Telegram channel to follow, a support group, a booking page…).

Telegram links are never fetched (they need a login); they are stored as a
reference only. Fetching is deliberately conservative: http(s) only, short
timeout, capped size, and everything is best-effort — a failed fetch still keeps
the link.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import database
import i18n
import utils

log = logging.getLogger("smartel.resources")

FETCH_TIMEOUT = 8
MAX_FETCH_BYTES = 400_000
MAX_TEXT_CHARS = 60_000
MAX_TITLE_CHARS = 120
MAX_NOTES_CHARS = 300

_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
_TELEGRAM_RE = re.compile(r"^(https?://)?(t\.me|telegram\.me|telegram\.dog)/", re.IGNORECASE)
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


@dataclass
class AddedResource:
    """What happened when the owner sent a link/text."""

    resource_id: int
    kind: str            # link | telegram | text
    title: str
    url: str
    fetched: bool = False
    chars: int = 0
    kb_item_id: int | None = None


def detect_kind(url: str) -> str:
    return "telegram" if _TELEGRAM_RE.match((url or "").strip()) else "link"


def first_url(text: str) -> str:
    match = _URL_RE.search(text or "")
    return match.group(0).rstrip(".,;)") if match else ""


def is_telegram_url(url: str) -> bool:
    return bool(_TELEGRAM_RE.match((url or "").strip()))


# =============================================================================
# Fetching
# =============================================================================
def fetch_text(url: str) -> tuple[str, str]:
    """Return ``(title, text)`` for an http(s) page; ``("", "")`` on any failure."""
    target = (url or "").strip()
    if not re.match(r"^https?://", target, re.IGNORECASE):
        return "", ""
    if is_telegram_url(target):
        return "", ""
    try:
        import requests
    except Exception:                      # pragma: no cover - requests is a hard dep
        return "", ""
    try:
        response = requests.get(
            target, timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "AlfiqiAiBot/2.0 (+knowledge base)"},
            stream=True,
        )
        response.raise_for_status()
        raw = response.raw.read(MAX_FETCH_BYTES, decode_content=True) or b""
    except Exception as e:
        log.info("could not fetch %s (%s)", target, type(e).__name__)
        return "", ""

    html = raw.decode("utf-8", errors="replace")
    title_match = _TITLE_RE.search(html)
    title = utils.strip_html(title_match.group(1)).strip()[:MAX_TITLE_CHARS] if title_match else ""
    body = _TAG_RE.sub(" ", html)
    text = utils.strip_html(body)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()[:MAX_TEXT_CHARS]
    if len(text) < 40:                     # a JS-only page has no usable text
        text = ""
    return title, text


def _store_in_knowledge_base(title: str, text: str, url: str) -> int | None:
    """Feed the fetched text to the knowledge base (best effort)."""
    body = (text or "").strip()
    if len(body) < 40:
        return None
    try:
        from services import kb_service
        name = (title or url or "resource")[:MAX_TITLE_CHARS]
        header = f"Source: {url}" if url else ""
        result = kb_service.add_text(f"[Resource] {name}",
                                     f"{header}\n\n{body}".strip())
        return result.get("item_id") if isinstance(result, dict) else None
    except Exception:
        log.warning("could not add the fetched text to the knowledge base", exc_info=True)
        return None


# =============================================================================
# Adding
# =============================================================================
def add(text: str, *, title: str = "", notes: str = "") -> AddedResource | None:
    """Add a resource from owner input: a link (with optional title) or plain text.

    Accepted shapes::

        https://example.com/prices
        https://example.com | Prices page | one line note
        https://t.me/mychannel
        any text without a link -> stored as a text resource
    """
    raw = " ".join((text or "").split()).strip()
    if not raw:
        return None

    url = first_url(raw)
    if url:
        rest = " ".join(raw.replace(url, " ").split()).strip(" |,;")
        parts = [part.strip() for part in rest.split("|") if part.strip()] if "|" in rest else []
        final_title = (title or (parts[0] if parts else "")).strip()[:MAX_TITLE_CHARS]
        final_notes = (notes or (parts[1] if len(parts) > 1 else "")).strip()[:MAX_NOTES_CHARS]
        kind = detect_kind(url)
        fetched_title, page_text = fetch_text(url)
        final_title = final_title or fetched_title or url
        chars = len(page_text)
        resource_id = database.insert_resource(kind, final_title, url, final_notes, chars=chars)
        kb_item_id = _store_in_knowledge_base(final_title, page_text, url)
        log.info("resource #%s added (%s) chars=%s", resource_id, kind, chars)
        return AddedResource(resource_id=resource_id, kind=kind, title=final_title, url=url,
                             fetched=bool(page_text), chars=chars, kb_item_id=kb_item_id)

    body = raw[:MAX_TEXT_CHARS]
    final_title = (title or body.split("\n")[0])[:MAX_TITLE_CHARS]
    resource_id = database.insert_resource("text", final_title, "", notes[:MAX_NOTES_CHARS],
                                           chars=len(body))
    kb_item_id = _store_in_knowledge_base(final_title, body, "")
    return AddedResource(resource_id=resource_id, kind="text", title=final_title, url="",
                         fetched=False, chars=len(body), kb_item_id=kb_item_id)


def remove(resource_id: int) -> bool:
    return bool(database.delete_resource(resource_id))


def toggle(resource_id: int) -> bool | None:
    row = database.get_resource(resource_id)
    if row is None:
        return None
    enabled = not bool(row["enabled"])
    database.set_resource_enabled(resource_id, enabled)
    return enabled


# =============================================================================
# Prompt / UI
# =============================================================================
def prompt_block() -> str:
    """Reference list for the system prompt (links the assistant may share)."""
    if not database.get_bool("resources_enabled"):
        return ""
    rows = database.list_resources(enabled_only=True)
    if not rows:
        return ""
    lines = [
        "RESOURCES (official references — share the exact link when it answers the "
        "question, and never invent links, prices or hours that are not here):",
    ]
    for row in rows:
        title = utils.plain_text(row["title"] or "")[:MAX_TITLE_CHARS]
        url = (row["url"] or "").strip()
        notes = utils.plain_text(row["notes"] or "")[:MAX_NOTES_CHARS]
        if row["kind"] == "text":
            continue                      # text resources live in the knowledge base
        line = f"- {title}: {url}" if url else f"- {title}"
        if notes:
            line += f" ({notes})"
        lines.append(line)
    return "\n".join(lines) if len(lines) > 1 else ""


def telegram_refs() -> list:
    """Enabled Telegram groups/channels (offered as 'follow us' targets)."""
    if not database.get_bool("resources_enabled"):
        return []
    return [row for row in database.list_resources(enabled_only=True)
            if row["kind"] == "telegram"]


def label(row) -> str:
    """One-line label used by the menu buttons and lists."""
    title = (row["title"] or row["url"] or f"#{row['id']}").strip()
    return f"#{row['id']} {title}"[:60]


def describe(row) -> str:
    kind_key = {"link": "res.kind.link", "telegram": "res.kind.telegram",
                "text": "res.kind.text"}.get(row["kind"], "res.kind.link")
    lines = [i18n.t("res.row.title", id=row["id"], title=utils.escape(row["title"] or "")),
             i18n.t("res.row.kind", kind=i18n.t(kind_key))]
    if row["url"]:
        lines.append(i18n.t("res.row.url", url=utils.escape(row["url"])))
    if row["notes"]:
        lines.append(i18n.t("res.row.notes", notes=utils.escape(row["notes"])))
    if row["chars"]:
        lines.append(i18n.t("res.row.chars", count=row["chars"]))
    if not row["enabled"]:
        lines.append(i18n.t("res.row.disabled"))
    return "\n".join(lines)


def summary_lines() -> list[str]:
    rows = database.list_resources()
    if not rows:
        return []
    by_kind: dict[str, int] = {}
    for row in rows:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    return [i18n.t("res.status.summary", total=len(rows),
                   telegram=by_kind.get("telegram", 0), links=by_kind.get("link", 0))]

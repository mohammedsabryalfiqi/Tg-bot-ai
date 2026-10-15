"""FAQ / canned answers: exact and fuzzy matching of customer messages against
owner-defined question→answer pairs.

Two ways an entry is used (both configurable in /settings → FAQ):

* **Direct reply** (``faq_direct_reply``, default on): when a trigger matches
  exactly, the canned answer is sent as-is — instantly, and with zero risk of
  the model paraphrasing a price or a policy. The reply still goes through the
  approval/draft mode if that mode is on.
* **Prompt context**: near-matches are injected into the system prompt as
  *authoritative* answers, so the AI phrases them naturally.

Matching is language-agnostic and Arabic-aware: diacritics, tatweel, alef/ya/ta
variants and Arabic-Indic digits are normalised before comparison, so
«الشحـن» matches «الشحن» and «٥» matches «5».
"""

from __future__ import annotations

import logging
import re

import database

log = logging.getLogger("smartel.faq")

MAX_KEYWORDS = 400          # safety cap on the trigger string length
MIN_PHRASE_LEN = 2          # ignore 1-character triggers
DEFAULT_THRESHOLD = 0.6     # fraction of phrases needed to answer WITHOUT the model
MIN_CONTEXT_SCORE = 0.3     # weaker matches still become context for the model

# --- Arabic/Latin normalisation ------------------------------------------------
_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_LETTER_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و",
    "ة": "ه", "ﻻ": "لا", "ﻷ": "لا",
})
_PUNCT_RE = re.compile(r"[^\w\s\u0600-\u06FF]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_PHRASE_SPLIT_RE = re.compile(r"\s*(?:,|،|;|؛|\||/|\n|\r\n)\s*")


def normalize(text: str) -> str:
    """Normalise text for matching (case, Arabic variants, punctuation, digits)."""
    if not text:
        return ""
    s = str(text)
    s = _DIACRITICS_RE.sub("", s)
    s = s.translate(_ARABIC_DIGITS).translate(_PERSIAN_DIGITS).translate(_LETTER_MAP)
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def parse_triggers(keywords: str) -> list[str]:
    """Split an entry's ``keywords`` field into normalised phrases.

    Any of the phrases can trigger the entry; a phrase with several words must
    appear as a whole for that phrase to count.
    """
    if not keywords:
        return []
    phrases = []
    for part in _PHRASE_SPLIT_RE.split(str(keywords)[:MAX_KEYWORDS]):
        phrase = normalize(part)
        if len(phrase) >= MIN_PHRASE_LEN:
            phrases.append(phrase)
    # de-duplicate, keep order
    seen: set[str] = set()
    unique = []
    for phrase in phrases:
        if phrase not in seen:
            seen.add(phrase)
            unique.append(phrase)
    return unique


def _phrase_matches(phrase: str, normalized_text: str) -> bool:
    if not phrase or not normalized_text:
        return False
    if phrase.isascii():
        # ASCII phrases get word boundaries ("cat" must not match "category").
        pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
        return re.search(pattern, normalized_text) is not None
    # Arabic/CJK/... : substring match, so prefixes like "ال" still hit.
    return phrase in normalized_text


# =============================================================================
# CRUD
# =============================================================================
def add(keywords: str, answer: str, question: str = "", enabled: bool = True) -> int:
    entry_id = database.insert_faq_entry(
        keywords=(keywords or "").strip(),
        answer=(answer or "").strip(),
        question=(question or "").strip(),
        enabled=enabled,
    )
    log.info("FAQ entry %s added (%d phrases)", entry_id, len(parse_triggers(keywords)))
    return entry_id


def update(entry_id: int, **fields) -> bool:
    return database.update_faq_entry(entry_id, **fields)


def delete(entry_id: int) -> bool:
    return database.delete_faq_entry(entry_id) > 0


def clear() -> int:
    return database.clear_faq()


def list_entries(only_enabled: bool = False) -> list:
    return database.list_faq_entries(only_enabled=only_enabled)


def get(entry_id: int):
    return database.get_faq_entry(entry_id)


def count() -> int:
    return len(database.list_faq_entries())


def export_rows() -> list[dict]:
    return [
        {
            "keywords": row["keywords"],
            "question": row["question"] or "",
            "answer": row["answer"] or "",
            "enabled": bool(row["enabled"]),
        }
        for row in database.list_faq_entries()
    ]


def import_rows(rows: list[dict]) -> int:
    """Replace the FAQ with the given rows (used by /faq_import)."""
    cleaned = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        keywords = str(row.get("keywords") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if not keywords or not answer:
            continue
        cleaned.append({
            "keywords": keywords,
            "question": str(row.get("question") or "").strip(),
            "answer": answer,
            "enabled": bool(row.get("enabled", True)),
        })
    inserted = database.replace_faq_entries(cleaned)
    log.info("FAQ import replaced entries with %d rows", inserted)
    return inserted


# =============================================================================
# Matching
# =============================================================================
def _threshold() -> float:
    try:
        raw = int(database.get_int("faq_match_threshold"))
    except Exception:
        raw = int(DEFAULT_THRESHOLD * 100)
    return max(0.0, min(1.0, raw / 100.0))


class Match:
    """Result of a FAQ lookup."""

    __slots__ = ("row", "score", "matched", "total", "exact")

    def __init__(self, row, score: float, matched: int, total: int):
        self.row = row
        self.score = score
        self.matched = matched
        self.total = total
        # "exact" = every trigger phrase of the entry matched.
        self.exact = matched >= total and total >= 1

    def is_direct(self, threshold: float | None = None) -> bool:
        """Whether this match is strong enough to answer without the model."""
        if threshold is None:
            threshold = _threshold()
        return self.score >= threshold

    @property
    def answer(self) -> str:
        return (self.row["answer"] or "").strip()

    @property
    def entry_id(self) -> int:
        return int(self.row["id"])


def find_best(text: str, *, threshold: float | None = None) -> Match | None:
    """Best matching entry for ``text``, or None.

    An entry qualifies when at least ``MIN_CONTEXT_SCORE`` of its trigger phrases
    match (or it only has one phrase). ``threshold`` (0-1) is the stricter bar
    used to decide whether the answer may be sent *without* the model.
    """
    normalized = normalize(text)
    if not normalized:
        return None
    if threshold is None:
        threshold = _threshold()
    best: Match | None = None
    for row in database.list_faq_entries(only_enabled=True):
        phrases = parse_triggers(row["keywords"])
        if not phrases:
            continue
        matched = sum(1 for phrase in phrases if _phrase_matches(phrase, normalized))
        if not matched:
            continue
        score = matched / len(phrases)
        if score < MIN_CONTEXT_SCORE and len(phrases) > 1:
            continue
        candidate = Match(row, score, matched, len(phrases))
        if best is None or (candidate.score, candidate.total) > (best.score, best.total):
            best = candidate
    return best


def search(text: str, limit: int = 5, min_score: float = MIN_CONTEXT_SCORE) -> list[Match]:
    """Ranked matches (used for prompt context and the owner's /faq search)."""
    normalized = normalize(text)
    results: list[Match] = []
    if not normalized:
        return results
    for row in database.list_faq_entries(only_enabled=True):
        phrases = parse_triggers(row["keywords"])
        if not phrases:
            continue
        matched = sum(1 for phrase in phrases if _phrase_matches(phrase, normalized))
        if matched:
            score = matched / len(phrases)
            if score < min_score and len(phrases) > 1 and min_score > 0:
                continue
            results.append(Match(row, score, matched, len(phrases)))
    results.sort(key=lambda m: (m.score, m.total), reverse=True)
    return results[:limit]


def resolve(text: str) -> tuple[Match | None, bool]:
    """Decide how to use FAQ data for a customer message.

    Returns ``(match, direct_reply)``:
      * a match with ``direct_reply=True`` must be answered verbatim,
      * a match with ``direct_reply=False`` should be added to the prompt,
      * ``(None, False)`` means the FAQ has nothing relevant.
    """
    try:
        if not database.get_bool("faq_enabled"):
            return None, False
        direct_enabled = database.get_bool("faq_direct_reply")
    except Exception:
        return None, False
    match = find_best(text)
    if match is None:
        return None, False
    return match, bool(direct_enabled and match.is_direct())


def build_context_block(matches: list[Match]) -> str:
    """Prompt block with authoritative answers (used by prompt_service)."""
    if not matches:
        return ""
    lines = ["APPROVED ANSWERS (use these when relevant; never contradict them):"]
    for match in matches:
        question = (match.row["question"] or "").strip()
        header = f"- Q: {question}\n  A: {match.answer}" if question else f"- A: {match.answer}"
        lines.append(header)
    return "\n".join(lines)


def format_entry(row) -> str:
    """One-line owner-facing summary of an entry."""
    triggers = row["keywords"] or ""
    answer = (row["answer"] or "").replace("\n", " ")
    if len(answer) > 120:
        answer = answer[:117] + "…"
    hits = int(row["hits"] or 0)
    state = "" if row["enabled"] else " (disabled)"
    return f"#{row['id']}{state} · <code>{_escape(triggers)}</code> → {_escape(answer)} · used {hits}×"


def _escape(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

"""Interface text localisation (Arabic by default, English available).

Why a catalog instead of inline Arabic strings
----------------------------------------------
Every user-visible sentence lives in ``i18n/ar.py`` / ``i18n/en.py`` under a
short key. Handlers call ``i18n.t("key", param=...)``, so:

* the bot speaks Arabic out of the box (``DEFAULT_LANGUAGE``) while the whole
  English wording stays available for English-speaking owners,
* a missing translation falls back to the other language instead of crashing or
  showing a raw key,
* tests can pin a language without touching the code under test.

Resolution order for the active language
----------------------------------------
1. ``BOT_LANGUAGE`` environment variable (hard override, useful for tests and
   for container deployments),
2. the ``ui_language`` setting stored in the database (changed at runtime with
   ``/language`` or /settings → 🌐 Language),
3. ``DEFAULT_LANGUAGE``.

Placeholders use ``str.format`` syntax: ``t("biz.welcome", name="Sara")``. A
string may also use HTML tags — Telegram renders them in any language.
"""

from __future__ import annotations

import logging
import os
import time

# Imported lazily inside _stored_language() so this module stays importable in
# isolation (tests import i18n before the database is initialised).
log = logging.getLogger("smartel.i18n")

DEFAULT_LANGUAGE = "ar"

# code -> label shown in the language picker (each label in its own language)
LANGUAGES: dict[str, str] = {
    "ar": "🇪🇬 العربية",
    "en": "🇬🇧 English",
}

ENV_VAR = "BOT_LANGUAGE"
SETTING_KEY = "ui_language"

_CACHE_TTL_SECONDS = 2.0
_cache: dict[str, object] = {"at": 0.0, "value": None}


def _normalise(code: str | None) -> str | None:
    """Accept "ar", "AR", "ar-EG" and return a supported code (or None)."""
    if not code:
        return None
    candidate = str(code).strip().lower()
    for known in LANGUAGES:
        if candidate == known or candidate.startswith(f"{known}-") or candidate.startswith(f"{known}_"):
            return known
    return None


def _from_env() -> str | None:
    return _normalise(os.environ.get(ENV_VAR))


def _from_database() -> str | None:
    try:
        import database
        return _normalise(database.get_str(SETTING_KEY))
    except Exception:
        # No database yet (early startup, unit test without a DB) — not an error.
        return None


def language() -> str:
    """The language the bot currently speaks."""
    env = _from_env()
    if env is not None:
        return env
    now = time.monotonic()
    if _cache["value"] is not None and now - float(_cache["at"]) < _CACHE_TTL_SECONDS:
        return str(_cache["value"])
    resolved = _from_database() or DEFAULT_LANGUAGE
    _cache["value"] = resolved
    _cache["at"] = now
    return resolved


def set_language(code: str) -> str:
    """Persist the language choice; returns the normalised code."""
    resolved = _normalise(code) or DEFAULT_LANGUAGE
    import database
    database.set_setting(SETTING_KEY, resolved)
    invalidate_cache()
    return resolved


def invalidate_cache() -> None:
    _cache["value"] = None
    _cache["at"] = 0.0


def catalog(lang: str | None = None) -> dict[str, str]:
    """The raw key -> text mapping for a language (defaults to the active one)."""
    code = _normalise(lang) or language()
    if code == "en":
        from i18n.en import STRINGS
        return STRINGS
    from i18n.ar import STRINGS
    return STRINGS


def keys() -> set[str]:
    return set(catalog("en")) | set(catalog("ar"))


def missing_in(lang: str) -> list[str]:
    """Keys defined in the other catalog but absent from ``lang`` (test helper)."""
    other = "en" if _normalise(lang) == "ar" else "ar"
    return sorted(set(catalog(other)) - set(catalog(lang)))


def _lookup(lang: str, key: str) -> str | None:
    value = catalog(lang).get(key)
    if value is None and lang != DEFAULT_LANGUAGE:
        value = catalog(DEFAULT_LANGUAGE).get(key)
    if value is None:
        for fallback in LANGUAGES:
            value = catalog(fallback).get(key)
            if value is not None:
                break
    return value


def t(key: str, default: str | None = None, **params) -> str:
    """Translate ``key`` into the active language.

    ``default`` is returned when the key is unknown — callers that have their own
    English text (the provider registry) pass it instead of logging a warning.
    Without a default an unknown key returns the key itself (visible in logs,
    never fatal) and a formatting mistake returns the unformatted text rather
    than raising inside a Telegram handler.
    """
    value = _lookup(language(), key)
    if value is None:
        if default is not None:
            value = default
        else:
            log.warning("missing translation key: %s", key)
            return key
    if not params:
        return value
    try:
        return value.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("translation %s could not be formatted with %s", key, sorted(params))
        return value


def n(key: str, count: int, **params) -> str:
    """Translate a key choosing ``key.one`` / ``key.many`` by count.

    Arabic (and English) plural rules differ, so the two forms are written out
    explicitly in the catalogs instead of being generated.
    """
    suffix = "one" if count == 1 else "many"
    specific = f"{key}.{suffix}"
    if specific in catalog(language()) or specific in catalog(DEFAULT_LANGUAGE):
        return t(specific, count=count, **params)
    return t(key, count=count, **params)

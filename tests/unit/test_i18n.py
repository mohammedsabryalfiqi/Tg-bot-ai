"""Tests for the i18n catalogs and the language they resolve to.

The suite runs with ``BOT_LANGUAGE=en`` (see ``conftest.clean_env``) because the
existing assertions quote the English wording; these tests cover the Arabic
default, the override order and the safety net around unknown keys.
"""

from __future__ import annotations

import re

import pytest

import i18n
from services import providers

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text or ""))


# --- catalog integrity --------------------------------------------------------
def test_both_catalogs_define_the_same_keys():
    english, arabic = i18n.catalog("en"), i18n.catalog("ar")
    assert i18n.missing_in("ar") == []
    assert i18n.missing_in("en") == []
    assert len(english) == len(arabic) > 400


def test_placeholders_match_across_languages():
    english, arabic = i18n.catalog("en"), i18n.catalog("ar")
    mismatched = {
        key: (sorted(_placeholders(english[key])), sorted(_placeholders(arabic[key])))
        for key in english
        if _placeholders(english[key]) != _placeholders(arabic[key])
    }
    assert mismatched == {}


def test_arabic_catalog_is_actually_arabic():
    english, arabic = i18n.catalog("en"), i18n.catalog("ar")
    translated = [key for key, value in english.items() if arabic[key] != value]
    # Proper nouns, URLs and model names are allowed to be identical, but the
    # overwhelming majority of the interface must differ between the languages.
    assert len(translated) > 0.75 * len(english)
    assert any("\u0600" <= ch <= "\u06ff" for key in translated
               for ch in arabic[key]), "no Arabic characters found"


def test_html_safety_is_preserved():
    """Every Telegram HTML tag used in English must survive in Arabic (broken
    tags make Telegram reject the whole message)."""
    english, arabic = i18n.catalog("en"), i18n.catalog("ar")
    tag = re.compile(r"</?[a-z]+>")
    for key in english:
        assert set(tag.findall(english[key])) == set(tag.findall(arabic[key])), key


# --- resolution order ---------------------------------------------------------
def test_default_language_is_arabic():
    assert i18n.DEFAULT_LANGUAGE == "ar"


def test_environment_variable_wins(db, monkeypatch):
    monkeypatch.setenv("BOT_LANGUAGE", "en")
    i18n.invalidate_cache()
    assert i18n.language() == "en"

    monkeypatch.setenv("BOT_LANGUAGE", "ar-EG")     # regional tag is accepted
    i18n.invalidate_cache()
    assert i18n.language() == "ar"

    monkeypatch.setenv("BOT_LANGUAGE", "klingon")   # unknown -> stored value
    i18n.invalidate_cache()
    assert i18n.language() in i18n.LANGUAGES


def test_stored_setting_is_used_when_the_environment_is_silent(db, monkeypatch):
    monkeypatch.delenv("BOT_LANGUAGE", raising=False)
    i18n.set_language("ar")
    assert db.get_str("ui_language") == "ar"
    assert i18n.t("kb.list.empty") == i18n.catalog("ar")["kb.list.empty"]

    i18n.set_language("en")
    assert db.get_str("ui_language") == "en"
    assert i18n.t("kb.list.empty") == i18n.catalog("en")["kb.list.empty"]


def test_set_language_normalises_and_persists(db):
    assert i18n.set_language("EN") == "en"
    assert db.get_str("ui_language") == "en"
    assert i18n.set_language("nope") == i18n.DEFAULT_LANGUAGE
    assert db.get_str("ui_language") == i18n.DEFAULT_LANGUAGE


def test_without_a_database_the_default_language_is_used(monkeypatch):
    monkeypatch.delenv("BOT_LANGUAGE", raising=False)
    i18n.invalidate_cache()
    assert i18n.language() == i18n.DEFAULT_LANGUAGE
    assert i18n.t("own.help").strip()


# --- safety net ---------------------------------------------------------------
def test_unknown_key_returns_the_key():
    assert i18n.t("no.such.key") == "no.such.key"


def test_default_is_returned_for_unknown_keys():
    assert i18n.t("no.such.key", default="fallback") == "fallback"


def test_unknown_key_still_formats_its_default():
    assert i18n.t("no.such.key", default="{name}!", name="سارة") == "سارة!"


def test_missing_format_parameter_returns_the_raw_text():
    raw = i18n.t("own.toggle")          # needs {label} and {state}
    assert "{label}" in raw or "{state}" in raw


def test_plural_helper_falls_back_to_the_base_key():
    assert i18n.n("no.such.key", 3) == "no.such.key"


# --- provider registry --------------------------------------------------------
def test_provider_texts_follow_the_language(monkeypatch):
    monkeypatch.setenv("BOT_LANGUAGE", "en")
    i18n.invalidate_cache()
    english_docs = providers.get("groq").docs
    english_label = providers.get("groq").label

    monkeypatch.setenv("BOT_LANGUAGE", "ar")
    i18n.invalidate_cache()
    provider = providers.get("groq")
    assert provider.label != english_label
    assert provider.docs != english_docs
    assert "Groq" in provider.label          # the brand name is kept
    assert any("\u0600" <= ch <= "\u06ff" for ch in provider.docs)


def test_every_provider_has_localised_texts():
    english = i18n.catalog("en")
    for provider in providers.ordered():
        assert f"prov.{provider.id}.label" in english
        assert f"prov.{provider.id}.docs" in english

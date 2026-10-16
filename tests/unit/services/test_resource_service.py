"""Tests for services/resource_service.py — what the assistant may look things up in.

The owner adds a website, a platform, a Telegram group or raw text; the page is
fetched into the knowledge base and the reference list is injected into the
system prompt so the assistant can hand out *real* links instead of inventing
them. Fetching is always stubbed here — the tests must never touch the network.
"""

from __future__ import annotations

import pytest

from services import resource_service


@pytest.fixture(autouse=True)
def no_embeddings(monkeypatch):
    """Never call the embedding API from a unit test (that would be slow)."""
    monkeypatch.setattr("services.embedding_service.embed_texts", lambda chunks: [])


# Long enough to be worth storing in the knowledge base (there is a 40-char floor).
_PAGE = "الأسعار هنا: 500 جنيه للقطعة، والتوصيل مجاني داخل دمياط خلال يومين."


def _stub_fetch(monkeypatch, title="صفحة الأسعار", text=_PAGE):
    monkeypatch.setattr(resource_service, "fetch_text",
                        lambda url: (title, text) if url.startswith("http") else ("", ""))


# --- detection ----------------------------------------------------------------
def test_kind_detection(db):
    assert resource_service.detect_kind("https://t.me/mychannel") == "telegram"
    assert resource_service.detect_kind("https://example.com/prices") == "link"
    assert resource_service.is_telegram_url("http://t.me/group") is True
    assert resource_service.is_telegram_url("https://example.com") is False


def test_first_url_picks_the_link_and_strips_punctuation(db):
    assert resource_service.first_url("شوف https://example.com/a.") == "https://example.com/a"
    assert resource_service.first_url("مفيش لينك") == ""


# --- adding -------------------------------------------------------------------
def test_a_plain_link_becomes_a_fetched_resource(db, monkeypatch):
    _stub_fetch(monkeypatch)
    added = resource_service.add("https://example.com/prices")
    assert added.kind == "link" and added.fetched is True
    assert added.title == "صفحة الأسعار"
    assert added.chars == len(_PAGE)
    assert added.kb_item_id                       # the text went into the knowledge base
    assert db.list_kb_items()


def test_a_link_with_title_and_note_is_parsed(db, monkeypatch):
    _stub_fetch(monkeypatch)
    added = resource_service.add("https://example.com | صفحة الأسعار | محدثة كل شهر")
    assert added.title == "صفحة الأسعار"
    row = db.list_resources()[0]
    assert row["notes"] == "محددة كل شهر" or row["notes"] == "محدثة كل شهر"
    assert row["url"] == "https://example.com"


def test_a_telegram_link_is_kept_without_fetching(db):
    added = resource_service.add("https://t.me/mychannel")
    assert added.kind == "telegram" and added.fetched is False
    assert added.chars == 0


def test_plain_text_is_stored_as_a_text_resource(db, monkeypatch):
    _stub_fetch(monkeypatch)
    added = resource_service.add("شروط الاستبدال: خلال 14 يوم بفاتورة")
    assert added.kind == "text"
    assert db.count_resources() == 1


def test_an_unreachable_page_is_still_recorded(db, monkeypatch):
    """No network? The reference is kept — the link is useful as it is."""
    monkeypatch.setattr(resource_service, "fetch_text", lambda url: ("", ""))
    added = resource_service.add("https://offline.example.com")
    assert added.fetched is False and added.chars == 0
    assert added.kb_item_id is None


def test_short_text_resources_do_not_pollute_the_knowledge_base(db, monkeypatch):
    monkeypatch.setattr(resource_service, "fetch_text", lambda url: ("", ""))
    assert resource_service.add("رابط: https://example.com").kb_item_id is None


def test_adding_nothing_returns_none(db):
    assert resource_service.add("   ") is None


# --- lifecycle ----------------------------------------------------------------
def test_toggle_and_remove(db, monkeypatch):
    _stub_fetch(monkeypatch)
    added = resource_service.add("https://example.com/a")
    assert resource_service.toggle(added.resource_id) is False
    assert db.list_resources(enabled_only=True) == []
    assert resource_service.toggle(added.resource_id) is True
    assert resource_service.remove(added.resource_id) is True
    assert resource_service.toggle(9999) is None
    assert resource_service.remove(9999) is False


# --- prompt integration -------------------------------------------------------
def test_prompt_block_lists_enabled_links_only(db, monkeypatch):
    _stub_fetch(monkeypatch)
    resource_service.add("https://example.com/prices | صفحة الأسعار")
    resource_service.add("https://t.me/mychannel")

    block = resource_service.prompt_block()
    assert "https://example.com/prices" in block
    assert "https://t.me/mychannel" in block
    assert "RESOURCES" in block

    db.set_setting("resources_enabled", False)
    assert resource_service.prompt_block() == ""

    db.set_setting("resources_enabled", True)
    rows = db.list_resources()
    resource_service.toggle(rows[0]["id"])
    resource_service.toggle(rows[1]["id"])
    assert resource_service.prompt_block() == ""


def test_telegram_refs_expose_only_telegram_resources(db, monkeypatch):
    _stub_fetch(monkeypatch)
    resource_service.add("https://example.com")
    assert resource_service.telegram_refs() == []
    resource_service.add("https://t.me/mychannel")
    assert [row["url"] for row in resource_service.telegram_refs()] == ["https://t.me/mychannel"]


def test_describe_and_summary_lines_are_human_readable(db, monkeypatch):
    _stub_fetch(monkeypatch)
    added = resource_service.add("https://example.com/x | صفحة")
    row = db.list_resources()[0]
    described = resource_service.describe(row)
    assert explained_title(described, added.title)
    assert resource_service.summary_lines()


def explained_title(described: str, title: str) -> bool:
    return title in described

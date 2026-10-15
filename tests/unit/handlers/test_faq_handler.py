"""Tests for handlers/faq.py: the quick-answer menu, the two-step add flow,
listing/deleting, search, export and import."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from handlers import faq as faq_handler
from services import faq_service


def _last_message():
    import handlers
    return handlers.bot.send_message.call_args.args[1]


@pytest.fixture
def env(db, stub_bot):
    return db


# --- menu --------------------------------------------------------------------
def test_menu_shows_statistics(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_service.add("price", "500")
    faq_handler.cmd_menu(make_message())
    text = _last_message()
    assert "Quick answers" in text
    assert "Entries: <b>1</b>" in text


def test_menu_callback_replaces_the_message(env, make_call, mocker):
    import handlers
    faq_handler.on_callback(make_call(data="faq:menu"))
    assert "Quick answers" in handlers.bot.edit_message_text.call_args.args[0]


# --- one-line add ------------------------------------------------------------
def test_add_one_liner_creates_the_entry(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_handler.cmd_add(make_message(text="/faq_add سعر, price :: يبدأ من 500 جنيه"))
    entries = faq_service.list_entries()
    assert len(entries) == 1
    assert entries[0]["keywords"] == "سعر, price"
    assert entries[0]["answer"] == "يبدأ من 500 جنيه"
    assert "Quick answer #1 saved" in _last_message()


def test_add_requires_a_separator_to_use_the_one_liner(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_handler.cmd_add(make_message(text="/faq_add price"))
    assert env.get_owner_pending_input(12345)["kind"] == "faq_keywords"


def test_add_rejects_too_short_triggers(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_handler.cmd_add(make_message(text="/faq_add a :: answer"))
    assert faq_service.count() == 0
    assert "too short" in _last_message()


def test_add_rejects_empty_answer(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_handler.cmd_add(make_message(text="/faq_add price ::   "))
    assert faq_service.count() == 0


# --- two-step flow -----------------------------------------------------------
def test_two_step_flow(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_handler.apply_pending(make_message(text="سعر, price"), "faq_keywords", {})
    state = env.get_owner_pending_input(12345)
    assert state["kind"] == "faq_answer"
    assert state["context"]["keywords"] == "سعر, price"

    faq_handler.apply_pending(make_message(text="يبدأ من 500 جنيه"), "faq_answer", state["context"])
    assert faq_service.find_best("كام السعر؟") is not None
    assert env.get_owner_pending_input(12345) is None


def test_two_step_flow_rejects_short_triggers(env, make_message):
    faq_handler.apply_pending(make_message(text="a"), "faq_keywords", {})
    assert env.get_owner_pending_input(12345) is None
    assert faq_service.count() == 0


def test_two_step_flow_rejects_empty_answer(env, make_message):
    faq_handler.apply_pending(make_message(text=""), "faq_answer", {"keywords": "price"})
    assert faq_service.count() == 0


# --- list / delete -----------------------------------------------------------
def test_list_shows_entries_and_delete_buttons(env, make_message):
    import handlers
    faq_service.add("price", "500")
    faq_handler.send_list(12345, 0)
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "faq:del:1:0" in data


def test_list_when_empty(env):
    faq_handler.send_list(12345, 0)
    assert "No quick answers yet" in _last_message()


def test_delete_callback_removes_the_entry(env, make_call):
    faq_service.add("price", "500")
    faq_handler.on_callback(make_call(data="faq:del:1:0"))
    assert faq_service.count() == 0


def test_cmd_delete(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_service.add("price", "500")
    faq_handler.cmd_delete(make_message(text="/faq_del 1"))
    assert faq_service.count() == 0


def test_cmd_delete_validates_input(env, make_message):
    faq_handler.cmd_delete(make_message(text="/faq_del abc"))
    assert "Usage" in _last_message()


def test_clear_requires_confirmation(env, make_message, mocker):
    import handlers
    mocker.patch("telegram_api.send_reply")
    faq_service.add("price", "500")
    faq_handler.cmd_clear(make_message())
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert "confirm:yes:faqclear" in data
    assert faq_service.count() == 1  # nothing deleted yet


# --- search ------------------------------------------------------------------
def test_search_reports_matches(env, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    faq_service.add("price, سعر", "500")
    faq_handler._do_search(12345, "كم السعر")
    assert "Matches for" in _last_message()


def test_search_reports_no_matches(env):
    faq_service.add("price", "500")
    faq_handler._do_search(12345, "hello there")
    assert "would be answered by the AI" in _last_message()


# --- export / import ---------------------------------------------------------
def test_export_sends_a_json_document(env, mocker):
    sent = mocker.patch("telegram_api.send_document")
    faq_service.add("price", "500", question="How much?")
    faq_handler.export_to_chat(12345)
    path = sent.call_args.args[2]
    assert sent.call_args.kwargs["caption"].startswith("Quick answers export")


def test_export_without_entries(env):
    faq_handler.export_to_chat(12345)
    assert "nothing to export" in _last_message()


def test_import_from_document(env, make_message, mocker):
    payload = {"type": "smartel-faq", "entries": [{"keywords": "price", "answer": "500"}]}
    mocker.patch("telegram_api.download_file_bytes", return_value=json.dumps(payload).encode())
    faq_service.add("old", "old")
    faq_handler.apply_pending(
        make_message(document=type("Doc", (), {"file_id": "f1"})()), "faq_import", {}
    )
    assert [e["keywords"] for e in faq_service.list_entries()] == ["price"]
    assert "Imported 1 quick answers" in _last_message()


def test_import_without_document(env, make_message):
    faq_handler.apply_pending(make_message(document=None), "faq_import", {})
    assert "not a JSON file" in _last_message()


def test_import_with_broken_json(env, make_message, mocker):
    mocker.patch("telegram_api.download_file_bytes", return_value=b"{not json")
    faq_handler.apply_pending(
        make_message(document=type("Doc", (), {"file_id": "f1"})()), "faq_import", {}
    )
    assert "Could not read that file" in _last_message()


def test_import_with_unexpected_structure(env, make_message, mocker):
    mocker.patch("telegram_api.download_file_bytes", return_value=b'{"entries": "nope"}')
    faq_handler.apply_pending(
        make_message(document=type("Doc", (), {"file_id": "f1"})()), "faq_import", {}
    )
    assert "Unexpected JSON structure" in _last_message()

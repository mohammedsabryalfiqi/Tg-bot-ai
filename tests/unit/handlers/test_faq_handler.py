"""Tests for handlers/faq.py: the quick-answer manager (menu, one-line and
two-step creation, listing, deleting, testing matches, import/export)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import database
import handlers
import telegram_api
from handlers import faq as faq_handler
from services import faq_service

OWNER_CHAT = 12345


def _msg(text: str = "", message_id: int = 9001, chat_id: int = OWNER_CHAT, **kw):
    """Duck-typed message: owner DM by default, `document=` for imports."""
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=OWNER_CHAT, first_name="Owner", last_name=None,
                                  username=None),
        message_id=message_id,
        text=text,
        caption=None,
        content_type="text",
        business_connection_id=None,
        sender_business_bot=None,
        **kw,
    )


def _document(file_id: str = "file1", file_name: str = "faq.json", size: int = 100):
    return SimpleNamespace(file_id=file_id, file_name=file_name, file_size=size)


def _sent(chat_id: int = OWNER_CHAT) -> list[str]:
    return [call.args[1] for call in handlers.bot.send_message.call_args_list
            if call.args[0] == chat_id]


@pytest.fixture
def env(db, stub_bot):
    return db


# --- menu --------------------------------------------------------------------
def test_menu_shows_stats_and_examples(env):
    faq_service.add("سعر, price", "500 EGP")
    faq_handler.cmd_menu(_msg("/faq"))
    text = _sent()[0]
    assert "Quick answers" in text
    assert "Entries: <b>1</b>" in text
    assert "سعر" in text


def test_menu_has_buttons(env):
    faq_handler.cmd_menu(_msg("/faq"))
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("faq:") for entry in data)


# --- one-line creation -------------------------------------------------------
def test_one_line_creation(env):
    faq_handler.cmd_add(_msg("/faq_add سعر, price :: prices start at 500"))
    entry = faq_service.list_entries()[0]
    assert entry["keywords"] == "سعر, price"
    assert entry["answer"] == "prices start at 500"
    assert "saved" in _sent()[0].lower()


def test_one_line_creation_rejects_short_triggers(env):
    faq_handler.cmd_add(_msg("/faq_add a :: answer"))
    assert faq_service.count() == 0
    assert "too short" in _sent()[0]


def test_one_line_creation_rejects_an_empty_answer(env):
    faq_handler.cmd_add(_msg("/faq_add price ::   "))
    assert faq_service.count() == 0
    assert "answer" in _sent()[0].lower()


def test_add_without_separator_starts_the_two_step_flow(env):
    faq_handler.cmd_add(_msg("/faq_add"))
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "faq_keywords"
    assert "step 1/2" in _sent()[0]


# --- two-step flow -----------------------------------------------------------
def test_two_step_flow_creates_the_entry(env):
    faq_handler.apply_pending(_msg("توصيل, delivery"), "faq_keywords", {})
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "faq_answer"

    faq_handler.apply_pending(_msg("التوصيل خلال 3 أيام"), "faq_answer",
                              {"keywords": "توصيل, delivery"})
    assert database.get_owner_pending_input(OWNER_CHAT) is None
    assert faq_service.count() == 1
    assert "saved" in _sent()[-1].lower()


def test_two_step_flow_rejects_bad_triggers(env):
    faq_handler.apply_pending(_msg("x"), "faq_keywords", {})
    assert faq_service.count() == 0
    assert database.get_owner_pending_input(OWNER_CHAT) is None


def test_two_step_flow_rejects_an_empty_answer(env):
    faq_handler.apply_pending(_msg("   "), "faq_answer", {"keywords": "price"})
    assert faq_service.count() == 0


# --- list / delete -----------------------------------------------------------
def test_list_shows_entries_with_delete_buttons(env):
    faq_service.add("price", "500")
    faq_handler.send_list(OWNER_CHAT, 0)
    assert "price" in _sent()[0]
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("faq:del:") for entry in data)


def test_empty_list_is_explained(env):
    faq_handler.send_list(OWNER_CHAT, 0)
    assert "No quick answers" in _sent()[0]


def test_delete_command(env):
    entry_id = faq_service.add("price", "500")
    faq_handler.cmd_delete(_msg(f"/faq_del {entry_id}"))
    assert faq_service.count() == 0
    assert "Deleted" in _sent()[0]


def test_delete_command_with_a_bad_id(env):
    faq_handler.cmd_delete(_msg("/faq_del abc"))
    assert "Usage" in _sent()[0]


def test_delete_callback(env, make_call):
    entry_id = faq_service.add("price", "500")
    faq_handler.on_callback(make_call(data=f"faq:del:{entry_id}:0"))
    assert faq_service.count() == 0


def test_clear_asks_for_confirmation(env):
    faq_service.add("price", "500")
    faq_handler.cmd_clear(_msg("/faq_clear"))
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("confirm:") for entry in data)
    assert faq_service.count() == 1  # not deleted yet


# --- search ------------------------------------------------------------------
def test_search_with_a_query_reports_a_match(env):
    faq_service.add("price", "500")
    faq_handler.cmd_search(_msg("/faq_search what is the price?"))
    assert "price" in _sent()[0]


def test_search_without_a_query_asks_for_one(env):
    faq_handler.cmd_search(_msg("/faq_search"))
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "faq_search"


def test_search_without_a_match_says_the_ai_handles_it(env):
    faq_service.add("price", "500")
    faq_handler._do_search(OWNER_CHAT, "do you deliver to Aswan?")
    assert "AI" in _sent()[0]


# --- import / export ---------------------------------------------------------
def test_export_sends_a_json_file(env, mocker):
    captured = {}
    mocker.patch("telegram_api.send_document",
                 side_effect=lambda bot, chat, path, **kw: captured.update(
                     payload=json.loads(path.read_text(encoding="utf-8"))))
    faq_service.add("سعر", "500", question="How much?")
    faq_handler.export_to_chat(OWNER_CHAT)
    assert captured["payload"]["type"] == "smartel-faq"
    assert captured["payload"]["entries"][0]["keywords"] == "سعر"


def test_export_without_entries_is_reported(env):
    faq_handler.export_to_chat(OWNER_CHAT)
    assert "Nothing to export" in _sent()[0] or "nothing to export" in _sent()[0]


def test_import_replaces_the_entries(env, mocker):
    payload = {"type": "smartel-faq", "version": 1,
               "entries": [{"keywords": "delivery", "answer": "3 days"}]}
    mocker.patch("telegram_api.download_file_bytes",
                 return_value=json.dumps(payload).encode())
    faq_service.add("old", "old")
    faq_handler.apply_pending(_msg(document=_document()), "faq_import", {})
    assert faq_service.count() == 1
    assert faq_service.list_entries()[0]["keywords"] == "delivery"


def test_import_without_a_document(env):
    faq_handler.apply_pending(_msg(), "faq_import", {})
    assert "not a JSON file" in _sent()[0]


def test_import_with_broken_json(env, mocker):
    mocker.patch("telegram_api.download_file_bytes", return_value=b"{not json")
    faq_handler.apply_pending(_msg(document=_document()), "faq_import", {})
    assert "Could not read that file" in _sent()[0]


def test_import_with_an_unexpected_structure(env, mocker):
    mocker.patch("telegram_api.download_file_bytes", return_value=b'{"entries": "nope"}')
    faq_handler.apply_pending(_msg(document=_document()), "faq_import", {})
    assert "Unexpected JSON structure" in _sent()[0]


def test_import_with_a_download_failure(env, mocker):
    mocker.patch("telegram_api.download_file_bytes",
                 side_effect=telegram_api.TelegramAPIError("too large"))
    faq_handler.apply_pending(_msg(document=_document()), "faq_import", {})
    assert "Could not read that file" in _sent()[0]


# --- callbacks ---------------------------------------------------------------
def test_menu_callback_edits_the_message(env, make_call):
    faq_handler.on_callback(make_call(data="faq:menu"))
    assert "Quick answers" in handlers.bot.edit_message_text.call_args.args[0]


def test_add_callback_starts_the_flow(env, make_call):
    faq_handler.on_callback(make_call(data="faq:add"))
    assert database.get_owner_pending_input(OWNER_CHAT)["kind"] == "faq_keywords"


def test_list_callback_paginates(env, make_call):
    for index in range(faq_handler.PER_PAGE + 2):
        faq_service.add(f"kw{index}", f"answer {index}")
    faq_handler.on_callback(make_call(data=f"faq:list:{faq_handler.PER_PAGE}"))
    assert handlers.bot.answer_callback_query.called


def test_clear_callback_confirms(env, make_call):
    faq_service.add("price", "500")
    faq_handler.on_callback(make_call(data="faq:clear"))
    markup = handlers.bot.send_message.call_args.kwargs["reply_markup"]
    data = [b.callback_data for row in markup.keyboard for b in row]
    assert any(entry.startswith("confirm:") for entry in data)
    assert faq_service.count() == 1  # the confirmation is still required


def test_close_callback(env, make_call):
    faq_handler.on_callback(make_call(data="faq:close"))
    handlers.bot.delete_message.assert_called_once()

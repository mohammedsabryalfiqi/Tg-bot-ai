"""Integration contracts between layers.

The unit tests cover behaviour inside a module; this module pins the *seams*
between them — the functions one layer calls on another (business_service,
memory_service, telegram file download, the approval router's pending-input
dispatch, and `get_all_settings`). A silent signature drift here breaks the live
bot without failing any single-module test.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import database
import handlers
import telegram_api
import utils
from handlers import approvals, owner_tools
from services import business_service, memory_service, rate_limit_service


# --- business_service --------------------------------------------------------
def _bc(bcid="bc1", user_id=999, enabled=True, can_reply=True, rights=None):
    bc = SimpleNamespace(id=bcid, is_enabled=enabled, can_reply=can_reply,
                         user=SimpleNamespace(id=user_id))
    if rights is not None:
        bc.rights = rights
    return bc


def test_upsert_connection_stores_the_owner_account(db):
    business_service.upsert_connection(_bc())
    row = business_service.get_connection("bc1")
    assert row["business_user_id"] == 999
    assert business_service.get_owner_user_id("bc1") == 999
    assert business_service.can_reply("bc1") is True


def test_upsert_connection_prefers_rights_can_reply(db):
    business_service.upsert_connection(_bc(can_reply=True, rights=SimpleNamespace(can_reply=False)))
    assert business_service.can_reply("bc1") is False


def test_set_enabled_roundtrip(db):
    business_service.upsert_connection(_bc())
    business_service.set_enabled("bc1", False)
    assert business_service.can_reply("bc1") is False
    assert business_service.get_connection("bc1")["is_enabled"] == 0


def test_fetch_and_store_via_raw_parses_telegram_payload(db, mocker):
    mocker.patch("telegram_api.get_business_connection", return_value={
        "id": "bc7",
        "user": {"id": 4242, "first_name": "Boss"},
        "is_enabled": True,
        "rights": {"can_reply": True},
    })
    row = business_service.fetch_and_store_via_raw("bc7")
    assert row["business_user_id"] == 4242
    assert row["can_reply"] == 1


def test_fetch_and_store_via_raw_survives_an_api_error(db, mocker):
    mocker.patch("telegram_api.get_business_connection", side_effect=RuntimeError("boom"))
    assert business_service.fetch_and_store_via_raw("bc7") is None
    assert business_service.get_connection("bc7") is None


def test_fetch_and_store_via_raw_with_no_result(db, mocker):
    mocker.patch("telegram_api.get_business_connection", return_value=None)
    assert business_service.fetch_and_store_via_raw("bc7") is None


def test_upsert_customer_from_message_keeps_the_display_name(db, make_message):
    business_service.upsert_connection(_bc())
    business_service.upsert_customer_from_message(
        "bc1", make_message(chat_id=5, user_id=10, first_name="Mona", last_name="Ali",
                            username="mona"))
    assert business_service.customer_display_name("bc1", 5) == "Mona Ali (@mona)"
    assert business_service.find_bcid_for_chat(5) == "bc1"


def test_customer_display_name_without_a_row(db, fake_config=None):
    assert business_service.customer_display_name("bc1", 77) == "chat 77"


def test_get_status_reports_the_live_switches(db):
    db.set_setting("auto_reply_enabled", True)
    business_service.upsert_connection(_bc())
    status = business_service.get_status()
    assert status["auto_reply_enabled"] is True
    assert status["model"]  # whatever the active model setting is
    assert len(status["connections"]) == 1
    assert status["kb"] == {"items": 0, "chunks": 0}


def test_pause_and_resume_roundtrip(db):
    business_service.pause_chat("bc1", 5, reason="manual_pause", minutes=None)
    assert business_service.is_chat_paused("bc1", 5) is True
    assert business_service.resume_chat("bc1", 5) is True
    assert business_service.is_chat_paused("bc1", 5) is False
    assert business_service.resume_chat("bc1", 5) is False  # nothing to resume


# --- memory_service ----------------------------------------------------------
def test_append_exchange_is_visible_to_get_recent(db):
    memory_service.append_exchange("bc1", 5, "how much?", "500 EGP")
    rows = memory_service.get_recent("bc1", 5, limit=10)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["content"] == "500 EGP"


def test_clear_all_memory_wipes_every_chat(db):
    memory_service.append_exchange("bc1", 5, "a", "b")
    memory_service.append_exchange("bc2", 6, "c", "d")
    assert memory_service.clear_all() >= 4
    assert memory_service.get_recent("bc1", 5, limit=10) == []
    assert memory_service.get_recent("bc2", 6, limit=10) == []


# --- rate_limit_service ------------------------------------------------------
def test_enforce_allows_up_to_the_limit_then_pauses(db):
    db.set_setting("max_messages_per_customer_per_hour", 2)
    database.insert_message("bc1", 5, None, "in", "user", "hi")          # 1 of 2
    database.insert_message("bc1", 5, None, "in", "user", "hi")          # 2 of 2
    at_limit = rate_limit_service.enforce("bc1", 5)
    assert at_limit.allowed is True
    assert (at_limit.used, at_limit.limit, at_limit.remaining) == (2, 2, 0)
    assert business_service.is_chat_paused("bc1", 5) is False

    database.insert_message("bc1", 5, None, "in", "user", "hi again")    # 3 > 2
    over = rate_limit_service.enforce("bc1", 5)
    assert over.allowed is False
    assert over.used == 3
    assert business_service.is_chat_paused("bc1", 5) is True


# --- telegram_api.download_file_bytes ---------------------------------------
def test_download_file_bytes_streams_the_file(monkeypatch):
    telegram_api.init("123456789:" + "A" * 35)
    monkeypatch.setattr(telegram_api, "get_file", lambda file_id: {"file_path": "docs/x.txt"})

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=0):
            yield b"hello "
            yield b"world"

    monkeypatch.setattr(telegram_api.requests, "get", lambda *a, **k: Resp())
    assert telegram_api.download_file_bytes("file1") == b"hello world"


def test_download_file_bytes_refuses_oversized_files(monkeypatch):
    telegram_api.init("123456789:" + "A" * 35)
    monkeypatch.setattr(
        telegram_api, "get_file",
        lambda file_id: {"file_path": "big.bin", "file_size": 30 * 1024 * 1024},
    )
    with pytest.raises(telegram_api.TelegramAPIError):
        telegram_api.download_file_bytes("file1")


def test_download_file_bytes_without_a_path(monkeypatch):
    telegram_api.init("123456789:" + "A" * 35)
    monkeypatch.setattr(telegram_api, "get_file", lambda file_id: {})
    with pytest.raises(telegram_api.TelegramAPIError):
        telegram_api.download_file_bytes("file1")


def test_download_file_bytes_retries_transient_errors(monkeypatch):
    telegram_api.init("123456789:" + "A" * 35)
    monkeypatch.setattr(telegram_api, "get_file", lambda file_id: {"file_path": "x"})
    calls = {"n": 0}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=0):
            return iter([b"ok"])

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise telegram_api.requests.RequestException("flaky")
        return Resp()

    monkeypatch.setattr(telegram_api.requests, "get", fake_get)
    assert telegram_api.download_file_bytes("file1") == b"ok"
    assert calls["n"] == 2


# --- pending-input router ----------------------------------------------------
def test_router_sends_reply_to_chat_input(db, stub_bot, make_message, mocker):
    """`/reply <chat>` parks the chat; the router hands the text to owner_tools."""
    send = mocker.patch("telegram_api.send_reply")
    db.upsert_business_connection("bc1", 999, True, True)
    db.set_setting("owner_takeover_pause_minutes", 30)

    database.set_owner_pending_input(12345, "reply_to_chat", {"chat_id": 5}, 15)
    approvals.on_owner_pending_input(make_message(user_id=12345, text="On my way"))

    assert send.call_args.args[1] == 5
    assert send.call_args.args[2] == "On my way"
    assert send.call_args.kwargs["business_connection_id"] == "bc1"
    # Recorded as an owner message and the chat is paused (takeover).
    rows = database.get_recent_messages("bc1", 5, limit=5)
    assert [r["role"] for r in rows] == ["owner"]
    assert business_service.is_chat_paused("bc1", 5) is True
    assert database.get_owner_pending_input(12345) is None


def test_router_is_silent_when_no_input_is_pending(db, stub_bot, make_message, mocker):
    send = mocker.patch("telegram_api.send_reply")
    approvals.on_owner_pending_input(make_message(user_id=12345, text="hello?"))
    send.assert_not_called()


def test_unknown_pending_kind_is_cleared(db, stub_bot, make_message):
    database.set_owner_pending_input(12345, "totally_unknown", {}, 15)
    approvals.on_owner_pending_input(make_message(user_id=12345, text="x"))
    assert database.get_owner_pending_input(12345) is None


def test_cmd_reply_without_text_parks_the_chat(db, stub_bot, make_message):
    db.set_setting("owner_takeover_pause_minutes", 30)
    db.upsert_business_connection("bc1", 999, True, True)
    owner_tools.cmd_reply(make_message(user_id=12345, text="/reply 5"))
    state = database.get_owner_pending_input(12345)
    assert state["kind"] == "reply_to_chat"
    assert state["context"]["chat_id"] == 5
    assert "Send the message" in stub_bot.send_message.call_args.args[1]


def test_owner_reply_rejects_unknown_chats(db, stub_bot, make_message):
    owner_tools.apply_pending(make_message(user_id=12345, text="hi"), "reply_to_chat",
                              {"chat_id": 424242})
    assert "Unknown chat id" in stub_bot.send_message.call_args.args[1]


# --- settings surface --------------------------------------------------------
def test_get_all_settings_round_trips_every_key(db):
    settings = database.get_all_settings()
    assert set(settings) == set(database.SETTINGS_SCHEMA)
    # Values come back with their declared python type, not as raw TEXT.
    for key, (kind, _default) in database.SETTINGS_SCHEMA.items():
        value = settings[key]
        assert isinstance(value, kind), f"{key} should be {kind.__name__}, got {type(value)}"
    # And they are JSON-serialisable (used by /export).
    json.dumps(settings, ensure_ascii=False)


def test_settings_schema_types_are_supported(db):
    assert set(database.SETTINGS_SCHEMA) == set(database.get_all_settings())
    for key in ("auto_reply_enabled", "approval_mode_enabled", "typing_indicator",
                "faq_enabled", "custom_instructions", "max_messages_per_customer_per_hour"):
        assert key in database.SETTINGS_SCHEMA


# --- message bookkeeping used by the pipeline -------------------------------
def test_message_exists_guards_the_pipeline(db):
    database.insert_message("bc1", 5, 99, "in", "user", "first")
    assert database.message_exists("bc1", 5, 99, "in") is True
    assert database.message_exists("bc1", 5, 99, "out") is False
    assert database.message_exists("bc1", 5, 100, "in") is False


def test_recent_messages_are_oldest_first(db):
    for index in range(3):
        database.insert_message("bc1", 5, index, "in", "user", f"m{index}")
    contents = [r["content"] for r in database.get_recent_messages("bc1", 5, limit=10)]
    assert contents == ["m0", "m1", "m2"]


def test_handlers_cfg_is_available_to_tools(stub_bot, fake_config):
    assert handlers.cfg is fake_config
    assert handlers.bot is stub_bot


def test_notify_owner_is_a_noop_without_a_bot(fake_config):
    handlers.cfg = fake_config
    handlers.bot = None
    handlers.notify_owner("ignored")  # must not raise


def test_utils_html_pipeline_is_shared_by_senders():
    assert utils.to_telegram_html("**hi** <script>") == "<b>hi</b> &lt;script&gt;"
    assert utils.plain_text("<b>hi</b>") == "hi"

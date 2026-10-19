"""Tests for handlers/business_updates.py: the customer-message decision
pipeline, branch by branch. Network/model calls are mocked; the DB is real."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import business_updates as bu
from services.ai_service import AIServiceError
from services.rate_limit_service import RateLimitDecision

EPOCH = "1970-01-01T00:00:00+00:00"


@pytest.fixture
def penv(db, stub_bot, mocker):
    """Pipeline environment: real DB + a registered connection, with the
    outbound Telegram calls patched. Owner (business_user_id) is 999.

    Message batching is disabled (window 0) so each call answers immediately.
    """
    send = mocker.patch("telegram_api.send_reply")
    chat_action = mocker.patch("telegram_api.chat_action")
    mocker.patch("telegram_api.typing_keepalive", return_value=_null_ctx())
    db.set_setting("reply_debounce_seconds", 0.0)
    db.upsert_business_connection("bc1", 999, True, True)
    return SimpleNamespace(db=db, send=send, chat_action=chat_action, bot=stub_bot)


def _null_ctx():
    from contextlib import nullcontext
    return nullcontext()


def _out_count(db, bcid="bc1", chat=5):
    return db.count_messages_in_window(bcid, chat, EPOCH, direction="out")


def _customer_texts(penv, chat=5):
    """Texts actually sent to the customer (owner notifications use chat 12345)."""
    return [call.args[2] for call in penv.send.call_args_list if call.args[1] == chat]


# --- early guards ------------------------------------------------------------
def test_no_bcid_ignored(penv, make_message):
    bu.process_business_message(make_message(business_connection_id=None))
    penv.send.assert_not_called()


def test_unknown_connection_ignored(penv, make_message, mocker):
    mocker.patch("services.business_service.fetch_and_store_via_raw", return_value=None)
    bu.process_business_message(make_message(business_connection_id="unknown"))
    penv.send.assert_not_called()


def test_echo_guard(penv, make_message):
    msg = make_message(business_connection_id="bc1", sender_business_bot=object())
    bu.process_business_message(msg)
    penv.send.assert_not_called()


def test_owner_takeover_pauses(penv, make_message):
    msg = make_message(business_connection_id="bc1", user_id=999, chat_id=5)
    bu.process_business_message(msg)
    assert penv.db.get_pause("bc1", 5) is not None
    penv.send.assert_not_called()


# --- non-text / monitoring ---------------------------------------------------
def test_non_text_monitoring_notice(penv, make_message):
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5,
                       text=None, content_type="photo")
    bu.process_business_message(msg)
    penv.send.assert_called()


def test_auto_off_notifies_incoming(penv, make_message):
    # auto_reply default OFF, monitoring default ON
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hi there")
    bu.process_business_message(msg)
    penv.send.assert_called()
    assert penv.db.count_pending_approvals() == 0


# --- paused / rate-limited ---------------------------------------------------
def test_paused_chat_skips(penv, make_message):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.upsert_pause("bc1", 5, "manual", None)  # indefinite
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hi")
    bu.process_business_message(msg)
    penv.send.assert_not_called()


def test_rate_limit_exceeded_notifies(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    mocker.patch("services.rate_limit_service.enforce",
                 return_value=RateLimitDecision(False, 21, 20, 0))
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hi")
    bu.process_business_message(msg)
    penv.send.assert_called()
    assert penv.db.count_pending_approvals() == 0


# --- generation paths --------------------------------------------------------
def test_strict_kb_short_circuit_no_model_call(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("strict_kb_mode", True)  # no chunks -> short circuit
    chat_spy = mocker.patch("services.ai_service.chat")
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="anything")
    bu.process_business_message(msg)
    chat_spy.assert_not_called()
    assert _out_count(penv.db) == 1  # short-circuit reply delivered


def test_openai_error_notifies_owner(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    mocker.patch("services.ai_service.chat",
                 side_effect=AIServiceError("bad key", kind="auth"))
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hello")
    bu.process_business_message(msg)
    penv.send.assert_called()
    assert penv.db.count_pending_approvals() == 0
    assert _out_count(penv.db) == 0


# --- dispatch: approval vs auto ---------------------------------------------
def test_approval_mode_creates_request(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", True)
    mocker.patch("services.ai_service.chat", return_value="AI reply")
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hello")
    bu.process_business_message(msg)
    assert penv.db.count_pending_approvals() == 1
    assert _out_count(penv.db) == 0  # not delivered yet, awaiting approval


def test_auto_delivery(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    mocker.patch("services.ai_service.chat", return_value="AI reply")
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5, text="hello")
    bu.process_business_message(msg)
    assert penv.db.count_pending_approvals() == 0
    assert _out_count(penv.db) == 1


def test_sensitive_forces_approval(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)  # approval OFF...
    penv.db.set_setting("sensitive_requires_approval", True)
    mocker.patch("services.ai_service.chat", return_value="AI reply")
    # ...but a sensitive message forces the approval path
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5,
                       text="I want a refund")
    bu.process_business_message(msg)
    assert penv.db.count_pending_approvals() == 1


# --- _deliver_auto permission guard -----------------------------------------
def test_deliver_auto_without_permission(db, stub_bot, make_message, mocker):
    send = mocker.patch("telegram_api.send_reply")
    db.upsert_business_connection("bc1", 999, True, False)  # can_reply False
    conn = db.get_business_connection("bc1")
    bu._deliver_auto(conn, 5, 21, "ctext", "reply")
    send.assert_called()  # owner warned
    assert _out_count(db) == 0  # nothing recorded as sent to customer


def test_deliver_auto_records_outbound(db, stub_bot, make_message, mocker):
    mocker.patch("telegram_api.send_reply")
    db.upsert_business_connection("bc1", 999, True, True)
    conn = db.get_business_connection("bc1")
    bu._deliver_auto(conn, 5, 22, "ctext", "reply text")
    assert _out_count(db) == 1


def test_deliver_auto_warns_on_partial_delivery(db, stub_bot, make_message, mocker):
    mocker.patch(
        "telegram_api.send_reply",
        side_effect=bu.telegram_api.TelegramPartialSendError(1, 2),
    )
    notify = mocker.patch("handlers.notify_owner")
    db.upsert_business_connection("bc1", 999, True, True)
    conn = db.get_business_connection("bc1")

    bu._deliver_auto(conn, 5, 21, "ctext", "reply text")

    assert "partially delivered (1/2 parts)" in notify.call_args.args[0]
    assert _out_count(db) == 0
    assert db.get_recent_memory("bc1", 5, 10) == []


def test_deliver_auto_warns_when_delivery_is_unconfirmed(
    db, stub_bot, make_message, mocker
):
    mocker.patch(
        "telegram_api.send_reply",
        side_effect=bu.telegram_api.TelegramAPIError("unavailable"),
    )
    notify = mocker.patch("handlers.notify_owner")
    db.upsert_business_connection("bc1", 999, True, True)
    conn = db.get_business_connection("bc1")

    bu._deliver_auto(conn, 5, 21, "ctext", "reply text")

    assert "could not be confirmed" in notify.call_args.args[0]
    assert _out_count(db) == 0
    assert db.get_recent_memory("bc1", 5, 10) == []


# --- edited / deleted messages ----------------------------------------------
def test_edited_customer_message_invalidates_approval(penv, make_message, mocker):
    aid = penv.db.insert_pending_approval("bc1", 5, 22, "before", "reply")
    notify = mocker.patch("handlers.notify_owner")

    bu.on_edited_business_message(
        make_message(
            business_connection_id="bc1", chat_id=5, message_id=22, text="after"
        )
    )

    assert penv.db.get_approval(aid)["status"] == "invalidated"
    assert "pending approval for the earlier version was cancelled" in notify.call_args.args[0]


def test_edited_customer_message_invalidates_with_monitoring_off(
    penv, make_message, mocker
):
    penv.db.set_setting("monitoring_mode", False)
    aid = penv.db.insert_pending_approval("bc1", 5, 22, "before", "reply")
    notify = mocker.patch("handlers.notify_owner")

    bu.on_edited_business_message(
        make_message(
            business_connection_id="bc1", chat_id=5, message_id=22, text="after"
        )
    )

    assert penv.db.get_approval(aid)["status"] == "invalidated"
    notify.assert_not_called()


def test_edited_owner_message_does_not_invalidate_customer_approval(
    penv, make_message, mocker
):
    aid = penv.db.insert_pending_approval("bc1", 5, 22, "customer", "reply")
    notify = mocker.patch("handlers.notify_owner")

    bu.on_edited_business_message(
        make_message(
            business_connection_id="bc1", user_id=999, chat_id=5,
            message_id=22, text="owner edit",
        )
    )

    assert penv.db.get_approval(aid)["status"] == "pending"
    notify.assert_not_called()


def test_deleted_invalidates_approval(penv):
    aid = penv.db.insert_pending_approval("bc1", 5, 22, "c", "r")
    deleted = SimpleNamespace(business_connection_id="bc1",
                              chat=SimpleNamespace(id=5), message_ids=[22])
    bu.on_deleted_business_messages(deleted)
    assert penv.db.get_approval(aid)["status"] == "invalidated"


# --- dedupe / batching / FAQ fast path ---------------------------------------
def test_duplicate_message_id_is_answered_once(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    chat = mocker.patch("services.ai_service.chat", return_value="AI reply")
    msg = make_message(business_connection_id="bc1", user_id=10, chat_id=5,
                       text="hello", message_id=77)
    bu.process_business_message(msg)
    bu.process_business_message(msg)          # Telegram redelivers the update
    assert chat.call_count == 1
    assert _out_count(penv.db) == 1


def test_burst_of_messages_is_answered_as_one(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("reply_debounce_seconds", 0.0)
    # Message 1 owns the flush and gets both texts; message 2 is folded in.
    mocker.patch("services.batching.batcher.process",
                 side_effect=[[(1, "hi"), (2, "how much")], None])
    chat = mocker.patch("services.ai_service.chat", return_value="AI reply")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="hi", message_id=1))
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="how much", message_id=2))
    assert chat.call_count == 1
    assert chat.call_args.args[0][-1]["content"] == "hi\nhow much"


def test_faq_exact_match_skips_the_model(penv, make_message, mocker):
    from services import faq_service
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    faq_service.add("price", "Prices start at 500 EGP.")
    chat = mocker.patch("services.ai_service.chat")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="what is the price?"))
    chat.assert_not_called()
    assert _out_count(penv.db) == 1
    assert _customer_texts(penv) == ["Prices start at 500 EGP."]


def test_signature_is_added_to_replies(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("signature", "— Cairo Bakery")
    mocker.patch("services.ai_service.chat", return_value="Hello there")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="hi"))
    assert _customer_texts(penv) == ["Hello there\n— Cairo Bakery"]


def test_new_customer_can_be_greeted(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("greet_new_customers", True)
    penv.db.set_setting("welcome_text", "Welcome to Cairo Bakery!")
    mocker.patch("services.ai_service.chat", return_value="AI reply")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="hi"))
    sent_texts = _customer_texts(penv)
    assert "Welcome to Cairo Bakery!" in sent_texts
    assert "AI reply" in sent_texts


def test_greeting_only_happens_once(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("greet_new_customers", True)
    mocker.patch("services.ai_service.chat", return_value="AI reply")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="hi", message_id=1))
    penv.send.reset_mock()
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="second", message_id=2))
    sent_texts = _customer_texts(penv)
    assert all("how can we help" not in (text or "") for text in sent_texts)


def test_nontext_acknowledgement(penv, make_message, mocker):
    penv.db.set_setting("auto_reply_enabled", True)
    penv.db.set_setting("approval_mode_enabled", False)
    penv.db.set_setting("nontext_ack_message", "Thanks! We received your file.")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text=None, content_type="photo"))
    assert "Thanks! We received your file." in _customer_texts(penv)


def test_no_automation_notifies_instead_of_answering(penv, make_message, mocker):
    """Both switches off -> only the owner is notified."""
    penv.db.set_setting("auto_reply_enabled", False)
    penv.db.set_setting("approval_mode_enabled", False)
    chat = mocker.patch("services.ai_service.chat")
    bu.process_business_message(make_message(business_connection_id="bc1", user_id=10,
                                             chat_id=5, text="hello"))
    chat.assert_not_called()
    assert penv.db.count_pending_approvals() == 0
    assert _out_count(penv.db) == 0


def test_off_master_switch_does_not_leave_approval_drafts_running(
    penv, make_message, mocker
):
    """An old/default approval flag cannot override the owner's OFF switch."""
    penv.db.set_setting("auto_reply_enabled", False)
    penv.db.set_setting("approval_mode_enabled", True)
    chat = mocker.patch("services.ai_service.chat")

    bu.process_business_message(make_message(
        business_connection_id="bc1", user_id=10, chat_id=5, text="hello"
    ))

    chat.assert_not_called()
    assert penv.db.count_pending_approvals() == 0
    assert _out_count(penv.db) == 0

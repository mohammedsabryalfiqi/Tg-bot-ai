"""Tests for services/gate_service.py — the two entry gates.

Both gates are admin switches that ship OFF, and both must fail *open*: a
permission-less bot, a stale cache, a missing price or an unknown membership
answer must never lock a real person out of the assistant. Those rules are what
this module pins.
"""

from __future__ import annotations

import pytest

from services import gate_service


def _fake_member(monkeypatch, statuses: dict):
    """Route ``get_chat_member`` through a dict; unseen chats answer "unknown"."""
    def fake(chat_ref, user_id):
        key = (chat_ref, user_id)
        if key not in statuses:
            return None                       # what the real call returns on error
        return {"status": statuses[key]}
    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member", fake)


# --- subscription gate --------------------------------------------------------
def test_the_gate_is_off_until_the_admin_turns_it_on(db, monkeypatch):
    db.add_required_channel("@mychannel", title="قناتي")
    _fake_member(monkeypatch, {})
    assert gate_service.subscription_enabled() is False
    assert gate_service.missing_channels(5001) == []
    assert gate_service.subscription_ok(5001) is True


def test_a_channel_without_the_switch_does_not_gate_anyone(db):
    assert gate_service.subscription_enabled() is False


def test_joined_users_pass_and_missing_users_are_reported(db, monkeypatch):
    db.add_required_channel("@required", title="قناة مطلوبة")
    db.set_setting("require_subscription_enabled", True)
    _fake_member(monkeypatch, {("@required", 5001): "member",
                               ("@required", 5002): "left"})

    assert gate_service.subscription_ok(5001) is True
    assert gate_service.missing_channels(5001) == []
    assert [row["chat_ref"] for row in gate_service.missing_channels(5002)] == ["@required"]


def test_an_unknown_membership_answer_never_blocks_a_person(db, monkeypatch):
    """A bot without permission to read members must not lock everyone out."""
    db.add_required_channel("@private_channel")
    db.set_setting("require_subscription_enabled", True)
    _fake_member(monkeypatch, {})                 # every lookup answers "unknown"
    assert gate_service.missing_channels(5001) == []

    def broken(chat_ref, user_id):
        raise RuntimeError("network down")

    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member", broken)
    db.clear_gate_checks()
    assert gate_service.missing_channels(5001) == []


def test_the_membership_answer_is_cached(db, monkeypatch):
    db.add_required_channel("@required")
    db.set_setting("require_subscription_enabled", True)
    calls: list = []

    def counting(chat_ref, user_id):
        calls.append(user_id)
        return {"status": "member"}

    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member", counting)
    gate_service.missing_channels(5001)
    gate_service.missing_channels(5001)
    assert calls == [5001]                        # second call served by the cache
    assert gate_service.was_verified_before(5001) is True

    # Changing the required channels invalidates the cache: the answer for the
    # old list must never keep a person inside (or outside).
    channel_id = db.list_required_channels()[0]["id"]
    gate_service.toggle_channel(channel_id)          # pause it
    gate_service.toggle_channel(channel_id)          # and enable it again
    calls.clear()
    assert gate_service.missing_channels(5001) == []
    assert calls == [5001]


def test_add_channel_builds_a_public_link_and_toggle_pauses_it(db):
    channel_id = gate_service.add_channel("mychannel")
    row = db.get_required_channel(channel_id)
    assert row["chat_ref"] == "@mychannel"
    assert row["invite_link"] == "https://t.me/mychannel"

    assert gate_service.toggle_channel(channel_id) is False
    assert gate_service.channels() == []
    assert gate_service.toggle_channel(9999) is None


def test_join_rows_skip_channels_without_a_link(db):
    gate_service.add_channel("-1001234", title="بدون رابط")
    assert gate_service.join_rows() == []


# --- stars gate ---------------------------------------------------------------
def test_payments_need_both_the_switch_and_a_price(db):
    db.set_setting("paid_messages_enabled", True)
    db.set_setting("paid_message_stars", 0)
    assert gate_service.payments_enabled() is False   # price 0 => gate open
    assert gate_service.payment_required(5001) is False

    db.set_setting("paid_message_stars", 50)
    assert gate_service.payments_enabled() is True
    assert gate_service.stars_price() == 50
    assert gate_service.payment_required(5001) is True


def test_payments_are_off_until_the_admin_types_a_price(db):
    db.set_setting("paid_message_stars", 50)
    assert gate_service.payments_enabled() is False


def test_free_quota_is_spent_before_the_gate_closes(db):
    db.set_setting("paid_messages_enabled", True)
    db.set_setting("paid_message_stars", 25)
    db.set_setting("paid_message_free_count", 2)

    assert gate_service.free_left(5001) == 2
    gate_service.park_message(5001, 5001, "الرسالة الأولى", free=True)
    assert gate_service.free_left(5001) == 1
    assert gate_service.payment_required(5001) is False

    gate_service.park_message(5001, 5001, "الرسالة التانية", free=True)
    assert gate_service.free_left(5001) == 0
    assert gate_service.payment_required(5001) is True


def test_parking_and_confirming_a_payment(db):
    db.set_setting("paid_messages_enabled", True)
    db.set_setting("paid_message_stars", 30)

    parked = gate_service.park_message(5001, 5001, "رسالة مدفوعة")
    assert parked["status"] == "pending" and parked["stars"] == 30
    assert db.count_paid_messages(status="paid") == 0

    paid = gate_service.confirm_payment(parked["payload"], charge_id="ch_1")
    assert paid["status"] == "paid" and paid["charge_id"] == "ch_1"
    assert db.sum_stars_earned() == 30

    # Confirming twice is a no-op (Telegram may retry the update).
    assert gate_service.confirm_payment(parked["payload"]) is None

    gate_service.mark_delivered(parked["id"])
    assert db.list_paid_messages()[0]["delivered"] == 1
    assert gate_service.refund(parked["id"]) is True
    assert db.count_paid_messages(status="refunded") == 1


def test_payloads_are_unique_per_message(db):
    first = gate_service.new_payload(5001)
    second = gate_service.new_payload(5001)
    assert first != second and first.startswith("pm:5001:")


def test_summary_reports_both_gates(db):
    db.add_required_channel("@required", title="قناة")
    db.set_setting("require_subscription_enabled", True)
    db.set_setting("paid_messages_enabled", True)

    data = gate_service.summary()
    assert data["subscription_on"] is True and data["channels"] == 1
    assert data["payments_on"] is False           # no price typed yet
    assert gate_service.summary_lines()

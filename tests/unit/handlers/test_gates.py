"""Regression coverage: entry gates must never authorize unpaid messages."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import keyboards
from handlers import gates, settings
from services import gate_service


def _buttons(markup):
    return {b.callback_data: b.to_dict() for row in markup.keyboard for b in row}


def test_subscription_toggle_is_present_and_changes_color(db, stub_bot, make_call):
    before = _buttons(keyboards.required_channels([]))
    assert before["gate:toggle_sub"]["style"] == "danger"
    gates.on_callback(make_call(data="gate:toggle_sub"))
    markup = stub_bot.edit_message_text.call_args.kwargs["reply_markup"]
    after = _buttons(markup)
    assert after["gate:toggle_sub"]["style"] == "success"
    assert "gate:add_channel" in after
    gates.on_callback(make_call(data="gate:toggle_sub"))
    assert _buttons(keyboards.required_channels([]))["gate:toggle_sub"]["style"] == "danger"


def test_stars_toggle_changes_color(db, stub_bot, make_call):
    assert _buttons(gates._stars_markup())["gate:toggle_stars"]["style"] == "danger"
    gates.on_callback(make_call(data="gate:toggle_stars"))
    markup = stub_bot.edit_message_text.call_args.kwargs["reply_markup"]
    assert _buttons(markup)["gate:toggle_stars"]["style"] == "success"


def test_settings_links_to_channel_and_stars_configuration(db):
    rows = settings._rows_for_group("gate")
    buttons = _buttons(keyboards.settings_root(rows))
    assert "gate:sub" in buttons and "gate:stars" in buttons
    assert buttons["set:toggle:require_subscription_enabled"]["style"] == "danger"
    db.set_setting("require_subscription_enabled", True)
    buttons = _buttons(keyboards.settings_root(settings._rows_for_group("gate")))
    assert buttons["set:toggle:require_subscription_enabled"]["style"] == "success"


@pytest.mark.parametrize("text,ref,link", [
    ("https://t.me/mychannel", "@mychannel", "https://t.me/mychannel"),
    ("@mychannel", "@mychannel", "https://t.me/mychannel"),
    ("-100123456 | Private | https://t.me/+invite", "-100123456", "https://t.me/+invite"),
])
def test_channel_input_accepts_links_and_private_ids(db, stub_bot, monkeypatch, text, ref, link):
    monkeypatch.setattr("telegram_api.get_chat", lambda ref: {})
    gates._save_channel(12345, text)
    row = db.list_required_channels()[0]
    assert row["chat_ref"] == ref
    assert row["invite_link"] == link


@pytest.mark.parametrize("text", ["https://t.me/+invite", "-100123456", "https://example.org/channel"])
def test_unusable_channel_references_are_rejected(db, stub_bot, monkeypatch, text):
    monkeypatch.setattr("telegram_api.get_chat", lambda ref: {})
    gates._save_channel(12345, text)
    assert db.list_required_channels() == []


@pytest.mark.parametrize("user_id,currency,amount,ok", [
    (5001, "XTR", 25, True), (5002, "XTR", 25, False),
    (5001, "USD", 25, False), (5001, "XTR", 1, False),
])
def test_checkout_checks_owner_currency_and_amount(db, monkeypatch, user_id, currency, amount, ok):
    db.set_setting("auto_reply_enabled", True)
    row = gate_service.park_message(5001, 5001, "hello", stars=25)
    answer = Mock()
    monkeypatch.setattr("telegram_api.answer_pre_checkout_query", answer)
    gates.on_pre_checkout(SimpleNamespace(
        id="checkout", invoice_payload=row["payload"],
        from_user=SimpleNamespace(id=user_id), currency=currency, total_amount=amount))
    assert answer.call_args.args[:2] == ("checkout", ok)


def test_business_precheckout_does_not_apply_direct_subscription_gate(db, monkeypatch):
    db.set_setting("auto_reply_enabled", True)
    db.set_setting("require_subscription_enabled", True)
    row = gate_service.park_message(
        5001, 5001, "hello", stars=25, business_connection_id="bc1"
    )
    monkeypatch.setattr(gate_service, "subscription_ok", lambda user_id: False)
    answer = Mock()
    monkeypatch.setattr("telegram_api.answer_pre_checkout_query", answer)

    gates.on_pre_checkout(SimpleNamespace(
        id="checkout", invoice_payload=row["payload"],
        from_user=SimpleNamespace(id=5001), currency="XTR", total_amount=25,
    ))

    assert answer.call_args.args[:2] == ("checkout", True)


def test_success_requires_matching_payment_and_is_not_delivered_twice(db, monkeypatch):
    row = gate_service.park_message(5001, 5001, "hello", stars=25)
    deliver = Mock()
    monkeypatch.setattr(gates, "deliver_paid_message", deliver)
    payment = SimpleNamespace(invoice_payload=row["payload"], currency="XTR",
                              total_amount=1, telegram_payment_charge_id="charge-1")
    message = SimpleNamespace(from_user=SimpleNamespace(id=5001), successful_payment=payment)
    gates.on_successful_payment(message)
    assert db.get_paid_message(row["id"])["status"] == "pending"
    deliver.assert_not_called()
    payment.total_amount = 25
    gates.on_successful_payment(message)
    gates.on_successful_payment(message)
    deliver.assert_called_once()
    assert db.get_paid_message(row["id"])["status"] == "paid"


def test_other_users_cannot_reopen_an_invoice(db, stub_bot, make_call, monkeypatch):
    row = gate_service.park_message(5001, 5001, "hello", stars=25)
    invoice = Mock()
    monkeypatch.setattr("telegram_api.send_star_invoice", invoice)
    gates.on_pay_callback(make_call(data=f"pay:buy:{row['payload']}", user_id=5002))
    invoice.assert_not_called()


def test_request_payment_uses_custom_message_and_star_placeholder(
    db, stub_bot, monkeypatch
):
    db.set_setting("paid_message_stars", 25)
    db.set_setting("payment_message", "Pay {stars} Stars to send your message.")
    monkeypatch.setattr(gate_service, "park_message",
                        lambda *args, **kwargs: {"payload": "pm:5001:test"})
    monkeypatch.setattr("telegram_api.send_star_invoice",
                        lambda *args, **kwargs: {"message_id": 12})

    assert gates.request_payment(5001, 5001, "hello") is True

    sent_text = stub_bot.send_message.call_args.args[1]
    assert sent_text == "Pay 25 Stars to send your message."


def test_verify_without_configured_channels_does_not_succeed(db, stub_bot, make_call):
    db.set_setting("require_subscription_enabled", True)
    gates.on_verify(make_call(data="gate:verify", user_id=5001))
    assert stub_bot.answer_callback_query.call_args.kwargs["show_alert"] is True
    stub_bot.edit_message_reply_markup.assert_not_called()

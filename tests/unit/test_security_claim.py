"""Tests for the first-run owner claim flow in security.py.

The bot can be started with only a bot token; ownership is claimed from Telegram
with a code that is printed in the terminal.
"""

from __future__ import annotations

import security


def _init_claim(db, bot, owner_id=None, code="ABCD1234"):
    security.init(bot, owner_id, claim_code=code)


def test_claim_pending_only_without_owner(db, stub_bot):
    _init_claim(db, stub_bot)
    assert security.claim_pending() is True
    assert security.owner_id() is None

    security.init(stub_bot, 555)
    assert security.claim_pending() is False
    assert security.owner_id() == 555


def test_correct_code_claims_ownership(db, stub_bot, make_message):
    _init_claim(db, stub_bot)
    security.handle_claim(make_message(user_id=321, text="/start ABCD1234"))

    assert security.owner_id() == 321
    assert security.is_owner(321) is True
    assert db.get_int("claimed_owner_user_id") == 321
    texts = [call.args[1] for call in stub_bot.send_message.call_args_list]
    assert any("now the owner" in text for text in texts)
    # The claim is followed by the control panel so the owner lands on the UI.
    assert any("Your Telegram Business assistant" in text for text in texts)


def test_claim_code_is_case_insensitive(db, stub_bot, make_message):
    _init_claim(db, stub_bot)
    security.handle_claim(make_message(user_id=321, text="/start abcd1234"))
    assert security.owner_id() == 321


def test_wrong_code_is_rejected(db, stub_bot, make_message):
    _init_claim(db, stub_bot)
    security.handle_claim(make_message(user_id=321, text="/start WRONG999"))

    assert security.owner_id() is None
    assert security.claim_pending() is True
    assert "not activated yet" in stub_bot.send_message.call_args.args[1]


def test_missing_code_shows_the_notice(db, stub_bot, make_message):
    _init_claim(db, stub_bot)
    security.handle_claim(make_message(user_id=321, text="/start"))
    assert security.owner_id() is None
    assert "claim-code" in stub_bot.send_message.call_args.args[1]


def test_claimed_owner_survives_a_restart(db, stub_bot, make_message, monkeypatch):
    _init_claim(db, stub_bot)
    security.handle_claim(make_message(user_id=321, text="/start ABCD1234"))

    # Simulate a restart: no configured owner, new claim code, cold cache.
    security.init(stub_bot, None, claim_code="NEWCODE1")
    assert security.owner_id() == 321
    assert security.claim_pending() is False


def test_configured_owner_beats_the_claim(db, stub_bot, make_message):
    security.init(stub_bot, 999, claim_code="ABCD1234")
    assert security.owner_id() == 999
    assert security.claim_pending() is False
    # Even the right code cannot steal an already-configured owner.
    security.handle_claim(make_message(user_id=321, text="/start ABCD1234"))
    assert security.owner_id() == 999


def test_too_many_failures_locks_the_claim(db, stub_bot, make_message):
    _init_claim(db, stub_bot)
    for _ in range(security._MAX_FAILED_CLAIMS + 2):
        security.handle_claim(make_message(user_id=321, text="/start WRONG999"))
    stub_bot.send_message.reset_mock()

    security.handle_claim(make_message(user_id=321, text="/start ABCD1234"))
    assert security.owner_id() is None
    stub_bot.send_message.assert_not_called()  # silently ignored while locked


def test_generate_claim_code_is_random_and_readable():
    codes = {security.generate_claim_code() for _ in range(20)}
    assert len(codes) == 20
    for code in codes:
        assert len(code) == 8
        assert code.isalnum() and code.upper() == code


def test_claim_handler_registration(bot_recorder=None):
    """The claim handler is registered for /start only while unclaimed."""
    from unittest.mock import MagicMock
    bot = MagicMock()
    security.init(bot, None, claim_code="ABCD1234")
    security.register_claim_handler(bot)
    assert bot.message_handler.called
    kwargs = bot.message_handler.call_args.kwargs
    assert kwargs["commands"] == ["start"]
    predicate = kwargs["func"]
    # With no owner yet the predicate allows the update, so the claim can happen.
    assert predicate(MagicMock()) is True

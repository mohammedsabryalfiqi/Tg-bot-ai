"""Tests for the /setup checklist: the live status of every onboarding step.

The checklist is the first screen a new owner sees, so it must render without a
connection, an AI key or any content — and must flip each step as the owner
progresses.
"""

from __future__ import annotations

import handlers
import i18n
from handlers import setup_guide

OWNER_CHAT = 5231453921


def _sent_text(bot) -> str:
    return bot.send_message.call_args.args[1]


def _sent_markup(bot):
    return bot.send_message.call_args.kwargs["reply_markup"]


def test_checklist_renders_with_an_empty_database(db, stub_bot):
    text = setup_guide.render_checklist()
    assert i18n.t("setup.title") in text
    for label in setup_guide.step_labels().values():
        assert label in text
    # Nothing is connected yet, and only the mode step can already be green.
    assert i18n.t("setup.connection.none") in text
    assert i18n.t("setup.direct") in text
    assert i18n.t("setup.tap_hint") in text


def test_steps_are_localised_at_render_time(db, stub_bot, monkeypatch):
    monkeypatch.setenv("BOT_LANGUAGE", "ar")
    i18n.invalidate_cache()
    arabic = setup_guide.render_checklist()
    assert any("\u0600" <= ch <= "\u06ff" for ch in arabic)
    assert "BotFather" in arabic          # the platform's own name is kept

    monkeypatch.setenv("BOT_LANGUAGE", "en")
    i18n.invalidate_cache()
    assert setup_guide.render_checklist() != arabic


def test_connection_flips_the_business_steps(db, stub_bot):
    db.upsert_business_connection("bc1", 999, True, True)
    text = setup_guide.render_checklist()
    assert i18n.t("setup.connection.live") in text
    assert setup_guide._status()["secretary"] is True
    assert setup_guide._status()["business"] is True


def test_a_read_only_connection_is_reported_separately(db, stub_bot):
    db.upsert_business_connection("bc1", 999, True, False)
    assert i18n.t("setup.connection.readonly") in setup_guide.render_checklist()


def test_the_synthetic_direct_connection_does_not_tick_the_business_step(db, stub_bot):
    from services import business_service
    business_service.ensure_direct_connection()
    assert setup_guide._status()["secretary"] is False
    assert setup_guide._status()["business"] is False


def test_content_and_test_steps_follow_the_data(db, stub_bot):
    assert setup_guide._status()["content"] is False
    from services import faq_service
    faq_service.add("price", "500 EGP")
    assert setup_guide._status()["content"] is True

    assert setup_guide._status()["test"] is False
    db.upsert_customer("bc1", 5, "Cara", None, None)
    db.insert_message("bc1", 5, 1, "out", "assistant", "hello")
    assert setup_guide._status()["test"] is True


def test_send_checklist_ships_the_step_buttons(db, stub_bot):
    setup_guide.send_checklist(OWNER_CHAT)
    assert i18n.t("setup.title") in _sent_text(stub_bot)
    data = [btn.callback_data for row in _sent_markup(stub_bot).keyboard for btn in row]
    assert "tool:setup_step:ai" in data
    assert any(d.startswith("tool:close") for d in data)


def test_send_step_includes_the_live_status_lines(db, stub_bot):
    setup_guide.send_step(OWNER_CHAT, "ai")
    text = _sent_text(stub_bot)
    assert i18n.t("setup.step.ai.body") in text
    assert "Provider:" in text or "المزوّد" in text


def test_send_step_with_an_unknown_key_returns_the_checklist(db, stub_bot):
    setup_guide.send_step(OWNER_CHAT, "nope")
    assert i18n.t("setup.title") in _sent_text(stub_bot)


def test_step_labels_have_details_for_every_step():
    labels = setup_guide.step_labels()
    assert set(labels) == set(setup_guide._DETAIL_KEYS)
    for key in labels:
        assert setup_guide.details(key)


def test_close_button_still_works(db, stub_bot, make_call):
    from handlers import owner_tools
    owner_tools.on_callback(make_call(data="tool:close"))
    assert stub_bot.delete_message.called

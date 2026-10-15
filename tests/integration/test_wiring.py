"""End-to-end wiring test: real TeleBot + real handler registration, with the
Telegram HTTP layer replaced by recorders.

This catches the class of bugs that unit tests cannot see: handler registration
order, ``allowed_updates`` mistakes, bot-command predicates, the claim flow and
the business-message pipeline being fed real Telegram ``Update`` objects.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import telebot

import config
import database
import handlers
import main
import security
import telegram_api
from services import file_service

TOKEN = "123456789:" + "A" * 35
OWNER_ID = 321
CLAIM_CODE = "ABCD1234"


class Recorder:
    """Captures everything the bot would send over the network."""

    def __init__(self):
        self.messages: list[tuple] = []       # (chat_id, text, kwargs)
        self.callbacks: list[tuple] = []      # (callback_id, text, show_alert)
        self.deleted: list[tuple] = []
        self.edits: list[tuple] = []

    def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text, kwargs))
        return SimpleNamespace(message_id=1000 + len(self.messages))

    def answer_callback_query(self, callback_id, text=None, show_alert=False, **kwargs):
        self.callbacks.append((callback_id, text, show_alert))
        return True

    def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True

    def edit_message_text(self, text, chat_id, message_id, **kwargs):
        self.edits.append((text, chat_id, message_id))
        return True

    def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        return True

    def send_chat_action(self, chat_id, action, **kwargs):
        return True

    def set_my_commands(self, commands):
        return True

    def remove_webhook(self, *args, **kwargs):
        return True

    def texts(self, chat_id=None) -> list[str]:
        return [m[1] for m in self.messages if chat_id is None or m[0] == chat_id]


@pytest.fixture
def wired(tmp_path, monkeypatch):
    cfg = config.Config(
        bot_token=TOKEN, owner_user_id=0, openai_api_key="", openai_base_url="",
        model_backend="openai", codex_model="", fernet_key="", default_model="gpt-4.1-mini",
        default_auto_reply=False, default_approval_mode=True,
        db_path=tmp_path / "smartel.db", uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store", worker_threads=2, debug=False,
    )
    database.init_db(cfg)
    file_service.init(cfg.uploads_dir)
    telegram_api.init(cfg.bot_token)

    bot = telebot.TeleBot(cfg.bot_token, parse_mode="HTML", threaded=False)
    recorder = Recorder()
    for name in ("send_message", "answer_callback_query", "delete_message",
                 "edit_message_text", "edit_message_reply_markup", "send_chat_action",
                 "set_my_commands", "remove_webhook"):
        monkeypatch.setattr(bot, name, getattr(recorder, name))

    security.init(bot, None, claim_code=CLAIM_CODE)
    handlers.init(bot, cfg)
    main.register_handlers(bot, cfg)
    try:
        yield SimpleNamespace(bot=bot, cfg=cfg, db=database, rec=recorder, tmp=tmp_path)
    finally:
        # The database module keeps a thread-local connection and its path
        # (conftest's `db` fixture does the same reset) — without this, the next
        # test in the module would read the previous test's database.
        conn = getattr(database._local, "conn", None)
        if conn is not None:
            conn.close()
            del database._local.conn
        database._DB_PATH = None
        database._SEED_DEFAULTS = {}
        handlers.bot = None
        handlers.cfg = None
        security._owner_id = None
        security._claimed_cache = None
        security._claim_code = None
        security._bot = None
        security._failed_claims.clear()
        security._last_notice.clear()
        file_service._uploads_dir = None
        telegram_api._TOKEN = telegram_api._API_BASE = telegram_api._FILE_BASE = None
        from services import batching
        batching.batcher.reset()


@pytest.fixture
def wired_owned(wired):
    """`wired` with the owner already claimed (so notify_owner has a target)."""
    wired.bot.process_new_updates([_dm(f"/start {CLAIM_CODE}")])
    wired.rec.messages.clear()
    wired.rec.callbacks.clear()
    return wired


def _update(payload: dict) -> telebot.types.Update:
    return telebot.types.Update.de_json(json.dumps(payload))


def _dm(text: str, user_id: int = OWNER_ID, update_id: int = 1, chat_id: int | None = None):
    return _update({
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "chat": {"id": chat_id or user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Someone"},
            "text": text,
            "entities": [{"type": "bot_command", "offset": 0,
                          "length": len(text.split()[0])}],
        },
    })


def _business_message(text: str, message_id: int = 50, chat_id: int = 5,
                      user_id: int = 10, bcid: str = "bc1", update_id: int = 100):
    return _update({
        "update_id": update_id,
        "business_message": {
            "message_id": message_id,
            "date": 0,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Customer"},
            "text": text,
            "business_connection_id": bcid,
        },
    })


# --- claim flow --------------------------------------------------------------
def test_claim_flow_then_owner_commands(wired):
    wired.bot.process_new_updates([_dm(f"/start {CLAIM_CODE}")])
    assert wired.db.get_int("claimed_owner_user_id") == OWNER_ID
    assert any("now the owner" in text for text in wired.rec.texts(OWNER_ID))

    wired.rec.messages.clear()
    wired.bot.process_new_updates([_dm("/help", update_id=2)])
    assert any("Telegram Business" in text for text in wired.rec.texts(OWNER_ID))


def test_wrong_claim_code_gets_the_notice(wired):
    wired.bot.process_new_updates([_dm("/start NOPE9999", user_id=999)])
    assert wired.db.get_int("claimed_owner_user_id") == 0
    assert any("not activated yet" in text for text in wired.rec.texts(999))


def test_non_owner_command_gets_the_managed_notice(wired):
    wired.db.set_setting("claimed_owner_user_id", OWNER_ID)
    security.init(wired.bot, OWNER_ID)
    wired.bot.process_new_updates([_dm("/help", user_id=4242, update_id=3)])
    assert any("managed Telegram Business assistant" in text for text in wired.rec.texts(4242))


# --- owner panel -------------------------------------------------------------
def test_start_panel_and_mode_command(wired):
    security.init(wired.bot, OWNER_ID)
    wired.bot.process_new_updates([_dm("/start", update_id=4)])
    assert any("Your Telegram Business assistant" in text for text in wired.rec.texts(OWNER_ID))

    wired.bot.process_new_updates([_dm("/mode auto", update_id=5)])
    assert wired.db.get_bool("auto_reply_enabled") is True
    assert wired.db.get_bool("approval_mode_enabled") is False


def test_setup_checklist_renders(wired):
    security.init(wired.bot, OWNER_ID)
    wired.bot.process_new_updates([_dm("/setup", update_id=6)])
    assert any("Setup" in text and "BotFather" in text for text in wired.rec.texts(OWNER_ID))


def test_ai_screen_renders(wired):
    security.init(wired.bot, OWNER_ID)
    wired.bot.process_new_updates([_dm("/ai", update_id=7)])
    assert any("AI provider" in text for text in wired.rec.texts(OWNER_ID))


# --- business pipeline -------------------------------------------------------
def test_business_message_produces_an_auto_reply(wired, monkeypatch):
    wired.db.upsert_business_connection("bc1", 999, True, True)
    wired.db.set_setting("auto_reply_enabled", True)
    wired.db.set_setting("approval_mode_enabled", False)
    wired.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "Sure — 500 EGP.")

    wired.bot.process_new_updates([_business_message("how much?")])

    assert "Sure — 500 EGP." in wired.rec.texts(5)
    assert wired.db.count_messages(direction="out", role="assistant") == 1


def test_business_message_creates_a_draft_for_approval(wired_owned, monkeypatch):
    wired_owned.db.upsert_business_connection("bc1", 999, True, True)
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", True)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "Draft reply")

    wired_owned.bot.process_new_updates([_business_message("hello there")])

    assert wired_owned.db.count_pending_approvals() == 1
    owner_messages = wired_owned.rec.texts(OWNER_ID)
    assert any("Approval #1" in text for text in owner_messages)
    # Nothing was sent to the customer: it waits for the owner's tap.
    assert wired_owned.rec.texts(5) == []


def test_faq_answers_instantly_end_to_end(wired, monkeypatch):
    from services import faq_service
    wired.db.upsert_business_connection("bc1", 999, True, True)
    wired.db.set_setting("auto_reply_enabled", True)
    wired.db.set_setting("approval_mode_enabled", False)
    wired.db.set_setting("reply_debounce_seconds", 0.0)
    faq_service.add("price", "Prices start at 500 EGP.")
    called = {"n": 0}

    def fail(_messages):
        called["n"] += 1
        raise AssertionError("the model must not be called for an exact FAQ match")

    monkeypatch.setattr("services.ai_service.chat", fail)

    wired.bot.process_new_updates([_business_message("what is the price?")])

    assert called["n"] == 0
    assert "Prices start at 500 EGP." in wired.rec.texts(5)


def test_html_unsafe_reply_cannot_break_the_send(wired, monkeypatch):
    """The raw model output goes through the sanitizer before Telegram sees it."""
    wired.db.upsert_business_connection("bc1", 999, True, True)
    wired.db.set_setting("auto_reply_enabled", True)
    wired.db.set_setting("approval_mode_enabled", False)
    wired.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat",
                        lambda messages: "**Yes!** price < 100 & shipping is fast")

    wired.bot.process_new_updates([_business_message("cheap?")])

    body = [text for text in wired.rec.texts(5)][0]
    assert body == "<b>Yes!</b> price &lt; 100 &amp; shipping is fast"


def test_owner_takeover_pauses_the_chat(wired):
    wired.db.upsert_business_connection("bc1", 999, True, True)
    wired.db.set_setting("auto_reply_enabled", True)

    # The business account owner (999) replies manually in the customer chat.
    wired.bot.process_new_updates([_business_message("I'll handle it", user_id=999)])

    assert wired.db.get_pause("bc1", 5) is not None
    assert wired.rec.texts(5) == []


def test_business_connection_update_is_announced(wired):
    wired.db.set_setting("claimed_owner_user_id", OWNER_ID)
    security.init(wired.bot, OWNER_ID)
    wired.bot.process_new_updates([_update({
        "update_id": 200,
        "business_connection": {
            "id": "bc9", "user": {"id": 999, "is_bot": False, "first_name": "Boss"},
            "user_chat_id": 999, "date": 0, "can_reply": True, "is_enabled": True,
        },
    })])
    assert wired.db.get_business_connection("bc9") is not None
    assert any("Business connection enabled" in text for text in wired.rec.texts(OWNER_ID))

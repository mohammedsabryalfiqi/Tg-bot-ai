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
        self.edits_full: list[tuple] = []     # (text, chat_id, message_id, kwargs)

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
        self.edits_full.append((text, chat_id, message_id, kwargs))
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


def _callback(data: str, user_id: int = OWNER_ID, chat_id: int | None = None,
              message_id: int = 4242, update_id: int = 900):
    """A button press by the owner (inline keyboard callback)."""
    return _update({
        "update_id": update_id,
        "callback_query": {
            "id": f"cb{update_id}",
            "from": {"id": user_id, "is_bot": False, "first_name": "Owner"},
            "chat_instance": "1",
            "data": data,
            "message": {
                "message_id": message_id,
                "date": 0,
                "chat": {"id": chat_id or user_id, "type": "private"},
                "from": {"id": 1, "is_bot": True, "first_name": "Bot"},
                "text": "approval card",
            },
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
    assert any("Alfiqi Ai — Telegram Business assistant" in text for text in wired.rec.texts(OWNER_ID))

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


def _direct_message(text: str, user_id: int = 4242, update_id: int = 300,
                    message_id: int | None = None, chat_id: int | None = None):
    """A plain private message sent to the bot itself (no Business connection)."""
    return _update({
        "update_id": update_id,
        "message": {
            "message_id": message_id or update_id,
            "date": 0,
            "chat": {"id": chat_id or user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Mona"},
            "text": text,
        },
    })


def _customer_kwargs(rec, chat_id: int) -> list[dict]:
    return [m[2] for m in rec.messages if m[0] == chat_id]


# --- direct messages (the bot's own private chat) -----------------------------
def test_direct_message_is_answered_end_to_end(wired_owned, monkeypatch):
    wired_owned.db.set_setting("ai_provider", "pollinations")   # usable, needs no key
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", False)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "أهلاً بيك 👋")

    wired_owned.bot.process_new_updates([_direct_message("السلام عليكم")])

    assert "أهلاً بيك 👋" in wired_owned.rec.texts(4242)
    assert wired_owned.db.count_messages(direction="out", role="assistant") == 1
    # The chat is stored under the reserved direct connection, hidden from stats.
    assert wired_owned.db.get_business_connection(telegram_api.DIRECT_CONNECTION_ID)


def test_direct_message_never_carries_a_business_connection_id(wired_owned, monkeypatch):
    """Telegram rejects a connection id that was never granted: the synthetic
    'direct' one must never reach the wire."""
    wired_owned.db.set_setting("ai_provider", "pollinations")
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", False)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "hi back")

    wired_owned.bot.process_new_updates([_direct_message("hello")])

    sent = _customer_kwargs(wired_owned.rec, 4242)
    assert sent and all("business_connection_id" not in kw for kw in sent)


def test_direct_draft_mode_creates_an_approval_the_owner_can_send(wired_owned, monkeypatch):
    wired_owned.db.set_setting("ai_provider", "pollinations")
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", True)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "مسودة رد")

    wired_owned.bot.process_new_updates([_direct_message("عندكم إيه؟")])
    assert wired_owned.db.count_pending_approvals() == 1
    assert wired_owned.rec.texts(4242) == []          # waits for the owner's tap

    wired_owned.bot.process_new_updates([_callback("apr:send:1")])

    assert "مسودة رد" in wired_owned.rec.texts(4242)
    assert wired_owned.db.count_pending_approvals() == 0


def test_direct_switch_off_restores_the_managed_notice(wired_owned):
    wired_owned.db.set_setting("direct_reply_enabled", False)

    wired_owned.bot.process_new_updates([_direct_message("أيوه؟")])

    assert any("managed Telegram Business assistant" in text
               for text in wired_owned.rec.texts(4242))


def test_direct_message_without_an_ai_key_gets_the_managed_notice(wired_owned, monkeypatch):
    wired_owned.db.set_setting("ai_provider", "openai")     # no key stored
    wired_owned.db.set_setting("auto_reply_enabled", True)
    monkeypatch.setattr("services.ai_service.chat",
                        lambda messages: pytest.fail("the model must not be called"))

    wired_owned.bot.process_new_updates([_direct_message("مرحبا")])

    assert any("managed Telegram Business assistant" in text
               for text in wired_owned.rec.texts(4242))


def test_language_command_switches_and_persists(wired_owned):
    wired_owned.bot.process_new_updates([_dm("/language ar", update_id=320)])
    assert wired_owned.db.get_str("ui_language") == "ar"

    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_dm("/lang en", update_id=321)])
    assert wired_owned.db.get_str("ui_language") == "en"


# --- Arabic interface ---------------------------------------------------------
def test_every_screen_renders_in_arabic_without_missing_keys(wired_owned, monkeypatch,
                                                            caplog):
    """Walk every owner screen in Arabic: no raw keys, no format warnings.

    ``i18n`` logs "missing translation key: …" whenever a screen asks for a key
    that only exists in one catalog, so a passing run means the whole interface is
    actually translated.
    """
    import i18n as i18n_module

    monkeypatch.setenv("BOT_LANGUAGE", "ar")
    i18n_module.invalidate_cache()
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", False)

    commands = ["/start", "/help", "/setup", "/mode", "/direct", "/language",
                "/ai", "/freeai", "/faq", "/kb", "/status", "/health",
                "/settings", "/chats", "/stats", "/instructions", "/connections",
                "/rules", "/unanswered", "/resources", "/gate"]
    rendered: list[str] = []
    with caplog.at_level("WARNING"):
        for index, command in enumerate(commands, start=400):
            wired_owned.rec.messages.clear()
            wired_owned.bot.process_new_updates([_dm(command, update_id=index)])
            rendered += wired_owned.rec.texts(OWNER_ID)
            assert rendered, f"{command} produced no reply"

        # A setup step screen (the buttons on the checklist).
        wired_owned.bot.process_new_updates([_callback("tool:setup_step:ai", update_id=500)])
        rendered += wired_owned.rec.texts(OWNER_ID)

        # The sub-screens of the new menus (they are edits, not new messages).
        for index, data in enumerate(["set:group:learning", "set:group:gate",
                                      "rule:add", "rule:list", "res:add", "res:list",
                                      "unans:list", "gate:sub", "gate:stars",
                                      "gate:list"], start=560):
            wired_owned.bot.process_new_updates([_callback(data, update_id=index)])
        rendered += [text for text, _chat, _mid in wired_owned.rec.edits]

    problems = [record.getMessage() for record in caplog.records
                if "missing translation" in record.getMessage()
                or "could not be formatted" in record.getMessage()]
    assert problems == []

    joined = " ".join(rendered)
    arabic = sum(1 for ch in joined if "\u0600" <= ch <= "\u06ff")
    assert arabic > 200, "the Arabic screens should be mostly Arabic text"
    assert "BotFather" in joined          # platform names stay as they are


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


# --- topic rules, unanswered questions and the two entry gates ----------------
def _buttons(markup) -> list[tuple[str, str]]:
    """(text, callback_data) for every inline button in a markup."""
    rows = getattr(markup, "keyboard", None) or []
    return [(button.text, getattr(button, "callback_data", "") or "")
            for row in rows for button in row]


def _rules_env(wired_owned, monkeypatch, reply: str = "تمام 👌"):
    """A ready direct-message pipeline with a fixed (fake) model answer."""
    wired_owned.db.set_setting("ai_provider", "pollinations")
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", False)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: reply)
    return wired_owned


def test_rules_command_renders_and_drafts_an_instruction(wired_owned, monkeypatch):
    wired_owned.bot.process_new_updates([_dm("/rules", update_id=600)])
    assert any("topic rules" in text.lower() for text in wired_owned.rec.texts(OWNER_ID))

    # The AI splits the owner's paragraph into rules, but nothing is live yet.
    monkeypatch.setattr("services.ai_service.is_ready", lambda: True)
    monkeypatch.setattr("services.ai_service.chat", lambda messages: (
        '{"rules": [{"topic": "الأسعار", "rule": "السعر 500 جنيه."}], "questions": []}'
    ))
    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_dm("/rules_add السعر 500 جنيه", update_id=601)])

    assert wired_owned.db.count_topic_rules(enabled_only=True) == 0
    assert wired_owned.db.count_topic_rules(enabled_only=False) == 1
    buttons = [b for _chat, _text, kw in wired_owned.rec.messages
               if kw.get("reply_markup") for b in _buttons(kw["reply_markup"])]
    assert any(data.startswith("rule:ok:") for _text, data in buttons)

    # ✅ makes them live.
    batch = wired_owned.db.list_topic_rules(enabled_only=False)[0]["batch"]
    wired_owned.bot.process_new_updates([_callback(f"rule:ok:{batch}", update_id=602)])
    assert wired_owned.db.count_topic_rules(enabled_only=True) == 1
    assert "السعر 500 جنيه" in wired_owned.db.list_topic_rules()[0]["rule"]

    # ... and from now on every reply is composed with the owner's rule.
    from services import prompt_service
    assert "السعر 500 جنيه" in prompt_service.build_system_prompt()


def test_an_approved_rule_reaches_the_model(wired_owned, monkeypatch):
    from services import rules_service

    _rules_env(wired_owned, monkeypatch)
    # Draft it the offline way (no AI needed), then approve it.
    with monkeypatch.context() as offline:
        offline.setattr("services.ai_service.is_ready", lambda: False)
        draft = rules_service.organize("متعملش خصم من نفسك")
    rules_service.approve(draft.batch)

    seen: list[list[dict]] = []
    monkeypatch.setattr("services.ai_service.chat",
                        lambda messages: seen.append(messages) or "حاضر")

    wired_owned.bot.process_new_updates([_direct_message("في خصم؟")])

    assert seen, "the model should have been called"
    system = seen[0][0]["content"]
    assert "TOPIC RULES" in system and "متعملش خصم من نفسك" in system
    assert "حاضر" in wired_owned.rec.texts(4242)


def test_no_answer_asks_the_owner_and_files_the_question(wired_owned, monkeypatch):
    """The model says NO_ANSWER -> polite notice to the person, question to the owner."""
    _rules_env(wired_owned, monkeypatch, reply="NO_ANSWER")

    wired_owned.bot.process_new_updates([_direct_message("بتشتغلوا الجمعة؟")])

    assert wired_owned.db.count_unanswered("open") == 1
    question = wired_owned.db.list_unanswered("open")[0]
    assert question["customer_chat_id"] == 4242

    # The person was told the team will get back to them — not the marker.
    customer_texts = wired_owned.rec.texts(4242)
    assert any("الفريق" in text or "team" in text for text in customer_texts)
    assert all("NO_ANSWER" not in text for text in customer_texts)

    # The owner got the question with an answer button.
    owner_messages = wired_owned.rec.messages
    assert any(chat == OWNER_ID and "بتشتغلوا الجمعة؟" in text
               for chat, text, _kw in owner_messages)


def test_the_owner_answer_is_delivered_and_learned(wired_owned, monkeypatch):
    from services import faq_service

    _rules_env(wired_owned, monkeypatch, reply="NO_ANSWER")
    wired_owned.bot.process_new_updates([_direct_message("بتشتغلوا الجمعة؟")])
    question_id = wired_owned.db.list_unanswered("open")[0]["id"]

    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_callback(f"unans:answer:{question_id}",
                                                   update_id=610)])
    wired_owned.bot.process_new_updates([_dm("أيوه، من 10 لـ 6.", update_id=611)])

    assert wired_owned.db.count_unanswered("open") == 0
    assert any("من 10 لـ 6" in text for text in wired_owned.rec.texts(4242))
    match, _verbatim = faq_service.resolve("بتشتغلوا الجمعة؟")
    assert match is not None and "من 10 لـ 6" in match.answer


def test_subscription_gate_holds_the_message_until_the_person_joins(wired_owned, monkeypatch):
    wired_owned.db.add_required_channel("@required", title="قناة مطلوبة")
    wired_owned.db.set_setting("require_subscription_enabled", True)
    _rules_env(wired_owned, monkeypatch)
    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member",
                        lambda ref, user: {"status": "left"})
    wired_owned.db.clear_gate_checks()

    wired_owned.bot.process_new_updates([_direct_message("مرحبا")])

    # Held at the gate: no answer, a join button, and nothing for the owner.
    texts = wired_owned.rec.texts(4242)
    assert texts and all("تمام" not in text for text in texts)
    gate_buttons = [b for chat, _t, kw in wired_owned.rec.messages
                    if chat == 4242 and kw.get("reply_markup")
                    for b in _buttons(kw["reply_markup"])]
    assert any(data == "gate:verify" for _text, data in gate_buttons)
    assert wired_owned.db.count_messages(direction="in") == 0
    assert not any("مطلوبة" in text for chat, text, _kw in wired_owned.rec.messages
                   if chat == OWNER_ID)

    # ... and the assistant answers once the membership check passes.
    wired_owned.rec.messages.clear()
    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member",
                        lambda ref, user: {"status": "member"})
    wired_owned.db.clear_gate_checks()
    wired_owned.bot.process_new_updates([_direct_message("مرحبا", update_id=620,
                                                         message_id=620)])
    assert "تمام 👌" in wired_owned.rec.texts(4242)


def test_business_chats_are_never_gated(wired_owned, monkeypatch):
    """A Telegram Business customer chat keeps working exactly as before."""
    wired_owned.db.add_required_channel("@required")
    wired_owned.db.set_setting("require_subscription_enabled", True)
    wired_owned.db.set_setting("paid_messages_enabled", True)
    wired_owned.db.set_setting("paid_message_stars", 50)
    wired_owned.db.upsert_business_connection("bc1", 999, True, True)
    wired_owned.db.set_setting("auto_reply_enabled", True)
    wired_owned.db.set_setting("approval_mode_enabled", False)
    wired_owned.db.set_setting("reply_debounce_seconds", 0.0)
    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member",
                        lambda ref, user: {"status": "left"})
    monkeypatch.setattr("services.ai_service.chat", lambda messages: "أهلاً 👋")

    wired_owned.bot.process_new_updates([_business_message("السلام عليكم")])

    assert "أهلاً 👋" in wired_owned.rec.texts(5)


def test_star_gate_invoices_then_delivers_after_payment(wired_owned, monkeypatch):
    wired_owned.db.set_setting("paid_messages_enabled", True)
    wired_owned.db.set_setting("paid_message_stars", 25)
    _rules_env(wired_owned, monkeypatch)
    monkeypatch.setattr("services.ai_service.is_ready", lambda: True)

    invoices: list[dict] = []
    monkeypatch.setattr("telegram_api.send_star_invoice",
                        lambda chat_id, **kw: invoices.append(kw) or {"message_id": 1})

    wired_owned.bot.process_new_updates([_direct_message("عايز أطلب")])

    assert invoices and invoices[0]["stars"] == 25
    assert wired_owned.db.count_paid_messages(status="pending") == 1
    assert wired_owned.rec.texts(4242)          # the "pay N stars" prompt
    assert wired_owned.db.count_messages(direction="in") == 0   # not delivered yet

    payload = invoices[0]["payload"]
    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_update({
        "update_id": 700,
        "message": {
            "message_id": 700, "date": 0,
            "chat": {"id": 4242, "type": "private"},
            "from": {"id": 4242, "is_bot": False, "first_name": "Mona"},
            "successful_payment": {
                "currency": "XTR", "total_amount": 25, "invoice_payload": payload,
                "telegram_payment_charge_id": "ch_99", "provider_payment_charge_id": "",
            },
        },
    })])

    assert wired_owned.db.count_paid_messages(status="paid") == 1
    assert wired_owned.db.sum_stars_earned() == 25
    assert "تمام 👌" in wired_owned.rec.texts(4242)
    # The owner got a copy of the paid message.
    assert any(chat == OWNER_ID and "عايز أطلب" in text
               for chat, text, _kw in wired_owned.rec.messages)


def test_a_paid_message_is_not_answered_when_the_invoice_fails(wired_owned, monkeypatch):
    wired_owned.db.set_setting("paid_messages_enabled", True)
    wired_owned.db.set_setting("paid_message_stars", 25)
    _rules_env(wired_owned, monkeypatch)
    monkeypatch.setattr("telegram_api.send_star_invoice", lambda chat_id, **kw: None)

    wired_owned.bot.process_new_updates([_direct_message("عايز أطلب")])

    # Telegram refused the invoice: the gate must not swallow the message.
    assert "تمام 👌" in wired_owned.rec.texts(4242)
    assert wired_owned.db.count_paid_messages(status="pending") == 0


def test_gate_and_rules_owner_screens_render(wired_owned):
    wired_owned.bot.process_new_updates([_dm("/gate", update_id=630)])
    assert any("Entry gates" in text for text in wired_owned.rec.texts(OWNER_ID))

    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_dm("/resources", update_id=631)])
    assert any("Knowledge" in text or "resource" in text.lower()
               for text in wired_owned.rec.texts(OWNER_ID))

    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_dm("/unanswered", update_id=632)])
    assert wired_owned.rec.texts(OWNER_ID)


def test_gate_price_is_typed_by_the_admin_and_then_charged(wired_owned, monkeypatch):
    """The star price is never preset: the admin types it in /gate."""
    monkeypatch.setattr("telegram_api.send_star_invoice",
                        lambda chat_id, **kw: {"message_id": 1})
    monkeypatch.setattr("services.ai_service.is_ready", lambda: True)

    wired_owned.bot.process_new_updates([_callback("gate:price", update_id=640)])
    wired_owned.bot.process_new_updates([_dm("50", update_id=641)])

    assert wired_owned.db.get_int("paid_message_stars") == 50
    assert wired_owned.db.get_bool("paid_messages_enabled") is True
    assert any("50" in text for text in wired_owned.rec.texts(OWNER_ID))

    # ... and the next customer message is invoiced at that price.
    invoices: list[dict] = []
    monkeypatch.setattr("telegram_api.send_star_invoice",
                        lambda chat_id, **kw: invoices.append(kw) or {"message_id": 1})
    _rules_env(wired_owned, monkeypatch)
    wired_owned.bot.process_new_updates([_direct_message("عايز أطلب", update_id=642)])
    assert [invoice["stars"] for invoice in invoices] == [50]


def test_gate_price_rejects_junk(wired_owned):
    wired_owned.bot.process_new_updates([_callback("gate:price", update_id=650)])
    wired_owned.bot.process_new_updates([_dm("مش رقم", update_id=651)])
    assert wired_owned.db.get_int("paid_message_stars") == 0
    assert any("digits" in text for text in wired_owned.rec.texts(OWNER_ID))


def test_adding_a_required_channel_from_the_gate_screen(wired_owned, monkeypatch):
    monkeypatch.setattr("telegram_api.get_chat",
                        lambda ref: {"title": "قناتي الرسمية", "type": "channel"})
    wired_owned.db.set_setting("require_subscription_enabled", True)

    wired_owned.bot.process_new_updates([_callback("gate:add_channel", update_id=660)])
    wired_owned.bot.process_new_updates([_dm("@mychannel", update_id=661)])

    rows = wired_owned.db.list_required_channels()
    assert [row["chat_ref"] for row in rows] == ["@mychannel"]
    assert rows[0]["title"] == "قناتي الرسمية"

    # The verify button re-checks membership (bypassing the cache) and answers.
    monkeypatch.setattr("services.gate_service.telegram_api.get_chat_member",
                        lambda ref, user: {"status": "member"})
    wired_owned.rec.callbacks.clear()
    wired_owned.bot.process_new_updates([_callback("gate:verify", user_id=4242,
                                                   chat_id=4242, update_id=662)])
    assert any("subscription is confirmed" in (text or "")
               for _cb, text, _alert in wired_owned.rec.callbacks)


def test_resources_add_accepts_a_typed_link(wired_owned, monkeypatch):
    monkeypatch.setattr("services.resource_service.fetch_text",
                        lambda url: ("صفحة الأسعار", "الأسعار: 500 جنيه، والتوصيل خلال يومين داخل دمياط."))

    wired_owned.bot.process_new_updates([_callback("res:add", update_id=670)])
    wired_owned.bot.process_new_updates([_dm("https://shop.example.com/prices", update_id=671)])

    rows = wired_owned.db.list_resources()
    assert len(rows) == 1 and rows[0]["kind"] == "link"
    assert rows[0]["url"] == "https://shop.example.com/prices"
    assert wired_owned.db.list_kb_items()             # fetched into the knowledge base

    # The reference reaches the model as approved context.
    from services import prompt_service
    assert "shop.example.com/prices" in prompt_service.build_system_prompt()


def test_rule_edit_replaces_the_draft(wired_owned, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    wired_owned.bot.process_new_updates([_dm("/rules_add قاعدة قديمة", update_id=680)])
    batch = wired_owned.db.list_topic_rules(enabled_only=False)[0]["batch"]

    wired_owned.bot.process_new_updates([_callback(f"rule:edit:{batch}", update_id=681)])
    wired_owned.bot.process_new_updates([_dm("قاعدة جديدة", update_id=682)])

    rules = wired_owned.db.list_topic_rules(enabled_only=False)
    assert [row["rule"] for row in rules] == ["قاعدة جديدة"]
    assert rules[0]["batch"] != batch


def test_unanswered_ignore_clears_the_card(wired_owned, monkeypatch):
    _rules_env(wired_owned, monkeypatch, reply="NO_ANSWER")
    wired_owned.bot.process_new_updates([_direct_message("سؤال غريب")])
    question_id = wired_owned.db.list_unanswered("open")[0]["id"]

    wired_owned.bot.process_new_updates([_callback(f"unans:ignore:{question_id}",
                                                   update_id=690)])

    assert wired_owned.db.count_unanswered("open") == 0
    assert wired_owned.db.count_unanswered("ignored") == 1


def test_settings_toggle_switches_the_new_features_off(wired_owned):
    wired_owned.bot.process_new_updates([_callback("set:toggle:rules_enabled",
                                                   update_id=695)])
    assert wired_owned.db.get_bool("rules_enabled") is False

    wired_owned.bot.process_new_updates([_callback("set:group:gate", update_id=696)])
    rendered = " ".join(text for text, _chat, _mid, _kw in wired_owned.rec.edits_full)
    assert "Entry gates" in rendered
    gate_buttons = [b for _t, _c, _m, kw in wired_owned.rec.edits_full
                    if kw.get("reply_markup")
                    for b in _buttons(kw["reply_markup"])]
    assert any(key in data for _text, data in gate_buttons
               for key in ("require_subscription_enabled", "paid_messages_enabled"))


def test_the_first_free_message_warns_before_the_gate_closes(wired_owned, monkeypatch):
    wired_owned.db.set_setting("paid_messages_enabled", True)
    wired_owned.db.set_setting("paid_message_stars", 40)
    wired_owned.db.set_setting("paid_message_free_count", 1)
    _rules_env(wired_owned, monkeypatch)

    # First message: free, answered, and the person is told what comes next.
    wired_owned.bot.process_new_updates([_direct_message("مرحبا", update_id=710,
                                                         message_id=710)])
    assert "تمام 👌" in wired_owned.rec.texts(4242)
    assert any("40" in text and "free" in text for text in wired_owned.rec.texts(4242))
    assert wired_owned.db.count_paid_messages(free=True) == 1

    # Second message: now it costs stars, so it is invoiced and held.
    invoices: list[dict] = []
    monkeypatch.setattr("telegram_api.send_star_invoice",
                        lambda chat_id, **kw: invoices.append(kw) or {"message_id": 9})
    wired_owned.rec.messages.clear()
    wired_owned.bot.process_new_updates([_direct_message("تاني", update_id=711,
                                                         message_id=711)])
    assert [invoice["stars"] for invoice in invoices] == [40]
    assert not any("تمام 👌" in text for text in wired_owned.rec.texts(4242))


def test_refunding_marks_the_payment_and_talks_to_telegram(wired_owned, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr("telegram_api.refund_star_payment",
                        lambda user_id, charge_id: calls.append((user_id, charge_id)) or True)

    payload = "pm:4242:abc123"
    wired_owned.db.create_paid_message(4242, 4242, payload, 30, "رسالة مدفوعة")
    wired_owned.db.mark_paid_message_paid(payload, "ch_7")
    paid_id = wired_owned.db.get_paid_message_by_payload(payload)["id"]

    wired_owned.bot.process_new_updates([_callback(f"gate:refund:{paid_id}",
                                                   update_id=720)])

    assert calls == [(4242, "ch_7")]
    assert wired_owned.db.get_paid_message(paid_id)["status"] == "refunded"


def test_every_new_owner_callback_runs_without_swallowing_an_error(wired_owned, monkeypatch,
                                                                  caplog):
    """Press every new button with real data behind it.

    The handlers catch their own exceptions (an owner screen must never kill the
    polling loop), so this test asserts on the *logs*: a swallowed exception is
    the only visible trace of a broken screen.
    """
    import logging

    monkeypatch.setattr("telegram_api.get_chat",
                        lambda ref: {"title": "قناتي", "type": "channel"})
    wired_owned.db.add_required_channel("@required", title="قناة", invite_link="https://t.me/required")
    wired_owned.db.set_setting("require_subscription_enabled", True)
    wired_owned.db.set_setting("paid_messages_enabled", True)
    wired_owned.db.set_setting("paid_message_stars", 30)

    with monkeypatch.context() as offline:
        offline.setattr("services.ai_service.is_ready", lambda: False)
        from services import rules_service
        draft = rules_service.organize("قاعدة للاختبار")
    from services import resource_service
    monkeypatch.setattr("services.resource_service.fetch_text", lambda url: ("", ""))
    resource = resource_service.add("https://example.com")
    question_id = wired_owned.db.insert_unanswered("direct", 4242, "سؤال")
    channel_id = wired_owned.db.list_required_channels()[0]["id"]
    rule_id = wired_owned.db.list_topic_rules(enabled_only=False)[0]["id"]
    payload = "pm:4242:x"
    wired_owned.db.create_paid_message(4242, 4242, payload, 30, "مدفوع")
    paid_id = wired_owned.db.get_paid_message_by_payload(payload)["id"]

    presses = [
        "rule:root", "rule:list", f"rule:toggle:{rule_id}", f"rule:no:{draft.batch}",
        "res:root", "res:list", f"res:toggle:{resource.resource_id}",
        "unans:list", f"unans:open:{question_id}", f"unans:ignore:{question_id}",
        "gate:root", "gate:sub", "gate:stars", "gate:list", "gate:toggle_sub",
        "gate:toggle_stars", "gate:toggle_channel:%d" % channel_id, "gate:free",
        f"gate:refund:{paid_id}",
        "rule:close", "res:close", "unans:close", "gate:close",
    ]
    with caplog.at_level(logging.ERROR):
        for index, data in enumerate(presses, start=800):
            wired_owned.rec.messages.clear()
            wired_owned.rec.edits.clear()
            wired_owned.rec.edits_full.clear()
            wired_owned.bot.process_new_updates([_callback(data, update_id=index)])
            assert (wired_owned.rec.messages or wired_owned.rec.edits
                    or wired_owned.rec.callbacks or wired_owned.rec.deleted), \
                f"{data} did nothing at all"

    problems = [record.getMessage() for record in caplog.records
                if record.levelno >= logging.ERROR]
    assert problems == []

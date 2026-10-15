"""Tests for database.py data-access layer: connections, customers, messages,
memory, pauses, approvals (incl. atomicity), KB, api_keys, owner_pending_input,
and reset_runtime_state."""

from __future__ import annotations

from freezegun import freeze_time

import utils

EPOCH = "1970-01-01T00:00:00+00:00"


# --- business_connections ----------------------------------------------------
def test_business_connection_roundtrip(db):
    db.upsert_business_connection("bc1", 999, True, True)
    row = db.get_business_connection("bc1")
    assert row["business_user_id"] == 999
    assert row["is_enabled"] == 1 and row["can_reply"] == 1
    db.upsert_business_connection("bc1", 999, True, False)  # conflict update
    assert db.get_business_connection("bc1")["can_reply"] == 0
    db.set_bc_enabled("bc1", False)
    assert db.get_business_connection("bc1")["is_enabled"] == 0
    assert len(db.list_business_connections()) == 1


# --- customers ---------------------------------------------------------------
def test_customer_roundtrip(db):
    db.upsert_customer("bc1", 5, "Ann", "Lee", "annlee")
    assert db.get_customer("bc1", 5)["username"] == "annlee"
    assert db.find_bcid_for_chat(5) == "bc1"


def test_find_bcid_fallback_single_connection(db):
    db.upsert_business_connection("only", 1, True, True)
    assert db.find_bcid_for_chat(424242) == "only"


def test_find_bcid_none_with_multiple(db):
    db.upsert_business_connection("a", 1, True, True)
    db.upsert_business_connection("b", 2, True, True)
    assert db.find_bcid_for_chat(424242) is None


# --- messages ----------------------------------------------------------------
def test_messages_window_by_direction(db):
    with freeze_time("2024-01-01 12:00:00"):
        db.insert_message("bc1", 5, 1, "in", "user", "a")
        db.insert_message("bc1", 5, 2, "in", "user", "b")
        db.insert_message("bc1", 5, 3, "out", "assistant", "c")
        since = utils.future_iso(-60)
        assert db.count_messages_in_window("bc1", 5, since, "in") == 2
        assert db.count_messages_in_window("bc1", 5, since, "out") == 1
        assert db.oldest_message_in_window("bc1", 5, since, "in") is not None


# --- conversation_memory -----------------------------------------------------
def test_memory_dal_order_and_trim(db):
    for i in range(5):
        db.insert_memory("bc1", 5, "user", f"m{i}")
    newest_first = [r["content"] for r in db.get_recent_memory("bc1", 5, 3)]
    assert newest_first == ["m4", "m3", "m2"]
    db.trim_memory("bc1", 5, 2)
    remaining = db.get_recent_memory("bc1", 5, 100)
    assert [r["content"] for r in remaining] == ["m4", "m3"]
    assert db.clear_all_memory() == 2


# --- paused_chats ------------------------------------------------------------
def test_pauses_dal(db):
    db.upsert_pause("bc1", 5, "manual", "2099-01-01T00:00:00+00:00")
    assert db.get_pause("bc1", 5)["reason"] == "manual"
    db.upsert_pause("bc1", 5, "rate_limit", None)  # conflict update -> indefinite
    row = db.get_pause("bc1", 5)
    assert row["reason"] == "rate_limit" and row["paused_until"] is None
    assert len(db.list_active_pauses()) == 1
    assert db.delete_pause("bc1", 5) == 1
    assert db.delete_pause("bc1", 5) == 0


def test_list_active_pauses_excludes_expired_deadlines(db):
    with freeze_time("2024-01-01 12:00:00"):
        db.upsert_pause("bc1", 5, "rate_limit", utils.future_iso(30))
        db.upsert_pause("bc1", 6, "manual", None)

    with freeze_time("2024-01-01 13:00:00"):
        active_chat_ids = [row["customer_chat_id"] for row in db.list_active_pauses()]

    assert active_chat_ids == [6]
    assert db.get_pause("bc1", 5) is not None  # enforcement still owns lazy cleanup


# --- pending_approvals -------------------------------------------------------
def test_mark_approval_is_atomic(db):
    aid = db.insert_pending_approval("bc1", 5, 22, "c", "r")
    assert db.mark_approval(aid, "sent") is True
    assert db.mark_approval(aid, "sent") is False  # double-tap loses


def test_approval_delivery_claim_can_be_released_or_completed(db):
    aid = db.insert_pending_approval("bc1", 5, 22, "customer", "reply")

    assert db.claim_approval_delivery(aid) is True
    assert db.claim_approval_delivery(aid) is False
    assert db.get_approval(aid)["status"] == "sending"
    assert db.get_approval(aid)["decided_at"] is not None

    assert db.release_approval_delivery(aid) is True
    assert db.get_approval(aid)["status"] == "pending"

    assert db.claim_approval_delivery(aid) is True
    assert db.complete_approval_delivery(aid, "sent") is True
    assert db.get_approval(aid)["status"] == "sent"


def test_reinitialization_quarantines_interrupted_delivery_claim(
    db, fake_config
):
    aid = db.insert_pending_approval("bc1", 5, 22, "customer", "reply")
    assert db.claim_approval_delivery(aid) is True

    conn = db._local.conn
    conn.close()
    del db._local.conn

    assert db.init_db(fake_config) == 1
    approval = db.get_approval(aid)
    assert approval["status"] == "delivery_uncertain"
    assert approval["decided_at"] is not None
    assert db.init_db(fake_config) == 0


def test_find_open_approval_matches_message_id(db):
    aid = db.insert_pending_approval("bc1", 5, 22, "c", "r")
    assert db.find_open_approval("bc1", 5, 22)["id"] == aid
    assert db.find_open_approval("bc1", 5, 999) is None
    aid2 = db.insert_pending_approval("bc1", 6, None, "c", "r")
    assert db.find_open_approval("bc1", 6, None)["id"] == aid2


def test_invalidate_and_count(db):
    a1 = db.insert_pending_approval("bc1", 5, 22, "c", "r")
    assert db.count_pending_approvals() == 1
    assert db.invalidate_approvals_for_messages("bc1", 5, [22]) == 1
    assert db.get_approval(a1)["status"] == "invalidated"
    assert db.invalidate_approvals_for_messages("bc1", 5, [22]) == 0


def test_expire_stale_approvals(db):
    with freeze_time("2024-01-01 12:00:00"):
        aid = db.insert_pending_approval("bc1", 5, 22, "c", "r")
    with freeze_time("2024-01-01 18:00:00"):
        assert db.expire_stale_approvals(60) == 1
        assert db.get_approval(aid)["status"] == "expired"


def test_cancel_all_pending(db):
    db.insert_pending_approval("bc1", 5, 22, "c", "r")
    assert db.cancel_all_pending_approvals() == 1


# --- kb_items / kb_chunks ----------------------------------------------------
def test_kb_cascade_delete(db):
    item = db.insert_kb_item("Title", "text", None)
    db.insert_kb_chunks_bulk([(item, 0, "hello", None), (item, 1, "world", None)])
    db.set_kb_item_chunk_count(item, 2)
    assert db.get_kb_item(item)["chunk_count"] == 2
    assert db.count_kb_chunks() == 2
    assert db.delete_kb_item(item) == 1
    assert db.count_kb_chunks() == 0  # FK ON DELETE CASCADE


def test_clear_kb(db):
    item = db.insert_kb_item("T", "text", None)
    db.insert_kb_chunks_bulk([(item, 0, "x", None)])
    db.clear_kb()
    assert db.count_kb_chunks() == 0 and db.list_kb_items() == []


# --- api_keys ----------------------------------------------------------------
def test_api_key_roundtrip(db):
    db.upsert_api_key("openai", "sk-...123", "plain:secret")
    assert db.get_api_key_row("openai")["masked_key"] == "sk-...123"
    db.upsert_api_key("openai", "sk-...456", "plain:secret2")
    assert db.get_api_key_row("openai")["encrypted_key_or_plain_local_key"] == "plain:secret2"
    assert db.delete_api_key("openai") == 1


# --- owner_pending_input -----------------------------------------------------
def test_owner_pending_input_roundtrip(db):
    db.set_owner_pending_input(12345, "kb_add", {"foo": "bar"}, 15)
    state = db.get_owner_pending_input(12345)
    assert state["kind"] == "kb_add" and state["context"] == {"foo": "bar"}
    assert db.has_owner_pending_input(12345) is True
    db.clear_owner_pending_input(12345)
    assert db.get_owner_pending_input(12345) is None


def test_owner_pending_input_expiry_self_clears(db):
    with freeze_time("2024-01-01 12:00:00"):
        db.set_owner_pending_input(1, "x", {}, 5)
    with freeze_time("2024-01-01 12:10:00"):
        assert db.get_owner_pending_input(1) is None


def test_owner_pending_input_bad_json(db):
    db.set_owner_pending_input(1, "x", {}, 15)
    with db.write_tx() as cur:
        cur.execute("UPDATE owner_pending_input SET context_json='{bad' WHERE owner_user_id=1")
    assert db.get_owner_pending_input(1)["context"] == {}


# --- reset_runtime_state -----------------------------------------------------
def test_reset_runtime_state(db):
    db.set_setting("auto_reply_enabled", True)
    db.upsert_pause("bc1", 5, "manual", None)
    db.set_owner_pending_input(1, "x", {}, 15)
    aid = db.insert_pending_approval("bc1", 5, 22, "c", "r")
    db.upsert_business_connection("bc1", 999, True, True)
    db.upsert_customer("bc1", 5, "A", None, None)
    db.insert_kb_item("T", "text", None)

    db.reset_runtime_state()

    assert db.get_bool("auto_reply_enabled") is False  # back to seeded default
    assert db.list_active_pauses() == []
    assert db.get_owner_pending_input(1) is None
    assert db.get_approval(aid)["status"] == "cancelled"
    # Preserved data:
    assert db.get_business_connection("bc1") is not None
    assert db.get_customer("bc1", 5) is not None
    assert len(db.list_kb_items()) == 1


# --- message bookkeeping (dedupe, history, stats) ----------------------------
def test_message_exists_dedupes_redelivered_updates(db):
    assert db.message_exists("bc1", 5, 22) is False
    db.insert_message("bc1", 5, 22, "in", "user", "hello")
    assert db.message_exists("bc1", 5, 22) is True
    assert db.message_exists("bc1", 5, 23) is False
    assert db.message_exists("bc1", 5, 22, direction="out") is False
    assert db.message_exists("bc1", 5, None) is False


def test_get_recent_messages_is_chronological_and_limited(db):
    for index in range(5):
        db.insert_message("bc1", 5, index, "in", "user", f"m{index}")
    rows = db.get_recent_messages("bc1", 5, limit=3)
    assert [r["content"] for r in rows] == ["m2", "m3", "m4"]


def test_list_recent_customer_chats_orders_by_activity(db):
    db.upsert_customer("bc1", 5, "Older", None, None)
    db.upsert_customer("bc1", 6, "Newer", None, None)
    db.insert_message("bc1", 5, 1, "in", "user", "hi")
    db.insert_message("bc1", 6, 2, "in", "user", "hello")
    db.insert_message("bc1", 6, 3, "in", "user", "again")
    rows = db.list_recent_customer_chats(limit=5)
    assert {r["customer_chat_id"] for r in rows} == {5, 6}
    counts = {r["customer_chat_id"]: r["message_count"] for r in rows}
    assert counts[6] == 2


def test_count_helpers(db):
    db.insert_message("bc1", 5, 1, "in", "user", "a")
    db.insert_message("bc1", 5, None, "out", "assistant", "b")
    db.insert_message("bc1", 5, None, "out", "owner", "c")
    db.upsert_customer("bc1", 5, "C", None, None)
    db.insert_pending_approval("bc1", 5, 1, "c", "r")

    assert db.count_messages() == 3
    assert db.count_messages(direction="in") == 1
    assert db.count_messages(direction="out", role="assistant") == 1
    assert db.count_ai_replies() == 1
    assert db.count_customers() == 1
    assert db.count_approvals() == 1
    assert db.count_approvals("pending") == 1
    assert db.count_approvals("sent") == 0


def test_count_messages_since_filter(db):
    db.insert_message("bc1", 5, 1, "in", "user", "old")
    assert db.count_messages(direction="in", since_iso="2999-01-01T00:00:00+00:00") == 0
    assert db.count_messages(direction="in", since_iso="1970-01-01T00:00:00+00:00") == 1


# --- FAQ DAL -----------------------------------------------------------------
def test_faq_crud(db):
    entry_id = db.insert_faq_entry("price, سعر", "500 EGP", question="How much?")
    row = db.get_faq_entry(entry_id)
    assert row["keywords"] == "price, سعر"
    assert row["enabled"] == 1

    assert db.update_faq_entry(entry_id, answer="600 EGP", enabled=False) is True
    row = db.get_faq_entry(entry_id)
    assert row["answer"] == "600 EGP" and row["enabled"] == 0
    assert db.update_faq_entry(entry_id) is False  # nothing to change

    assert [r["id"] for r in db.list_faq_entries()] == [entry_id]
    assert db.list_faq_entries(only_enabled=True) == []

    assert db.touch_faq_hit(entry_id) is None
    assert db.get_faq_entry(entry_id)["hits"] == 1
    assert db.get_faq_entry(entry_id)["last_hit_at"] is not None

    assert db.delete_faq_entry(entry_id) == 1
    assert db.delete_faq_entry(entry_id) == 0


def test_faq_replace_and_clear(db):
    db.insert_faq_entry("old", "old")
    inserted = db.replace_faq_entries([
        {"keywords": "a", "answer": "1", "question": "q", "enabled": True},
        {"keywords": "b", "answer": "2", "enabled": False},
    ])
    assert inserted == 2
    assert [r["keywords"] for r in db.list_faq_entries()] == ["a", "b"]
    assert db.clear_faq() == 2
    assert db.list_faq_entries() == []

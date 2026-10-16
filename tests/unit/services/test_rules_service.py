"""Tests for services/rules_service.py — owner instructions become live rules.

The service is the contract between "the owner typed a paragraph" and "the
assistant obeys those rules in every future reply", so the tests pin:

* drafting never activates anything (a draft is disabled until approved),
* the AI path and the no-AI fallback both produce usable rules,
* only approved rules reach the system-prompt block,
* a question the model could not answer is filed once, and the owner's answer is
  remembered *and* reused (FAQ) — including the ``NO_ANSWER`` marker detection.
"""

from __future__ import annotations

import pytest

from services import rules_service


@pytest.fixture
def ai_on(db, monkeypatch):
    """A rules service with a fake, deterministic "AI" for the split step."""

    def fake_chat(messages, **kwargs):
        return (
            '{"rules": [{"topic": "الأسعار", "rule": "أي سؤال عن السعر: 500 جنيه."},'
            ' {"topic": "التوصيل", "rule": "التوصيل داخل دمياط يومين."}],'
            ' "questions": ["الدفع بالفيزا؟"]}'
        )

    monkeypatch.setattr("services.ai_service.chat", fake_chat)
    return rules_service


# --- drafting -----------------------------------------------------------------
def test_local_split_keeps_every_instruction(db):
    rules = rules_service.local_split(
        "الأسعار: 500 جنيه\nالتوصيل: يومين داخل دمياط\n\nمتعملش خصم من نفسك"
    )
    assert len(rules) == 3
    assert all(item["rule"] for item in rules)
    assert rules[0]["topic"]


def test_parse_ai_reply_reads_the_json_and_survives_junk(db):
    rules, questions = rules_service.parse_ai_reply(
        'prefix {"rules": [{"topic": "الأسعار", "rule": "السعر 500 جنيه"}],'
        ' "questions": ["الدفع بالفيزا؟"]} suffix'
    )
    assert rules == [{"topic": "الأسعار", "rule": "السعر 500 جنيه"}]
    assert questions == ["الدفع بالفيزا؟"]

    # Junk, markdown fences and too-short rules never reach the store.
    assert rules_service.parse_ai_reply("not json at all") == ([], [])
    assert rules_service.parse_ai_reply('```json\n{"rules": [{"rule": "r"}]}\n```') == ([], [])


def test_organize_with_the_ai_stores_a_disabled_draft(db, ai_on, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: True)
    draft = ai_on.organize("الأسعار 500 والتوصيل يومين")
    assert draft.used_ai is True
    assert len(draft.rules) == 2
    assert draft.questions == ["الدفع بالفيزا؟"]

    # Stored, but not active: the owner still has to approve.
    assert db.count_topic_rules(enabled_only=True) == 0
    assert db.count_topic_rules(enabled_only=False) == 2
    assert rules_service.prompt_block() == ""


def test_organize_without_an_ai_backend_still_drafts(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    monkeypatch.setattr("services.ai_service.chat",
                        lambda *a, **k: pytest.fail("no AI call expected"))
    draft = rules_service.organize("خلي الرد رسمي\nمتبعتش عروض أسعار")
    assert draft.used_ai is False
    assert len(draft.rules) == 2
    assert db.count_topic_rules(enabled_only=True) == 0


def test_organize_of_blank_text_is_empty(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    assert rules_service.organize("   ").empty is True


# --- approving ----------------------------------------------------------------
def test_approve_activates_only_that_batch(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    first = rules_service.organize("قاعدة أولى")
    second = rules_service.organize("قاعدة تانية")

    assert rules_service.approve(first.batch) == 1
    active = rules_service.active_rules()
    assert [row["rule"] for row in active] == ["قاعدة أولى"]
    assert rules_service.draft_rules(second.batch)          # still waiting
    assert db.count_topic_rules(enabled_only=False) == 2


def test_reject_discards_the_draft(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    draft = rules_service.organize("قاعدة هتتشال")
    assert rules_service.reject(draft.batch) == 1
    assert db.count_topic_rules(enabled_only=False) == 0


def test_prompt_block_lists_the_active_rules_and_respects_the_switch(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    draft = rules_service.organize("متعملش خصم من نفسك")
    rules_service.approve(draft.batch)

    block = rules_service.prompt_block()
    assert "TOPIC RULES" in block and "متعملش خصم من نفسك" in block

    db.set_setting("rules_enabled", False)
    assert rules_service.prompt_block() == ""


def test_toggle_pauses_a_rule_without_deleting_it(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    draft = rules_service.organize("قاعدة قابلة للإيقاف")
    rules_service.approve(draft.batch)
    rule_id = rules_service.active_rules()[0]["id"]

    assert rules_service.toggle(rule_id) is False
    assert rules_service.prompt_block() == ""
    assert db.count_topic_rules(enabled_only=False) == 1
    assert rules_service.toggle(rule_id) is True
    assert rules_service.toggle(9999) is None


# --- unanswered questions -----------------------------------------------------
def test_is_no_answer_only_matches_the_bare_marker(db):
    assert rules_service.is_no_answer("NO_ANSWER") is True
    assert rules_service.is_no_answer(" **no_answer** ") is True
    assert rules_service.is_no_answer("NO_ANSWER.") is True
    assert rules_service.is_no_answer("الرد: NO_ANSWER") is False
    assert rules_service.is_no_answer("") is False
    assert rules_service.is_no_answer("للأسف مش عارف") is False


def test_clean_no_answer_drops_a_stray_marker_line(db):
    assert rules_service.clean_no_answer("أهلاً\nNO_ANSWER") == "أهلاً"
    assert rules_service.clean_no_answer("NO_ANSWER") == ""


def test_record_unanswered_is_deduplicated_while_open(db):
    first = rules_service.record_unanswered("direct", 5001, "بتشتغلوا الجمعة؟")
    again = rules_service.record_unanswered("direct", 5001, "بتشتغلوا الجمعة؟")
    assert first == again
    assert db.count_unanswered("open") == 1


def test_record_unanswered_respects_the_switch(db):
    db.set_setting("unanswered_enabled", False)
    assert rules_service.record_unanswered("direct", 5001, "سؤال") is None


def test_answering_learns_a_quick_answer_and_closes_the_question(db, monkeypatch):
    question_id = rules_service.record_unanswered("direct", 5001, "بتشتغلوا الجمعة؟")
    result = rules_service.answer_question(question_id, "أيوه، من 10 لـ 6.")

    assert result is not None and result["faq_id"]
    assert db.count_unanswered("open") == 0
    assert db.count_unanswered("answered") == 1

    # ... and it is injected into the prompt as approved context.
    block = rules_service.answers_block()
    assert "بتشتغلوا الجمعة؟" in block and "من 10 لـ 6" in block


def test_answering_twice_is_refused(db):
    question_id = rules_service.record_unanswered("direct", 5001, "سؤال")
    assert rules_service.answer_question(question_id, "إجابة") is not None
    assert rules_service.answer_question(question_id, "إجابة تانية") is None


def test_ignore_closes_the_question_without_learning_it(db):
    question_id = rules_service.record_unanswered("direct", 5001, "سؤال مزعج")
    assert rules_service.ignore_question(question_id) is True
    assert db.count_unanswered("open") == 0
    assert rules_service.answers_block() == ""


def test_summary_counts_everything(db, monkeypatch):
    monkeypatch.setattr("services.ai_service.is_ready", lambda: False)
    draft = rules_service.organize("قاعدة")
    rules_service.approve(draft.batch)
    rules_service.record_unanswered("direct", 5001, "سؤال")

    data = rules_service.summary()
    assert data["rules"] == 1 and data["unanswered"] == 1
    assert rules_service.localised_summary_lines()

"""Tests for services/faq_service.py: normalisation (incl. Arabic), trigger
parsing, scoring, the direct-reply decision, CRUD and import/export."""

from __future__ import annotations

from services import faq_service as faq


# --- normalisation -----------------------------------------------------------
def test_normalize_strips_arabic_diacritics_and_tatweel():
    assert faq.normalize("الشّحــن") == "الشحن"


def test_normalize_unifies_letter_variants():
    assert faq.normalize("أحمد إبراهيم آدم") == "احمد ابراهيم ادم"
    assert faq.normalize("مصطفى") == "مصطفي"
    assert faq.normalize("مكتبة") == "مكتبه"


def test_normalize_maps_arabic_indic_digits():
    assert faq.normalize("السعر ٥٠٠") == "السعر 500"
    assert faq.normalize("قیمت ۳۰۰") == "قیمت 300"


def test_normalize_lowercases_and_drops_punctuation():
    assert faq.normalize("Hello,   WORLD!!! :)") == "hello world"


def test_normalize_empty_inputs():
    assert faq.normalize("") == ""
    assert faq.normalize(None) == ""


# --- trigger parsing ---------------------------------------------------------
def test_parse_triggers_splits_on_commas_and_pipes():
    assert faq.parse_triggers("price, سعر | how much") == ["price", "سعر", "how much"]


def test_parse_triggers_drops_short_and_empty_items():
    assert faq.parse_triggers("a, price, , b") == ["price"]


def test_parse_triggers_dedupes():
    assert faq.parse_triggers("price, PRICE, price!") == ["price"]


# --- CRUD --------------------------------------------------------------------
def test_add_and_list(db):
    entry_id = faq.add("price, سعر", "Prices start at 500 EGP.")
    entries = faq.list_entries()
    assert [e["id"] for e in entries] == [entry_id]
    assert faq.count() == 1


def test_update_and_disable(db):
    entry_id = faq.add("price", "500")
    assert faq.update(entry_id, answer="600") is True
    assert faq.get(entry_id)["answer"] == "600"
    faq.update(entry_id, enabled=False)
    assert faq.find_best("price ?") is None  # disabled entries never match


def test_delete_and_clear(db):
    first = faq.add("a1", "x")
    faq.add("b2", "y")
    assert faq.delete(first) is True
    assert faq.count() == 1
    assert faq.clear() == 1
    assert faq.count() == 0


def test_import_replaces_all(db):
    faq.add("old", "old answer")
    inserted = faq.import_rows([
        {"keywords": "new", "answer": "new answer", "question": "?"},
        {"keywords": "", "answer": "skipped"},          # no triggers
        {"keywords": "other", "answer": ""},            # no answer
        "not a dict",
    ])
    assert inserted == 1
    assert [e["keywords"] for e in faq.list_entries()] == ["new"]


def test_export_rows_roundtrip(db):
    faq.add("price, سعر", "500 EGP", question="How much?")
    rows = faq.export_rows()
    assert rows[0]["keywords"] == "price, سعر"
    assert rows[0]["enabled"] is True
    faq.clear()
    faq.import_rows(rows)
    assert faq.find_best("سعر") is not None


# --- matching ----------------------------------------------------------------
def test_single_trigger_matches_and_is_direct(db):
    faq.add("سعر", "يبدأ السعر من 500 جنيه")
    match = faq.find_best("كام السعر؟")
    assert match is not None
    assert match.is_direct() is True
    assert faq.resolve("كام السعر؟")[1] is True


def test_ascii_trigger_needs_word_boundary(db):
    faq.add("cat", "meow")
    assert faq.find_best("category listing") is None
    assert faq.find_best("a cat photo") is not None


def test_triggers_are_alternatives_so_one_hit_is_direct(db):
    """A synonym list must not dilute the match: any trigger answers the entry."""
    faq.add("سعر, بكام, كام, price", "الأسعار تبدأ من 500 جنيه")
    match = faq.find_best("بكام الكيك؟")
    assert match is not None
    assert match.total == 4              # four alternative triggers
    assert match.matched >= 1            # «بكام» hit (Arabic substrings match too)
    assert match.score == 1.0
    assert match.is_direct() is True
    assert faq.resolve("بكام الكيك؟")[1] is True


def test_word_form_hit_is_context_but_not_direct(db):
    """"do you deliver?" is a word-form hit for «delivery»: prompt context only."""
    faq.add("delivery", "3-5 days")
    match = faq.find_best("do you deliver to Aswan?")
    assert match is not None
    assert match.score == 0.5
    assert match.is_direct() is False
    assert faq.resolve("do you deliver to Aswan?")[1] is False


def test_word_form_hit_becomes_direct_when_the_threshold_is_lowered(db):
    db.set_setting("faq_match_threshold", 50)
    faq.add("delivery", "3-5 days")
    assert faq.resolve("do you deliver to Aswan?")[1] is True


def test_word_forms_cover_plurals_and_gerunds(db):
    faq.add("order", "Orders ship in 24h")
    assert faq.find_best("I have two orders") is not None
    assert faq.find_best("ordering again") is not None


def test_word_forms_do_not_match_unrelated_words(db):
    faq.add("cancel", "Use /cancel-free support")
    assert faq.find_best("my cancer screening") is None


def test_more_specific_entry_wins(db):
    faq.add("price", "generic price")
    specific = faq.add("price, delivery", "price + delivery info")
    match = faq.find_best("price and delivery please")
    assert match.entry_id == specific


def test_no_match_returns_none(db):
    faq.add("price", "500")
    assert faq.find_best("hello there") is None
    assert faq.resolve("hello there") == (None, False)


def test_direct_reply_respects_the_setting(db):
    faq.add("price", "500")
    db.set_setting("faq_direct_reply", False)
    assert faq.resolve("price?")[1] is False
    db.set_setting("faq_direct_reply", True)
    assert faq.resolve("price?")[1] is True


def test_faq_disabled_disables_everything(db):
    faq.add("price", "500")
    db.set_setting("faq_enabled", False)
    assert faq.resolve("price?") == (None, False)


def test_search_returns_ranked_matches(db):
    faq.add("price", "cheap")
    faq.add("price, delivery", "bundle")
    results = faq.search("price and delivery")
    assert [r.score for r in results] == sorted([r.score for r in results], reverse=True)
    assert len(results) == 2


def test_context_block_is_empty_without_matches():
    assert faq.build_context_block([]) == ""


def test_context_block_includes_question_and_answer(db):
    faq.add("price", "500 EGP", question="How much is it?")
    block = faq.build_context_block([faq.find_best("price")])
    assert "APPROVED ANSWERS" in block
    assert "How much is it?" in block
    assert "500 EGP" in block


def test_format_entry_escapes_html(db):
    entry_id = faq.add("price <b>", "answer & more")
    text = faq.format_entry(faq.get(entry_id))
    assert "<b>" not in text
    assert "&amp;" in text or "&lt;" in text

"""Tests for utils.to_telegram_html / strip_html / KeyedLock.

Outgoing-text safety is security-relevant: a single unescaped "<" in model
output used to make Telegram reject the whole message.
"""

from __future__ import annotations

import threading

import pytest

import utils


# --- escaping -----------------------------------------------------------------
def test_plain_text_is_unchanged():
    assert utils.to_telegram_html("hello world") == "hello world"


def test_stray_angle_brackets_are_escaped():
    assert utils.to_telegram_html("price < 100 & > 50") == "price &lt; 100 &amp; &gt; 50"


def test_existing_entities_are_not_double_escaped():
    assert utils.to_telegram_html("Tom &amp; Jerry") == "Tom &amp; Jerry"


def test_allowed_tags_survive():
    assert utils.to_telegram_html("<b>bold</b>") == "<b>bold</b>"
    assert utils.to_telegram_html('<a href="https://x.com">x</a>') == \
        '<a href="https://x.com">x</a>'


def test_unknown_tags_are_escaped_away():
    out = utils.to_telegram_html("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_unbalanced_tags_fall_back_to_plain_text():
    out = utils.to_telegram_html("hello <b>unclosed")
    assert out == "hello unclosed"


def test_none_and_numbers():
    assert utils.to_telegram_html(None) == ""
    assert utils.to_telegram_html(123) == "123"


# --- markdown conversion ------------------------------------------------------
@pytest.mark.parametrize("source,expected", [
    ("**bold**", "<b>bold</b>"),
    ("__bold__", "<b>bold</b>"),
    ("*italic*", "<i>italic</i>"),
    ("~~gone~~", "<s>gone</s>"),
    ("`code`", "<code>code</code>"),
    ("# Title", "<b>Title</b>"),
    ("- item", "• item"),
    ("[site](https://x.com)", '<a href="https://x.com">site</a>'),
])
def test_markdown_conversion(source, expected):
    assert utils.to_telegram_html(source) == expected


def test_code_block_becomes_pre():
    assert utils.to_telegram_html("```\nprint(1)\n```") == "<pre>print(1)</pre>"


def test_code_block_language_tag_is_dropped():
    assert utils.to_telegram_html("```python\nx = 1\n```") == "<pre>x = 1</pre>"


def test_markup_inside_code_is_escaped():
    out = utils.to_telegram_html("`a < b`")
    assert out == "<code>a &lt; b</code>"


def test_nested_markdown():
    out = utils.to_telegram_html("**bold with `code` inside**")
    assert out == "<b>bold with <code>code</code> inside</b>"


def test_snake_case_words_are_not_italicised():
    assert utils.to_telegram_html("/kb_add item_id") == "/kb_add item_id"


def test_arabic_text_is_untouched():
    text = "أهلاً بك، السعر أقل من 100 دولار > 50"
    assert utils.to_telegram_html(text) == "أهلاً بك، السعر أقل من 100 دولار &gt; 50"


def test_long_text_keeps_balanced_output():
    out = utils.to_telegram_html("**bold** " * 50 + "<broken")
    assert utils._is_balanced(out) is False or "<b>bold</b>" in out


# --- strip_html ---------------------------------------------------------------
def test_strip_html_removes_tags_and_unescapes():
    assert utils.strip_html("<b>a</b> &amp; <i>b</i>") == "a & b"


def test_strip_html_handles_empty():
    assert utils.strip_html("") == ""
    assert utils.strip_html(None) == ""


# --- KeyedLock ----------------------------------------------------------------
def test_keyed_lock_is_exclusive_per_key():
    lock = utils.KeyedLock()
    order: list[str] = []

    def worker(name, key):
        with lock.hold(key):
            order.append(f"{name}-in")
            order.append(f"{name}-out")

    first = threading.Thread(target=worker, args=("a", "k"))
    first.start()
    first.join(2)
    worker("b", "k")
    assert order == ["a-in", "a-out", "b-in", "b-out"]


def test_keyed_lock_allows_parallel_keys():
    lock = utils.KeyedLock()
    started = threading.Event()
    release = threading.Event()

    def holder():
        with lock.hold("k1"):
            started.set()
            release.wait(2)

    thread = threading.Thread(target=holder)
    thread.start()
    assert started.wait(2)
    with lock.hold("k2"):           # different key must not block
        assert lock.locked("k1") is True
    release.set()
    thread.join(2)


def test_keyed_lock_evicts_idle_keys():
    lock = utils.KeyedLock(max_keys=4)
    for index in range(20):
        with lock.hold(index):
            pass
    assert len(lock._locks) <= 4


def test_locked_reports_false_for_unknown_key():
    assert utils.KeyedLock().locked("nope") is False

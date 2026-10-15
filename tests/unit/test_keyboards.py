"""Tests for keyboards.py: callback_data length safety and builder integrity."""

from __future__ import annotations

import pytest

import keyboards


def _all_callback_data(markup):
    return [btn.callback_data for row in markup.keyboard for btn in row]


# --- cb() --------------------------------------------------------------------
def test_cb_joins_with_colon():
    assert keyboards.cb("apr", "send", 42) == "apr:send:42"


def test_cb_exactly_64_bytes_ok():
    data = keyboards.cb("x" * 64)
    assert len(data.encode("utf-8")) == 64


def test_cb_65_bytes_raises():
    with pytest.raises(ValueError):
        keyboards.cb("x" * 65)


def test_cb_multibyte_boundary():
    # "é" is 2 UTF-8 bytes: 32 chars == 64 bytes (ok), 33 chars == 66 bytes (raises).
    assert len(keyboards.cb("é" * 32).encode("utf-8")) == 64
    with pytest.raises(ValueError):
        keyboards.cb("é" * 33)


# --- builders emit safe callback data ----------------------------------------
def test_control_panel_buttons_within_limit():
    kb = keyboards.control_panel(auto_on=True, approval_on=False)
    data = _all_callback_data(kb)
    assert data and all(len(d.encode("utf-8")) <= 64 for d in data)


def test_approval_actions_buttons():
    kb = keyboards.approval_actions(999999)
    data = _all_callback_data(kb)
    assert "apr:send:999999" in data
    assert all(len(d.encode("utf-8")) <= 64 for d in data)


def test_settings_root_and_enum():
    root = keyboards.settings_root([{"label": "X", "callback_data": "set:open:x"}])
    assert all(len(d.encode("utf-8")) <= 64 for d in _all_callback_data(root))
    enum = keyboards.settings_enum("openai_model", ["gpt-4o", "gpt-4.1"], "gpt-4o")
    assert all(len(d.encode("utf-8")) <= 64 for d in _all_callback_data(enum))


def test_kb_menu_and_confirm():
    assert all(len(d.encode("utf-8")) <= 64 for d in _all_callback_data(keyboards.kb_menu()))
    assert all(len(d.encode("utf-8")) <= 64 for d in _all_callback_data(keyboards.confirm("tok123")))


# --- kb_list_keyboard pagination --------------------------------------------
def _items(n):
    return [{"id": i, "title": f"Item {i}", "chunk_count": i} for i in range(n)]


def test_kb_list_first_page_has_next_only():
    kb = keyboards.kb_list_keyboard(_items(12), page=0, per_page=5)
    data = _all_callback_data(kb)
    assert any(d == "kb:list:1" for d in data)          # Next
    assert not any(d == "kb:list:-1" for d in data)     # no Prev


def test_kb_list_middle_page_has_both():
    data = _all_callback_data(keyboards.kb_list_keyboard(_items(12), page=1, per_page=5))
    assert "kb:list:0" in data and "kb:list:2" in data


def test_kb_list_last_page_has_prev_only():
    data = _all_callback_data(keyboards.kb_list_keyboard(_items(12), page=2, per_page=5))
    assert "kb:list:1" in data
    assert "kb:list:3" not in data


# --- AI provider keyboards ---------------------------------------------------
def test_ai_providers_lists_every_provider_with_a_free_marker():
    from services import providers
    markup = keyboards.ai_providers("openai")
    data = _all_callback_data(markup)
    for provider_id in providers.ids():
        assert keyboards.cb("ai", "provider", provider_id) in data
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert any("🆓" in label for label in labels)
    assert any("💻" in label for label in labels)
    assert "ai:providers_free" in data


def test_ai_providers_free_only_excludes_paid_providers():
    from services import providers
    markup = keyboards.ai_providers("groq", free_only=True)
    data = _all_callback_data(markup)
    for provider_id in providers.ids():
        expected = provider_id in providers.free_ids()
        assert (keyboards.cb("ai", "provider", provider_id) in data) is expected
    assert "ai:providers" in data           # toggle back to the full list


def test_ai_providers_marks_the_active_one():
    markup = keyboards.ai_providers("cerebras")
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert any(label.startswith("• ") and "Cerebras" in label for label in labels)


def test_ai_free_switch_offers_only_free_providers():
    from services import providers
    suggestions = providers.switch_suggestions("openai", limit=3)
    markup = keyboards.ai_free_switch(suggestions)
    data = _all_callback_data(markup)
    for provider in suggestions:
        assert keyboards.cb("ai", "freeswitch", provider.id) in data
        assert providers.is_free(provider)
    assert "ai:key" in data and "ai:root" in data


def test_ai_models_offers_a_refresh_and_a_manual_entry():
    markup = keyboards.ai_models(["gpt-4.1-mini", "gpt-4o"], "gpt-4o")
    data = _all_callback_data(markup)
    assert "ai:models_live" in data
    assert "ai:model_custom" in data
    assert "ai:model:gpt-4.1-mini" in data


def test_ai_models_can_hide_the_refresh_button():
    markup = keyboards.ai_models(["gpt-4o"], "gpt-4o", can_refresh=False)
    assert "ai:models_live" not in _all_callback_data(markup)


def test_ai_models_keeps_a_colon_in_the_callback_data():
    model = "meta-llama/llama-3.3-70b-instruct:free"
    markup = keyboards.ai_models([model], "")
    assert keyboards.cb("ai", "model", model) in _all_callback_data(markup)


def test_ai_models_skips_names_too_long_for_callback_data():
    long_model = "vendor/" + "x" * 80
    markup = keyboards.ai_models([long_model, "gpt-4o"], "gpt-4o")
    data = _all_callback_data(markup)
    assert "ai:model:gpt-4o" in data
    assert all(len(entry.encode("utf-8")) <= 64 for entry in data)


def test_ai_root_always_offers_the_free_shortcut_and_a_test():
    data = _all_callback_data(keyboards.ai_root(has_key=False, is_ready=False,
                                                provider_label="OpenAI"))
    assert "ai:providers_free" in data
    assert "ai:test" in data
    assert "ai:key" in data
    assert "ai:disconnect" not in data


def test_ai_provider_actions_hides_the_key_button_when_no_key_is_needed():
    data = _all_callback_data(keyboards.ai_provider_actions("pollinations", False))
    assert "ai:key" not in data
    assert "ai:test" in data
    assert "ai:models_live" in data

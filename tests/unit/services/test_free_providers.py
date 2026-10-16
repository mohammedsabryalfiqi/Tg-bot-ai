"""Tests for the free-provider side of the registry (services/providers.py).

The point of these tests is the owner experience that motivated them: someone
without a credit card (or whose paid key has no balance) must always find a
working zero-cost path, and the bot must never recommend a provider that
secretly needs money.
"""

from __future__ import annotations

import pytest

from services import providers
from services.ai_service import SWITCHABLE_KINDS, cost_label, hints_for


# --- registry sanity ---------------------------------------------------------
def test_ids_and_labels_are_unique():
    ids = providers.ids()
    labels = [providers.label_for(pid) for pid in ids]
    assert len(ids) == len(set(ids)) == len(providers.PROVIDERS)
    assert len(labels) == len(set(labels))


def test_free_providers_are_listed_before_paid_ones():
    ids = providers.ids()
    paid_positions = [ids.index(pid) for pid in ids
                      if providers.needs_credit(pid)]
    free_positions = [ids.index(pid) for pid in providers.free_ids()
                      if not providers.PROVIDERS[pid].local]
    assert free_positions, "there must be free hosted providers"
    assert paid_positions, "there must be paid providers"
    assert max(free_positions) < min(paid_positions)


@pytest.mark.parametrize("provider_id", [
    "google", "groq", "cerebras", "openrouter", "mistral",
    "nvidia", "sambanova", "huggingface", "pollinations", "ollama", "lmstudio",
])
def test_every_free_provider_is_usable_without_paying(provider_id):
    provider = providers.get(provider_id)
    assert provider is not None
    assert providers.is_free(provider)
    assert provider_id in providers.free_ids()
    assert not providers.needs_credit(provider_id)
    # Either no key is needed at all, or the owner is told where to get one.
    assert provider.key_url or not provider.key_required


@pytest.mark.parametrize("provider_id", ["openai", "anthropic", "deepseek", "xai", "together"])
def test_paid_providers_are_flagged_as_needing_credit(provider_id):
    provider = providers.get(provider_id)
    assert providers.needs_credit(provider_id)
    assert not provider.free_tier
    assert "paid" in cost_label(provider)


def test_free_hosted_providers_have_https_endpoints():
    for provider in providers.free():
        if provider.local:
            continue
        assert provider.base_url.startswith("https://"), provider.id


def test_free_note_is_present_for_hosted_free_tiers():
    """`/freeai` prints free_note; a free provider without one would show blank."""
    for provider in providers.free():
        if provider.free_tier:
            assert provider.free_note.strip(), provider.id


def test_key_env_var_covers_every_provider():
    for pid in providers.ids():
        env_var = providers.key_env_var(pid)
        provider = providers.PROVIDERS[pid]
        if provider.key_required:
            assert env_var, f"{pid} requires a key but has no env var"
            assert env_var.isupper()
        elif provider.id == "omniroute":
            # OmniRoute needs no key by default but accepts an optional one
            # (REQUIRE_API_KEY=true).
            assert env_var == "OMNIROUTE_API_KEY"
        else:
            assert env_var == ""


def test_new_free_providers_have_expected_env_vars():
    assert providers.key_env_var("cerebras") == "CEREBRAS_API_KEY"
    assert providers.key_env_var("nvidia") == "NVIDIA_API_KEY"
    assert providers.key_env_var("sambanova") == "SAMBANOVA_API_KEY"
    assert providers.key_env_var("huggingface") == "HF_TOKEN"


# --- suggestions -------------------------------------------------------------
def test_switch_suggestions_never_include_the_current_provider():
    for pid in providers.ids():
        for suggestion in providers.switch_suggestions(pid, limit=3):
            assert suggestion.id != pid
            assert providers.is_free(suggestion)


def test_switch_suggestions_prefers_the_generous_free_tiers():
    first = providers.switch_suggestions("openai", limit=3)[0]
    assert first.id in providers.FREE_SUGGESTIONS
    assert first.free_tier


def test_switch_suggestions_limit_is_respected():
    assert len(providers.switch_suggestions("openai", limit=2)) == 2
    assert len(providers.switch_suggestions("openai", limit=1)) == 1


def test_switchable_kinds_are_the_unfixable_by_retry_ones():
    assert "no_credit" in SWITCHABLE_KINDS
    assert "auth" in SWITCHABLE_KINDS
    assert "server" not in SWITCHABLE_KINDS
    assert "timeout" not in SWITCHABLE_KINDS


# --- free menu ---------------------------------------------------------------
def test_free_menu_lists_every_free_provider_with_its_key_url():
    lines = "\n".join(providers.free_menu_lines())
    for provider in providers.free():
        assert provider.label in lines
        if provider.key_url:
            assert provider.key_url in lines


def test_free_menu_mentions_the_no_key_option():
    lines = "\n".join(providers.free_menu_lines())
    assert "No API key needed" in lines


def test_no_provider_label_carries_an_emoji_the_ui_also_adds():
    """The picker appends 🆓/💻 markers; a label with the same emoji doubles it."""
    for provider in providers.ordered():
        assert "🆓" not in provider.label
        assert "💻" not in provider.label


# --- hints -------------------------------------------------------------------
def test_hints_for_no_credit_point_at_free_providers():
    hints = "\n".join(hints_for("no_credit", providers.get("openai")))
    assert "free" in hints.lower()
    assert "not a broken key" in hints


def test_hints_for_auth_include_provider_specific_advice():
    hints = "\n".join(hints_for("auth", providers.get("google")))
    assert "aistudio.google.com" in hints


def test_hints_for_model_point_at_the_live_model_list():
    hints = "\n".join(hints_for("model", providers.get("groq")))
    assert "Load models" in hints


def test_hints_are_deduplicated():
    hints = hints_for("auth", providers.get("openai"))
    assert len(hints) == len(set(hints))

"""Tests for AI failure diagnosis (services/ai_service.py).

These cover the confusion this feature exists to remove: a brand-new API key that
"does not work" must be reported as what it actually is — a rejected key, an
account with no credit, an unknown model name, a free-tier rate limit or a region
block — each with the fix, and (where switching helps) free alternatives.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import ai_service as svc
from services import providers


def _response(status, body=None, text=""):
    if body is None:
        def _json():
            raise ValueError("no json")
    else:
        def _json():
            return body
    return SimpleNamespace(status_code=status, headers={}, json=_json, text=text)


def _error(status, message, code="", err_type=""):
    return _response(status, {"error": {"message": message, "code": code, "type": err_type}})


# --- classification ----------------------------------------------------------
def test_openai_insufficient_quota_is_no_credit_not_a_bad_key():
    error = svc._error_from_response(_error(
        429, "You exceeded your current quota, please check your plan and billing details.",
        code="insufficient_quota"), providers.get("openai"))
    assert error.kind == "no_credit"
    assert "no credit" in error.owner_message
    assert any("free" in hint.lower() for hint in error.hints)


def test_payment_required_is_no_credit():
    error = svc._error_from_response(_error(402, "Payment required."), providers.get("deepseek"))
    assert error.kind == "no_credit"
    assert any("top" in hint.lower() or "credit" in hint.lower() for hint in error.hints)


def test_insufficient_balance_wording_is_no_credit():
    error = svc._error_from_response(
        _error(403, "Insufficient balance, please recharge your account."),
        providers.get("deepseek"))
    assert error.kind == "no_credit"


def test_wrong_key_is_auth():
    error = svc._error_from_response(
        _error(401, "Incorrect API key provided: sk-abc**xyz."),
        providers.get("openai"))
    assert error.kind == "auth"
    assert "rejected this API key" in error.owner_message
    assert any("THIS provider" in hint for hint in error.hints)


def test_google_permission_denied_is_auth_with_a_google_specific_hint():
    error = svc._error_from_response(
        _error(403, "API key not valid. Please pass a valid API key."),
        providers.get("google"))
    assert error.kind == "auth"
    assert any("aistudio.google.com" in hint for hint in error.hints)


def test_unknown_model_is_model_kind():
    error = svc._error_from_response(
        _error(404, "The model `gpt-4o-2024-99` does not exist", code="model_not_found"),
        providers.get("openai"))
    assert error.kind == "model"
    assert any("Load models" in hint for hint in error.hints)


def test_model_access_denied_is_model_kind():
    error = svc._error_from_response(
        _error(400, "You do not have access to model meta-llama/Llama-3.3-70B-Instruct"),
        providers.get("huggingface"))
    assert error.kind == "model"


def test_free_tier_rate_limit_is_rate_limit_not_no_credit():
    error = svc._error_from_response(
        _error(429, "Rate limit reached for requests per minute. Please retry after 30s."),
        providers.get("groq"))
    assert error.kind == "rate_limit"
    assert any("resets" in hint.lower() or "wait" in hint.lower() for hint in error.hints)


def test_region_block_is_its_own_kind():
    error = svc._error_from_response(
        _error(403, "The service is not available in your country or region."),
        providers.get("openai"))
    assert error.kind == "region"
    assert "country/region" in error.owner_message


def test_plain_404_blames_the_base_url():
    error = svc._error_from_response(_error(404, "Not Found"), providers.get("custom"))
    assert error.kind == "bad_request"
    assert "/v1" in error.owner_message


def test_server_error_stays_retryable():
    error = svc._error_from_response(_error(503, "upstream unavailable"), providers.get("groq"))
    assert error.kind == "server"


def test_param_errors_stay_bad_request_so_the_chat_retry_can_fix_them():
    error = svc._error_from_response(
        _error(400, "Unsupported value: 'max_tokens' is not supported with this model"),
        providers.get("openai"))
    assert error.kind == "bad_request"
    assert "max_tokens" in error.owner_message


def test_non_json_error_body_is_still_classified():
    error = svc._error_from_response(_response(401, text="Unauthorized"), providers.get("groq"))
    assert error.kind == "auth"


def test_provider_without_key_gets_a_generic_label():
    error = svc._error_from_response(_error(401, "bad key"))
    assert error.kind == "auth"
    assert error.owner_message.startswith("The provider")


# --- check_key ---------------------------------------------------------------
def test_check_key_success_reports_model_and_latency(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _response(200, {"choices": [{"message": {"content": "ok"}}]}))
    result = svc.check_key("groq", "gsk-test")
    assert result.ok is True
    assert "groq" not in result.message.lower() or "Groq" in result.message
    assert result.model == providers.get("groq").default_model
    assert result.elapsed is not None


def test_check_key_no_credit_suggests_free_providers(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _error(
        429, "You exceeded your current quota, please check your plan and billing details.",
        code="insufficient_quota"))
    result = svc.check_key("openai", "sk-test")
    assert result.ok is False
    assert result.kind == "no_credit"
    assert result.suggestions
    assert all(providers.is_free(p) for p in result.suggestions)
    assert all(p.id != "openai" for p in result.suggestions)


def test_check_key_auth_failure_suggests_free_providers(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _error(401, "Incorrect API key provided."))
    result = svc.check_key("openai", "sk-test")
    assert result.kind == "auth"
    assert result.suggestions


def test_check_key_server_error_does_not_suggest_switching(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _error(500, "boom"))
    result = svc.check_key("groq", "gsk-test")
    assert result.ok is False
    assert result.kind == "server"
    assert result.suggestions == ()


def test_check_key_missing_key_explains_how_to_add_one(db):
    result = svc.check_key("google", "")
    assert result.ok is False
    assert result.kind == "no_key"
    assert any("aistudio.google.com" in hint for hint in result.hints)


def test_check_key_unknown_provider(db):
    assert svc.check_key("nope", "x").ok is False


def test_validate_key_wrapper_still_returns_a_pair(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _error(401, "Incorrect API key provided."))
    ok, message = svc.validate_key("openai", "sk-test")
    assert ok is False
    assert "rejected" in message


def test_no_key_needed_provider_can_be_checked_without_a_key(db, monkeypatch):
    db.set_setting("ai_provider", "pollinations")
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _response(200, {"choices": [{"message": {"content": "ok"}}]}))
    result = svc.check_key("pollinations", "")
    assert result.ok is True


def test_check_connection_uses_the_stored_key(db, monkeypatch):
    db.set_setting("ai_provider", "groq")
    svc.store_api_key("gsk-stored", "groq")
    seen = {}

    def _post(url, headers=None, json=None, timeout=None):
        seen["auth"] = headers.get("Authorization")
        seen["url"] = url
        return _response(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(svc.requests, "post", _post)
    result = svc.check_connection()
    assert result.ok is True
    assert seen["auth"] == "Bearer gsk-stored"
    assert seen["url"].endswith("/chat/completions")
    ok, message = svc.test_connection()
    assert ok is True and message


# --- live model catalogue ----------------------------------------------------
def _models_response(ids):
    return _response(200, {"object": "list", "data": [{"id": name} for name in ids]})


def test_list_models_parses_the_openai_shape(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: _models_response(
        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "whisper-large-v3"]))
    models = svc.list_models("groq")
    assert "llama-3.3-70b-versatile" in models
    # registry suggestion first, non-chat models last
    assert models.index("llama-3.3-70b-versatile") < models.index("whisper-large-v3")


def test_list_models_parses_plain_strings_and_dicts(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "get",
                        lambda *a, **k: _response(200, {"models": {"openai": {"tier": "free"}}}))
    assert svc.list_models("pollinations") == ["openai"]


def test_list_models_puts_free_openrouter_models_first(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: _models_response(
        ["openai/gpt-4o", "meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-3.5-haiku"]))
    models = svc.list_models("openrouter")
    assert models[0] == "meta-llama/llama-3.3-70b-instruct:free"


def test_list_models_marks_the_current_model_first(db, monkeypatch):
    svc.set_model("mistral-small-latest", "mistral")
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: _models_response(
        ["ministral-3b", "codestral-latest", "mistral-small-latest"]))
    assert svc.list_models("mistral")[0] == "mistral-small-latest"


def test_list_models_is_capped(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "get",
                        lambda *a, **k: _models_response([f"model-{i}" for i in range(200)]))
    assert len(svc.list_models("groq")) == svc.MODEL_LIST_LIMIT


def test_list_models_sends_the_key_as_bearer(db, monkeypatch):
    svc.store_api_key("gsk-secret", "groq")
    seen = {}

    def _get(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return _models_response(["llama-3.3-70b-versatile"])

    monkeypatch.setattr(svc.requests, "get", _get)
    svc.list_models("groq")
    assert seen["url"] == "https://api.groq.com/openai/v1/models"
    assert seen["headers"]["Authorization"] == "Bearer gsk-secret"


def test_list_models_uses_the_anthropic_headers(db, monkeypatch):
    seen = {}

    def _get(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return _models_response(["claude-3-5-haiku-latest"])

    monkeypatch.setattr(svc.requests, "get", _get)
    svc.list_models("anthropic", key="sk-ant-1")
    assert seen["url"].endswith("/v1/models")
    assert seen["headers"]["x-api-key"] == "sk-ant-1"
    assert "anthropic-version" in seen["headers"]


def test_list_models_failure_is_an_owner_safe_error(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "get",
                        lambda *a, **k: _error(401, "Incorrect API key provided."))
    with pytest.raises(svc.AIServiceError) as info:
        svc.list_models("openai", key="sk-bad")
    assert info.value.kind == "auth"
    assert info.value.hints


def test_list_models_without_base_url(db):
    with pytest.raises(svc.AIServiceError):
        svc.list_models("custom")


def test_list_models_for_codex_is_empty(db):
    assert svc.list_models("codex") == []


def test_list_models_network_failure(db, monkeypatch):
    import requests

    def _boom(*a, **k):
        raise requests.ConnectionError("dns down")

    monkeypatch.setattr(svc.requests, "get", _boom)
    with pytest.raises(svc.AIServiceError) as info:
        svc.list_models("groq")
    assert info.value.kind == "connection"
    assert info.value.hints


# --- pasted-key shape checks (the two classic setup mistakes) ----------------
def test_clean_key_strips_quotes_bearer_and_line_breaks():
    assert svc._clean_key('  "sk-abc123"  ') == "sk-abc123"
    assert svc._clean_key("Bearer sk-abc123") == "sk-abc123"
    assert svc._clean_key("sk-abc\n123") == "sk-abc123"
    assert svc._clean_key("`gsk_x`") == "gsk_x"


def test_store_api_key_saves_the_cleaned_key(db):
    svc.store_api_key('  "gsk-clean"  ', "groq")
    assert svc.resolve_api_key("groq") == "gsk-clean"


def test_bot_token_pasted_as_an_ai_key_is_named_as_such(db, monkeypatch):
    called = []
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: called.append(1) or _response(200, {}))
    result = svc.check_key("groq", "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
    assert result.ok is False
    assert result.kind == "auth"
    assert "bot token" in result.message
    assert "@BotFather" in result.message
    assert called == []                     # never wastes a request on it
    assert result.suggestions


def test_a_key_from_another_provider_is_named_as_such(db, monkeypatch):
    called = []
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: called.append(1) or _response(200, {}))
    result = svc.check_key("groq", "AIzaSyDUMMY-1234567890")
    assert result.ok is False
    assert "Google Gemini" in result.message
    assert "Groq" in result.message
    assert called == []
    assert any("aistudio.google.com" in hint for hint in result.hints)


def test_the_right_shape_key_is_actually_probed(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _response(200, {"choices": [{"message": {"content": "ok"}}]}))
    result = svc.check_key("groq", "gsk-test-123")
    assert result.ok is True


def test_unknown_key_shape_is_never_rejected_before_the_probe(db, monkeypatch):
    """Mistral/Together/SambaNova publish no prefix — do not guess, just test."""
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _response(200, {"choices": [{"message": {"content": "ok"}}]}))
    assert svc.check_key("mistral", "some-random-shape").ok is True


def test_an_ambiguous_sk_key_is_not_blamed_on_the_wrong_provider(db, monkeypatch):
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _response(200, {"choices": [{"message": {"content": "ok"}}]}))
    # Both OpenAI and DeepSeek keys start with "sk-"; adding it to DeepSeek is fine.
    assert svc.check_key("deepseek", "sk-deepseek-key").ok is True


def test_key_prefix_matches_reports_every_candidate():
    matches = [p.id for p in providers.key_prefix_matches("sk-or-v1-abcdef")]
    assert matches[0] == "openrouter"          # longest prefix wins the ordering
    assert "openai" in matches
    assert providers.looks_like_key_of("sk-or-v1-abcdef").id == "openrouter"


def test_looks_like_key_of_is_none_when_ambiguous_or_unknown():
    assert providers.looks_like_key_of("sk-plain") is None
    assert providers.looks_like_key_of("whatever") is None
    assert providers.looks_like_key_of("") is None


def test_keyless_providers_never_report_a_shape_problem():
    assert svc.key_shape_problem(providers.get("pollinations"), "") is None
    assert svc.key_shape_problem(providers.get("ollama"), "") is None


# --- free-tier quota vs. running out of money --------------------------------
def test_gemini_resource_exhausted_is_a_rate_limit_not_missing_credit():
    error = svc._error_from_response(
        _error(429, "Resource has been exhausted (e.g. check quota).", code="RESOURCE_EXHAUSTED"),
        providers.get("google"))
    assert error.kind == "rate_limit"
    assert "nothing is broken" in error.owner_message
    assert any("reset" in hint.lower() for hint in error.hints)


def test_daily_quota_wording_is_a_rate_limit():
    error = svc._error_from_response(
        _error(429, "You exceeded your current requests list."), providers.get("google"))
    assert error.kind == "rate_limit"


def test_pollinations_402_is_the_throttle_not_a_bill():
    error = svc._error_from_response(_error(402, "Payment Required"),
                                     providers.get("pollinations"))
    assert error.kind == "rate_limit"
    assert "30 seconds" in error.owner_message


def test_deepseek_recharge_is_missing_credit():
    error = svc._error_from_response(
        _error(403, "Insufficient balance, please recharge your account."),
        providers.get("deepseek"))
    assert error.kind == "no_credit"
    assert any("top" in hint.lower() or "credit" in hint.lower() for hint in error.hints)

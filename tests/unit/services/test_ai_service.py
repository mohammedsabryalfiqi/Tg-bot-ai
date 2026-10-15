"""Tests for the provider-agnostic AI layer (services/ai_service.py).

The HTTP layer is mocked (``requests.post``) so the whole matrix of providers is
covered without network access: OpenAI-compatible endpoints, Anthropic's native
Messages API and the Codex CLI bridge.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import ai_service as svc
from services import providers


def _http_ok(payload):
    return SimpleNamespace(status_code=200, headers={}, json=lambda: payload)


def _http_error(status, message="nope"):
    return SimpleNamespace(status_code=status, headers={},
                           json=lambda: {"error": {"message": message}})


def _openai_body(content="hello"):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


# --- key protection ----------------------------------------------------------
def test_protect_unprotect_fernet_roundtrip(fernet_env):
    stored = svc._protect("sk-secret-value")
    assert stored.startswith("fernet:")
    assert svc._unprotect(stored) == "sk-secret-value"


def test_protect_plain_fallback_without_key():
    stored = svc._protect("sk-secret")
    assert stored.startswith("plain:")
    assert svc._unprotect(stored) == "sk-secret"


def test_unprotect_handles_missing_and_legacy():
    assert svc._unprotect(None) is None
    assert svc._unprotect("legacy-unprefixed") == "legacy-unprefixed"


def test_unprotect_wrong_key_returns_none(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("SMARTEL_FERNET_KEY", Fernet.generate_key().decode())
    stored = svc._protect("sk-secret")
    monkeypatch.setenv("SMARTEL_FERNET_KEY", Fernet.generate_key().decode())
    assert svc._unprotect(stored) is None


# --- provider / model resolution --------------------------------------------
def test_default_provider_is_openai(db):
    assert svc.active_provider_id() == "openai"
    assert svc.active_model_label() == "gpt-4.1-mini"


def test_env_provider_is_used_when_db_is_default(db, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    assert svc.active_provider_id() == "groq"
    assert svc.active_model_label() == "llama-3.3-70b-versatile"


def test_db_setting_wins_over_env(db, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    db.set_setting("ai_provider", "deepseek")
    assert svc.active_provider_id() == "deepseek"


def test_legacy_model_backend_codex_maps_to_codex_provider(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "codex")
    assert svc.active_provider_id() == "codex"


def test_legacy_openai_base_url_maps_to_custom(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    assert svc.active_provider_id() == "custom"
    assert svc.active_base_url() == "http://localhost:1234/v1"


def test_custom_provider_base_url_is_read_from_settings(db):
    db.set_setting("ai_provider", "custom")
    db.set_setting("ai_base_url", "http://my-proxy:8080/v1")
    assert svc.active_base_url() == "http://my-proxy:8080/v1"
    assert "my-proxy" in svc.backend_label()


def test_model_per_provider_is_remembered(db):
    svc.set_model("gpt-4o", "openai")
    svc.set_model("llama-3.1-8b-instant", "groq")
    assert svc.active_model("openai") == "gpt-4o"
    assert svc.active_model("groq") == "llama-3.1-8b-instant"
    assert svc.has_explicit_model("groq") is True
    assert svc.has_explicit_model("mistral") is False


def test_broken_model_map_falls_back_to_default(db):
    db.set_setting("ai_model_by_provider", "{not json")
    assert svc.active_model("openai") in {"gpt-4.1-mini", db.get_str("openai_model")}


# --- readiness / labels ------------------------------------------------------
def test_not_ready_without_key(db):
    assert svc.is_ready() is False
    assert svc.masked_active_key() == "<not set>"


def test_ready_with_stored_key(db, fernet_env):
    svc.store_api_key("sk-test-key-123456", "openai")
    assert svc.is_ready() is True
    assert svc.key_source("openai") == "db"
    assert svc.masked_active_key() == "sk-...3456"


def test_env_key_wins_over_db(db, monkeypatch, fernet_env):
    svc.store_api_key("sk-stored-key-1234", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key-9999")
    assert svc.resolve_api_key() == "sk-env-key-9999"
    assert svc.key_source() == "env"


def test_local_providers_need_no_key(db):
    db.set_setting("ai_provider", "ollama")
    assert svc.is_ready() is True  # has a default base URL, no key required


def test_custom_provider_ready_only_with_base_url(db):
    db.set_setting("ai_provider", "custom")
    assert svc.is_ready() is False
    db.set_setting("ai_base_url", "http://localhost:9000/v1")
    assert svc.is_ready() is True


def test_disconnect_removes_key(db, fernet_env):
    svc.store_api_key("sk-test-key-123456", "openai")
    svc.disconnect_api_key("openai")
    assert svc.has_api_key("openai") is False
    assert svc.is_ready() is False


# --- openai-compatible chat --------------------------------------------------
def test_chat_openai_compatible(db, monkeypatch, fernet_env):
    svc.store_api_key("sk-test-key-123456", "openai")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)
        return _http_ok(_openai_body("Hi there"))

    monkeypatch.setattr(svc.requests, "post", fake_post)
    out = svc.chat([{"role": "user", "content": "hello"}])
    assert out == "Hi there"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test-key-123456"
    assert captured["payload"]["model"] == "gpt-4.1-mini"
    assert captured["payload"]["max_tokens"] == 800


def test_chat_groq_uses_its_base_url(db, monkeypatch):
    db.set_setting("ai_provider", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-123456")
    captured = {}
    monkeypatch.setattr(
        svc.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (
            captured.update(url=url), _http_ok(_openai_body("ok")))[1],
    )
    assert svc.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"


def test_reasoning_models_use_max_completion_tokens(db, monkeypatch):
    db.set_setting("ai_provider", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    svc.set_model("o4-mini", "openai")
    captured = {}
    monkeypatch.setattr(
        svc.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (
            captured.update(payload=json), _http_ok(_openai_body("ok")))[1],
    )
    svc.chat([{"role": "user", "content": "hi"}], max_tokens=64)
    assert captured["payload"]["max_completion_tokens"] == 64
    assert "max_tokens" not in captured["payload"]


def test_chat_retries_with_max_completion_tokens_on_bad_request(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    calls = {"n": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _http_error(400, "Unsupported parameter: 'max_tokens'")
        return _http_ok(_openai_body("recovered"))

    monkeypatch.setattr(svc.requests, "post", fake_post)
    assert svc.chat([{"role": "user", "content": "hi"}]) == "recovered"
    assert calls["n"] == 2


def test_chat_auth_error_mapping(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _http_error(401, "Incorrect API key"))
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "auth"
    assert "key" in err.value.owner_message.lower()


def test_chat_rate_limit_mapping(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _http_error(429, "slow down"))
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "rate_limit"


def test_chat_network_error_mapping(db, monkeypatch):
    import requests
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")

    def boom(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(svc.requests, "post", boom)
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "connection"


def test_chat_without_key_raises_no_key(db):
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "no_key"


def test_chat_server_error_is_retried_then_raised(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _http_error(503, "unavailable")

    monkeypatch.setattr(svc.requests, "post", fake_post)
    monkeypatch.setattr(svc.time, "sleep", lambda *_: None)
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "server"
    assert calls["n"] == svc.MAX_ATTEMPTS


def test_chat_empty_reply_raises(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    monkeypatch.setattr(svc.requests, "post",
                        lambda *a, **k: _http_ok({"choices": [{"message": {"content": ""}}]}))
    with pytest.raises(svc.AIServiceError) as err:
        svc.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == "unknown"


# --- Anthropic native API ----------------------------------------------------
def test_chat_anthropic_uses_messages_api(db, monkeypatch):
    db.set_setting("ai_provider", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-123456")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)
        return _http_ok({"content": [{"type": "text", "text": "Bonjour"}]})

    monkeypatch.setattr(svc.requests, "post", fake_post)
    out = svc.chat([
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "salut"},
    ])
    assert out == "Bonjour"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-ant-123456"
    assert captured["payload"]["system"] == "be nice"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "salut"}]


# --- embeddings --------------------------------------------------------------
def test_embed_uses_openai_when_provider_cannot_embed(db, monkeypatch):
    db.set_setting("ai_provider", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-123")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-embed")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, payload=json)
        return _http_ok({"data": [{"embedding": [0.1, 0.2]}]})

    monkeypatch.setattr(svc.requests, "post", fake_post)
    vectors = svc.embed(["hello"])
    assert vectors == [[0.1, 0.2]]
    assert captured["url"].endswith("/embeddings")
    assert captured["payload"]["model"] == "text-embedding-3-small"


def test_embed_raises_without_any_embedding_provider(db):
    db.set_setting("ai_provider", "groq")
    with pytest.raises(svc.AIServiceError) as err:
        svc.embed(["hello"])
    assert err.value.kind == "no_embeddings"


def test_supports_embeddings_flags(db):
    assert svc.supports_embeddings() is True          # openai by default
    db.set_setting("ai_provider", "anthropic")
    assert svc.supports_embeddings() is False


# --- validation / test -------------------------------------------------------
def test_validate_key_success(db, monkeypatch):
    monkeypatch.setattr(svc, "_probe", lambda provider, key, model: "ok")
    ok, message = svc.validate_key("openai", "sk-test-1234")
    assert ok is True
    assert "ok" in message


def test_validate_key_maps_errors(db, monkeypatch):
    def boom(*_a, **_k):
        raise svc.AIServiceError("bad key", kind="auth")

    monkeypatch.setattr(svc, "_probe", boom)
    ok, message = svc.validate_key("openai", "sk-test-1234")
    assert ok is False
    assert message == "bad key"


def test_validate_key_requires_a_key_for_key_providers(db):
    ok, message = svc.validate_key("openai", "")
    assert ok is False
    assert "No API key" in message


def test_validate_key_without_key_for_local_provider(db, monkeypatch):
    db.set_setting("ai_provider", "ollama")
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _http_ok(_openai_body("ok")))
    ok, _ = svc.validate_key("ollama", "")
    assert ok is True


def test_test_connection_reports_status(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _http_ok(_openai_body("ok")))
    ok, message = svc.test_connection()
    assert ok is True
    assert "s)" in message or "ok" in message.lower()


def test_status_lines_include_provider_and_embeddings(db):
    lines = " ".join(svc.status_lines())
    assert "OpenAI" in lines
    assert "Embeddings" in lines


# --- provider registry -------------------------------------------------------
def test_registry_ordering_is_stable():
    ids = providers.ids()
    assert set(ids) == set(providers.PROVIDERS)
    assert len(ids) == len(set(ids))
    # Free providers are listed first: an owner without a credit card should not
    # have to scroll past the paid ones.
    first_paid = ids.index("openai")
    assert ids[0] == "google"
    assert all(ids.index(pid) < first_paid for pid in providers.free_ids()
               if not providers.PROVIDERS[pid].local)


def test_every_provider_is_reachable_via_get():
    for provider in providers.ordered():
        assert providers.get(provider.id) is provider
        assert providers.label_for(provider.id) == provider.label


def test_unknown_provider_falls_back_to_default():
    assert providers.get_or_default("does-not-exist").id == providers.DEFAULT_PROVIDER


def test_key_env_var_mapping():
    assert providers.key_env_var("anthropic") == "ANTHROPIC_API_KEY"
    assert providers.key_env_var("ollama") == ""


def test_set_provider_rejects_unknown(db):
    with pytest.raises(svc.AIServiceError):
        svc.set_provider("nope")


# --- OmniRoute (self-hosted gateway, no AI key in the bot) -------------------
def test_omniroute_is_a_keyless_local_provider():
    provider = providers.get("omniroute")
    assert provider is not None
    assert provider.kind == "openai_compat"
    assert provider.key_required is False
    assert provider.local is True
    assert provider.base_url == "http://localhost:20128/v1"
    assert provider.default_model == "auto"
    assert "omniroute" in providers.ids()


def test_omniroute_ready_without_any_key(db):
    db.set_setting("ai_provider", "omniroute")
    assert svc.is_ready() is True
    assert svc.active_model() == "auto"


def test_omniroute_base_url_env_override(db, monkeypatch):
    db.set_setting("ai_provider", "omniroute")
    assert svc.active_base_url() == "http://localhost:20128/v1"
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://host.docker.internal:20128/v1")
    assert svc.active_base_url() == "http://host.docker.internal:20128/v1"


def test_cloud_provider_base_url_is_not_env_overridable(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://evil.example/v1")
    assert svc.active_base_url("openai") == "https://api.openai.com/v1"


def test_omniroute_chat_sends_no_authorization_header(db, monkeypatch):
    db.set_setting("ai_provider", "omniroute")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)
        return _http_ok(_openai_body("routed reply"))

    monkeypatch.setattr(svc.requests, "post", fake_post)
    out = svc.chat([{"role": "user", "content": "hello"}])
    assert out == "routed reply"
    assert captured["url"] == "http://localhost:20128/v1/chat/completions"
    assert "Authorization" not in captured["headers"]
    assert captured["payload"]["model"] == "auto"


def test_omniroute_optional_key_is_sent_when_configured(db, monkeypatch):
    db.set_setting("ai_provider", "omniroute")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk_omniroute")
    captured = {}
    monkeypatch.setattr(
        svc.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (
            captured.update(headers=headers), _http_ok(_openai_body("ok")))[1],
    )
    assert svc.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert captured["headers"]["Authorization"] == "Bearer sk_omniroute"


def test_omniroute_validate_key_without_a_key(db, monkeypatch):
    db.set_setting("ai_provider", "omniroute")
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _http_ok(_openai_body("ok")))
    ok, _ = svc.validate_key("omniroute", "")
    assert ok is True


def test_omniroute_status_lines_show_endpoint(db):
    db.set_setting("ai_provider", "omniroute")
    lines = " ".join(svc.status_lines())
    assert "http://localhost:20128/v1" in lines


def test_base_url_env_names_only_cover_self_hosted_endpoints():
    assert providers.base_url_env_names("omniroute") == ["OMNIROUTE_BASE_URL"]
    assert providers.base_url_env_names("openai") == []
    assert providers.key_env_var("omniroute") == "OMNIROUTE_API_KEY"

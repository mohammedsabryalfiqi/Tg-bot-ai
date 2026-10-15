"""Provider-agnostic AI layer: chat generation, embeddings, key storage and
connection testing for every backend in ``services/providers.py``.

Design rules
------------
* One HTTP path per transport kind (``openai_compat`` / ``anthropic``), no
  provider-specific SDKs — so adding a provider is a registry entry, and the
  whole layer is mockable in tests.
* Every failure becomes an :class:`AIServiceError` with a ``kind`` and an
  owner-safe ``owner_message``. Customers never see error detail.
* API keys are stored encrypted at rest (Fernet) in the ``api_keys`` table, one
  row per provider. If a key also exists in the environment/.env, the
  environment wins (deterministic, documented).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from urllib.parse import urlparse

import requests

import database
import utils
from services import providers

log = logging.getLogger("smartel.ai")

HTTP_TIMEOUT = (10, 120)          # (connect, read) for generation
VALIDATE_TIMEOUT = (10, 40)       # (connect, read) for key validation
MAX_ATTEMPTS = 3                  # attempts for transient failures (5xx/network)


class AIServiceError(Exception):
    """Internal, sanitized AI error.

    ``owner_message`` is safe to show the OWNER (it is never sent verbatim to a
    customer). ``kind`` is one of: auth, rate_limit, bad_request, timeout,
    connection, server, no_key, no_embeddings, unknown.
    """

    def __init__(self, owner_message: str, *, kind: str, cause: Exception | None = None):
        super().__init__(owner_message)
        self.owner_message = owner_message
        self.kind = kind
        self.cause = cause


# Backwards-compatible alias: older code/tests import this name.
OpenAIServiceError = AIServiceError


# =============================================================================
# API-key protection (at rest)
# =============================================================================
def _fernet():
    key = (os.environ.get("SMARTEL_FERNET_KEY") or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception as e:  # missing lib or bad key
        log.warning("Fernet unavailable (%s); using plain-local key storage.", type(e).__name__)
        return None


def _protect(api_key: str) -> str:
    f = _fernet()
    if f is not None:
        try:
            return "fernet:" + f.encrypt(api_key.encode()).decode()
        except Exception:
            log.warning("Fernet encryption failed; storing plain-local.")
    return "plain:" + api_key


def _unprotect(stored: str | None) -> str | None:
    if not stored:
        return None
    if stored.startswith("fernet:"):
        f = _fernet()
        if f is None:
            return None
        try:
            return f.decrypt(stored[len("fernet:"):].encode()).decode()
        except Exception:
            log.warning("Could not decrypt stored API key (wrong/lost SMARTEL_FERNET_KEY).")
            return None
    if stored.startswith("plain:"):
        return stored[len("plain:"):]
    return stored  # legacy / unprefixed


# =============================================================================
# Small DB guards (status screens must never crash on an uninitialised DB)
# =============================================================================
def _db_setting(key: str, default=""):
    try:
        return database.get_setting(key)
    except Exception:
        return default


def _db_key_row(provider_id: str):
    try:
        return database.get_api_key_row(provider_id)
    except Exception:
        return None


# =============================================================================
# Active provider / model / key resolution
# =============================================================================
def active_provider_id() -> str:
    """Resolve the active provider.

    Precedence: env ``AI_PROVIDER`` (unless the owner deliberately picked a
    different provider in Telegram, i.e. the stored value is not the default) ->
    stored setting -> legacy ``MODEL_BACKEND``/``OPENAI_BASE_URL`` -> default.
    """
    stored = str(_db_setting("ai_provider", "") or "").strip().lower()
    env_provider = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if env_provider and providers.get(env_provider) and stored in ("", providers.DEFAULT_PROVIDER):
        return env_provider
    if stored and providers.get(stored):
        return stored
    if (os.environ.get("MODEL_BACKEND") or "").strip().lower() == "codex":
        return "codex"
    if (os.environ.get("OPENAI_BASE_URL") or "").strip():
        return "custom"
    return providers.DEFAULT_PROVIDER


def active_provider() -> providers.Provider:
    return providers.get_or_default(active_provider_id())


def _model_map() -> dict[str, str]:
    raw = str(_db_setting("ai_model_by_provider", "{}") or "{}")
    try:
        data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def active_model(provider_id: str | None = None) -> str:
    provider = providers.get_or_default(provider_id or active_provider_id())
    mapped = _model_map().get(provider.id)
    if mapped:
        return mapped
    if provider.id == "openai":
        legacy = (os.environ.get("DEFAULT_MODEL") or "").strip()
        legacy = legacy or str(_db_setting("openai_model", "") or "")
        if legacy:
            return legacy
    if provider.id == "codex":
        return (os.environ.get("CODEX_MODEL") or "").strip() or provider.default_model or "codex-default"
    if provider.id == "custom":
        return provider.default_model or "your-model"
    return provider.default_model


def has_explicit_model(provider_id: str | None = None) -> bool:
    """True when a model was chosen for this provider (not just the default)."""
    return bool(_model_map().get((provider_id or active_provider_id()).strip().lower()))


def set_model(model: str, provider_id: str | None = None) -> None:
    provider_id = (provider_id or active_provider_id()).strip().lower()
    mapping = _model_map()
    mapping[provider_id] = (model or "").strip()
    database.set_setting("ai_model_by_provider", json.dumps(mapping))


def active_base_url(provider_id: str | None = None) -> str:
    """Base URL for the active provider.

    ``custom`` reads the owner-stored URL (Telegram / .env). Local self-hosted
    endpoints (OmniRoute, Ollama, LM Studio) use their registry default but let
    an environment variable override it, so the same installation can move the
    gateway to another host/port (or to ``host.docker.internal`` under Docker)
    without code changes.
    """
    provider = providers.get_or_default(provider_id or active_provider_id())
    if provider.id == "custom":
        stored = str(_db_setting("ai_base_url", "") or "").strip()
        return (
            stored
            or (os.environ.get("AI_BASE_URL") or "").strip()
            or (os.environ.get("OPENAI_BASE_URL") or "").strip()  # legacy key
        )
    for name in providers.base_url_env_names(provider.id):
        override = (os.environ.get(name) or "").strip()
        if override:
            return override
    return provider.base_url


def key_env_names(provider_id: str) -> list[str]:
    names = [providers.key_env_var(provider_id)]
    if provider_id == "openai":
        names.append("AI_API_KEY")
    return [n for n in names if n]


def resolve_api_key(provider_id: str | None = None) -> str | None:
    """Active key: environment/.env first, then the encrypted DB copy."""
    provider_id = (provider_id or active_provider_id()).strip().lower()
    for name in key_env_names(provider_id):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    row = _db_key_row(provider_id)
    if row is not None:
        return _unprotect(row["encrypted_key_or_plain_local_key"])
    return None


def key_source(provider_id: str | None = None) -> str:
    """'env' | 'db' | 'none' — used by the /ai screen to explain what is in use."""
    provider_id = (provider_id or active_provider_id()).strip().lower()
    for name in key_env_names(provider_id):
        if (os.environ.get(name) or "").strip():
            return "env"
    if _db_key_row(provider_id) is not None:
        return "db"
    return "none"


def has_api_key(provider_id: str | None = None) -> bool:
    return bool(resolve_api_key(provider_id))


def is_ready() -> bool:
    """Whether the active backend can currently generate replies."""
    provider = active_provider()
    if provider.kind == "codex":
        from services import codex_service
        return codex_service.is_available()
    if provider.id == "custom":
        # A custom endpoint needs a base URL; a key is optional (many proxies
        # and local servers ignore authentication).
        return bool(active_base_url())
    if not provider.key_required:
        return bool(active_base_url())
    return bool(resolve_api_key(provider.id))


def backend_label() -> str:
    provider = active_provider()
    if provider.id == "custom":
        base = active_base_url()
        if base:
            try:
                host = urlparse(base).netloc or base
            except Exception:
                host = base
            return f"custom endpoint ({host})"
        return "custom endpoint (not configured)"
    if provider.kind == "codex":
        return "ChatGPT via Codex CLI"
    return provider.label


def active_model_label() -> str:
    model = active_model()
    provider = active_provider()
    if provider.id == "codex" and model == "codex-default":
        return "Codex default"
    return model or "(not set)"


def masked_active_key(provider_id: str | None = None) -> str:
    key = resolve_api_key(provider_id)
    return utils.mask_key(key) if key else "<not set>"


def using_custom_endpoint() -> bool:
    return active_provider_id() == "custom" or bool((os.environ.get("OPENAI_BASE_URL") or "").strip())


# Backwards-compatible helpers kept for older call sites / third-party scripts.
def _resolve_backend() -> str:
    provider = active_provider()
    return "codex" if provider.kind == "codex" else "openai"


def _resolve_api_key() -> str | None:
    return resolve_api_key()


def _resolve_base_url() -> str | None:
    return active_base_url() or None


# =============================================================================
# Key storage
# =============================================================================
def store_api_key(api_key: str, provider_id: str | None = None, *, persist_env: bool = False) -> None:
    """Persist a key: process env + encrypted DB row for that provider."""
    provider_id = (provider_id or active_provider_id()).strip().lower()
    api_key = (api_key or "").strip()
    env_names = key_env_names(provider_id)
    if env_names and persist_env:
        os.environ[env_names[0]] = api_key
    database.upsert_api_key(provider_id, utils.mask_key(api_key), _protect(api_key))
    log.info("API key stored for provider %s (%s)", provider_id, utils.mask_key(api_key))


def disconnect_api_key(provider_id: str | None = None) -> None:
    provider_id = (provider_id or active_provider_id()).strip().lower()
    for name in key_env_names(provider_id):
        os.environ.pop(name, None)
    database.delete_api_key(provider_id)
    log.info("API key removed for provider %s", provider_id)


def set_provider(provider_id: str) -> None:
    provider = providers.get(provider_id)
    if provider is None:
        raise AIServiceError(f"Unknown provider: {provider_id}", kind="bad_request")
    database.set_setting("ai_provider", provider.id)
    log.info("AI provider switched to %s", provider.id)


def set_base_url(url: str) -> None:
    database.set_setting("ai_base_url", (url or "").strip())


# =============================================================================
# HTTP plumbing
# =============================================================================
def _error_from_response(response: requests.Response) -> AIServiceError:
    status = response.status_code
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("type") or "")
        elif error:
            detail = str(error)
        if not detail:
            detail = str(body.get("message") or body.get("detail") or "")
    detail = utils.plain_text(detail)[:300]
    if status in (401, 403):
        return AIServiceError(
            "The provider rejected the API key. Re-send it with /ai → “Add / update key”."
            + (f" ({detail})" if detail else ""),
            kind="auth",
        )
    if status == 404:
        return AIServiceError(
            "The provider returned 404 (wrong base URL or model name)."
            + (f" {detail}" if detail else ""),
            kind="bad_request",
        )
    if status == 429:
        return AIServiceError(
            "The provider rate-limited the request (quota or too many requests)."
            + (f" {detail}" if detail else ""),
            kind="rate_limit",
        )
    if status >= 500:
        return AIServiceError(
            f"The provider is having problems (HTTP {status}). Retry in a moment."
            + (f" {detail}" if detail else ""),
            kind="server",
        )
    return AIServiceError(
        f"The provider rejected the request (HTTP {status})."
        + (f" {detail}" if detail else ""),
        kind="bad_request",
    )


def _post_json(url: str, headers: dict, payload: dict, *, timeout, what: str) -> dict:
    """POST JSON with bounded retries for transient failures."""
    last_error: AIServiceError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout as e:
            last_error = AIServiceError(f"{what} timed out. Try again.", kind="timeout", cause=e)
        except requests.RequestException as e:
            last_error = AIServiceError(
                f"Could not reach the provider ({type(e).__name__}). Check the network.",
                kind="connection", cause=e,
            )
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as e:
                    raise AIServiceError(
                        f"{what}: the provider returned a non-JSON response.", kind="unknown", cause=e
                    )
            error = _error_from_response(response)
            if error.kind not in ("server", "rate_limit", "timeout"):
                raise error
            last_error = error
            retry_after = 0.0
            try:
                retry_after = float(response.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                retry_after = 0.0
            if attempt < MAX_ATTEMPTS:
                time.sleep(min(retry_after or (1.5 * attempt), 20.0))
                continue
        if attempt < MAX_ATTEMPTS:
            time.sleep(1.5 * attempt)
    raise last_error or AIServiceError(f"{what} failed.", kind="unknown")


# =============================================================================
# Chat
# =============================================================================
def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Anthropic wants the system prompt as a top-level field, not a message."""
    system_parts = [str(m.get("content") or "") for m in messages if m.get("role") == "system"]
    convo = [
        {"role": "assistant" if m.get("role") == "assistant" else "user",
         "content": str(m.get("content") or "")}
        for m in messages
        if m.get("role") != "system"
    ]
    return "\n\n".join(p for p in system_parts if p), convo


def _max_tokens_param(model: str) -> str:
    """Newer reasoning models require ``max_completion_tokens``."""
    lowered = (model or "").lower()
    if lowered.startswith(("o1", "o3", "o4", "gpt-5", "gpt-4.5")):
        return "max_completion_tokens"
    return "max_tokens"


def _extract_openai_text(body: dict) -> str:
    try:
        choices = body.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, list):  # some gateways return content parts
            return "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            ).strip()
        if content:
            return str(content).strip()
        return str(message.get("reasoning_content") or "").strip()
    except (IndexError, AttributeError, TypeError):
        return ""


def _extract_anthropic_text(body: dict) -> str:
    parts = body.get("content")
    if isinstance(parts, list):
        return "".join(
            str(p.get("text", "")) for p in parts
            if isinstance(p, dict) and p.get("type") in (None, "text")
        ).strip()
    return ""


def _openai_compat_chat(provider, model: str, messages: list[dict], temperature, max_tokens) -> str:
    base = active_base_url(provider.id).rstrip("/")
    if not base:
        raise AIServiceError("No base URL configured for this endpoint.", kind="no_key")
    key = resolve_api_key(provider.id)
    if not key and provider.key_required:
        raise AIServiceError(
            "No API key configured for this provider. Add one with /ai.", kind="no_key"
        )
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if provider.id == "openrouter":
        headers.setdefault("HTTP-Referer", "https://github.com/Ai-bot/SmarTel")
        headers.setdefault("X-Title", "SmarTel Telegram Business Bot")

    payload: dict = {"model": model, "messages": messages}
    if temperature is not None:
        payload["temperature"] = temperature
    token_param = _max_tokens_param(model)
    if max_tokens:
        payload[token_param] = max_tokens

    url = f"{base}/chat/completions"
    what = f"{provider.label} chat"
    try:
        body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what)
    except AIServiceError as error:
        if error.kind == "bad_request":
            # Some models reject `temperature`, `max_tokens` (or a param name
            # differs). Retry with the most compatible payload before giving up.
            if "max_tokens" in str(error.owner_message):
                payload.pop(token_param, None)
                payload["max_completion_tokens"] = max_tokens or 800
                body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what)
            elif "temperature" in str(error.owner_message):
                payload.pop("temperature", None)
                body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what)
            else:
                raise
        else:
            raise
    text = _extract_openai_text(body)
    if not text:
        raise AIServiceError("The model returned an empty reply.", kind="unknown")
    return text


def _anthropic_chat(provider, model: str, messages: list[dict], temperature, max_tokens) -> str:
    base = active_base_url(provider.id).rstrip("/")
    key = resolve_api_key(provider.id)
    if not key:
        raise AIServiceError(
            "No Anthropic API key configured. Add one with /ai.", kind="no_key"
        )
    system_text, convo = _split_system(messages)
    payload = {
        "model": model,
        "max_tokens": max_tokens or 1024,
        "messages": convo or [{"role": "user", "content": "Hello"}],
    }
    if system_text:
        payload["system"] = system_text
    if temperature is not None:
        payload["temperature"] = temperature
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    body = _post_json(f"{base}/messages", headers, payload,
                      timeout=HTTP_TIMEOUT, what=f"{provider.label} chat")
    text = _extract_anthropic_text(body)
    if not text:
        raise AIServiceError("The model returned an empty reply.", kind="unknown")
    return text


def chat(messages: list[dict], *, model: str | None = None,
         temperature: float | None = None, max_tokens: int | None = None) -> str:
    """Generate a reply with the active provider."""
    provider = active_provider()
    model = model or active_model(provider.id)
    if temperature is None:
        temperature = float(_db_setting("temperature", 0.4) or 0.4)
    if max_tokens is None:
        max_tokens = int(_db_setting("max_tokens", 800) or 800)

    if provider.kind == "codex":
        from services import codex_service
        return codex_service.chat(messages, model=model)
    if provider.kind == "anthropic":
        return _anthropic_chat(provider, model, messages, temperature, max_tokens)
    return _openai_compat_chat(provider, model, messages, temperature, max_tokens)


# =============================================================================
# Embeddings (knowledge base)
# =============================================================================
def _embed_provider() -> providers.Provider | None:
    """Provider used for embeddings: the active one if it can embed, else OpenAI
    (documented behaviour: chat can be on any provider while KB retrieval uses
    OpenAI embeddings when an OpenAI key exists)."""
    active = active_provider()
    if active.embed_model:
        return active
    openai = providers.PROVIDERS["openai"]
    if key_source("openai") != "none" or (os.environ.get("OPENAI_API_KEY") or "").strip():
        return openai
    return None


def supports_embeddings() -> bool:
    return _embed_provider() is not None


def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Embed texts. Raises AIServiceError(kind='no_embeddings') when unavailable
    (callers fall back to keyword search)."""
    provider = _embed_provider()
    if provider is None:
        raise AIServiceError(
            "Embeddings are not available for the active provider "
            "(knowledge base will use keyword search).",
            kind="no_embeddings",
        )
    base = active_base_url(provider.id).rstrip("/")
    if not base:
        raise AIServiceError("No base URL for embeddings.", kind="no_embeddings")
    key = resolve_api_key(provider.id)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    embed_model = model or provider.embed_model
    payload = {"model": embed_model, "input": [str(t)[:8000] for t in texts]}
    body = _post_json(f"{base}/embeddings", headers, payload,
                      timeout=HTTP_TIMEOUT, what=f"{provider.label} embeddings")
    data = body.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise AIServiceError("The embeddings endpoint returned an unexpected payload.",
                             kind="unknown")
    return [list(item.get("embedding") or []) for item in data]


# =============================================================================
# Validation / testing (used by the in-Telegram setup flow)
# =============================================================================
def validate_key(provider_id: str, key: str, *, model: str | None = None) -> tuple[bool, str]:
    """Live-check a key against the provider (and that the model name works).

    Returns ``(ok, message)`` where the message is owner-facing.
    """
    provider = providers.get(provider_id)
    if provider is None:
        return False, "Unknown provider."
    if not (key or "").strip() and provider.key_required:
        return False, "No key provided."
    try:
        text = _probe(provider, key.strip(), model or active_model(provider.id))
    except AIServiceError as e:
        return False, e.owner_message
    return True, f"Connection OK — the model replied: “{utils.plain_text(text)[:60]}”"


def _probe(provider, key: str, model: str) -> str:
    """One tiny generation to prove key + endpoint + model all work."""
    messages = [{"role": "user", "content": "Reply with the single word: ok"}]
    if provider.kind == "codex":
        from services import codex_service
        if not codex_service.is_available():
            raise AIServiceError("The Codex CLI is not installed on this machine.", kind="no_key")
        return codex_service.chat(messages, model=model)
    if provider.kind == "anthropic":
        payload = {"model": model, "max_tokens": 16, "messages": messages}
        headers = {"Content-Type": "application/json", "x-api-key": key,
                   "anthropic-version": "2023-06-01"}
        base = (provider.base_url or "https://api.anthropic.com/v1").rstrip("/")
        body = _post_json(f"{base}/messages", headers, payload,
                          timeout=VALIDATE_TIMEOUT, what="Anthropic test")
        return _extract_anthropic_text(body) or "ok"
    base = (active_base_url(provider.id) or provider.base_url or "").rstrip("/")
    if not base:
        raise AIServiceError("No base URL set for this endpoint.", kind="bad_request")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": model, "messages": messages, "max_tokens": 16}
    body = _post_json(f"{base}/chat/completions", headers, payload,
                      timeout=VALIDATE_TIMEOUT, what=f"{provider.label} test")
    return _extract_openai_text(body) or "ok"


def test_connection() -> tuple[bool, str]:
    """End-to-end test of the *active* configuration (token + model + latency)."""
    provider = active_provider()
    started = time.monotonic()
    ok, message = validate_key(provider.id, resolve_api_key(provider.id) or "")
    elapsed = time.monotonic() - started
    if not ok:
        return False, message
    return True, f"{message} ({elapsed:.1f}s)"


def status_lines() -> list[str]:
    """Human-readable status block (owner-facing, plain text)."""
    provider = active_provider()
    lines = [f"Provider: {provider.label}"]
    lines.append(f"Model: {active_model_label()}")
    if provider.kind == "codex":
        from services import codex_service
        lines.append(f"Codex CLI: {'found' if codex_service.is_available() else 'NOT found'}"
                     f" · login: {'yes' if codex_service.is_logged_in() else 'no/unknown'}")
    elif provider.key_required or provider.id == "custom":
        source = key_source(provider.id)
        origin = {"env": " (from .env)", "db": " (saved in Telegram)", "none": ""}[source]
        lines.append(f"API key: {masked_active_key(provider.id)}{origin}")
        if provider.id == "custom":
            lines.append(f"Base URL: {active_base_url() or '(not set)'}")
    else:
        lines.append(f"Endpoint: {active_base_url() or '(not set)'}")
        if key_source(provider.id) != "none":
            lines.append(f"API key: {masked_active_key(provider.id)} (optional here)")
    lines.append(f"Embeddings: {'yes' if supports_embeddings() else 'no (keyword search only)'}")
    return lines


# Backwards-compatible no-op: the SDK client cache no longer exists.
def invalidate_client() -> None:  # pragma: no cover - compat shim
    return None


_client_lock = threading.Lock()  # kept so older imports do not break

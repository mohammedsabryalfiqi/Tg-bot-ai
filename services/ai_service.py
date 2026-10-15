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
import re
import threading
import time
from dataclasses import dataclass
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
    customer). ``kind`` is one of: no_credit, auth, model, rate_limit, region,
    bad_request, timeout, connection, server, no_key, no_embeddings, unknown.
    ``hints`` are short owner-facing bullets explaining how to fix it (shown by
    the /ai screens and by the failure notification).
    """

    def __init__(self, owner_message: str, *, kind: str, cause: Exception | None = None,
                 hints: tuple[str, ...] = ()):
        super().__init__(owner_message)
        self.owner_message = owner_message
        self.kind = kind
        self.cause = cause
        self.hints = tuple(hints)


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
    """Base URL for the active provider (custom/local endpoints are owner-set)."""
    provider = providers.get_or_default(provider_id or active_provider_id())
    if provider.id == "custom":
        stored = str(_db_setting("ai_base_url", "") or "").strip()
        return (
            stored
            or (os.environ.get("AI_BASE_URL") or "").strip()
            or (os.environ.get("OPENAI_BASE_URL") or "").strip()  # legacy key
        )
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
    api_key = _clean_key(api_key)
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
# Markers used to tell "this key is fine but the account has no money/quota left"
# apart from "this key is wrong". Getting this right matters: an owner who just
# created a free key must not be told their key is broken.
BILLING_MARKERS = (
    "insufficient_quota", "insufficient quota", "insufficient_balance",
    "insufficient balance", "insufficient_credit", "insufficient credit",
    "no balance", "zero balance", "balance is 0", "balance: 0", "out of credit",
    "out of credits", "no credit", "no credits", "not enough credit",
    "credit exhausted", "credits exhausted", "billing", "payment required",
    "payment_required", "unpaid", "arrears", "recharge", "top up", "top-up",
    "topup", "purchase credit", "add credit", "no active subscription",
    "requires payment", "plan and billing", "trial ended", "trial expired",
    "subscription expired", "add funds", "not enough funds",
)

# Time-based quotas (free tiers) reset on their own — that is NOT "no credit",
# and telling an owner it is would send them off to buy something they do not need.
RATE_MARKERS = (
    "rate limit", "rate_limit", "ratelimit", "too many requests",
    "requests per minute", "requests per day", "per minute", "per day",
    "per second", " rpm", "rpd", "tpm", "resource_exhausted", "resource exhausted",
    "resource has been exhausted", "quota exceeded", "exceeded your current quota",
    "exceeded your quota", "exceeded your current requests", "free tier limit",
    "free quota", "daily quota", "quota will reset", "will reset", "retry after",
    "please retry", "try again", "reduce your requests", "concurrency",
)

# Kept as an alias: older code/tests may reference the previous name.
NO_CREDIT_MARKERS = BILLING_MARKERS

MODEL_MARKERS = (
    "model_not_found", "model not found", "does not exist", "no such model",
    "unsupported model", "invalid model", "unknown model", "model is not",
    "not a valid model", "model does not", "access to model", "permission to use",
    "model permission", "gated model", "not enabled for model",
)

REGION_MARKERS = (
    "country", "region", "territory", "not available in", "sanctioned",
    "geographic", "ip address", "unsupported jurisdiction",
)

VERIFICATION_MARKERS = (
    "verify your", "verification", "phone number", "email address is not",
    "activate your account", "account is not active",
)

# Extra per-provider hint, appended when a key is rejected — the mistakes owners
# actually make on each platform.
KEY_HINTS: dict[str, str] = {
    "openai": "OpenAI needs credit on the API account — a ChatGPT Plus subscription "
              "is not API credit (platform.openai.com → Billing).",
    "anthropic": "Anthropic needs credit on console.anthropic.com — a Claude "
                 "subscription is not API credit.",
    "google": "Use a key from aistudio.google.com/app/apikey (Gemini API), not a "
              "Google Cloud OAuth token.",
    "groq": "Groq keys come from console.groq.com/keys — a free account, no card.",
    "cerebras": "Cerebras keys come from cloud.cerebras.ai → API Keys.",
    "openrouter": "OpenRouter: models ending in ':free' need no credit; any other "
                  "model needs a paid balance.",
    "mistral": "Mistral's free plan needs phone verification before the key works.",
    "nvidia": "NVIDIA: copy the model name exactly as build.nvidia.com shows it "
              "(e.g. meta/llama-3.1-8b-instruct).",
    "huggingface": "Hugging Face: use a token with 'Read' scope, and open the model "
                   "page once to accept its licence if it is gated.",
    "deepseek": "DeepSeek keys only work after the balance is topped up "
                "(platform.deepseek.com → Top up).",
    "together": "Together needs a minimum top-up before the key works.",
    "pollinations": "Pollinations needs no key at all — a 402/429 here means the "
                    "free per-IP slot is busy: wait ~30 seconds and retry.",
}

# Free providers suggested when the current one cannot be used.
FREE_HINT = "Free providers that need no card: Google Gemini, Groq, Cerebras, " \
            "Mistral — open /ai → 🆓 Free providers (or send /freeai)."


def _parse_error_body(response: requests.Response) -> tuple[str, str, str]:
    """Extract ``(detail, code, error_type)`` from a provider error payload."""
    detail = code = err_type = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message") or "")
            code = str(error.get("code") or "")
            err_type = str(error.get("type") or "")
        elif error:
            detail = str(error)
        if not detail:
            detail = str(body.get("message") or body.get("detail") or body.get("error") or "")
        if not code:
            code = str(body.get("code") or "")
    if not detail:
        try:
            detail = (response.text or "")[:200]
        except Exception:
            detail = ""
    return utils.plain_text(detail)[:300], code.lower(), err_type.lower()


def _blob(detail: str, code: str, err_type: str) -> str:
    return f"{code} {err_type} {detail}".lower()


def _has(blob: str, markers) -> bool:
    return any(marker in blob for marker in markers)


def _classify(status: int, detail: str, code: str, err_type: str,
              provider=None) -> tuple[str, str]:
    """Map an HTTP failure to ``(kind, owner_message)``.

    The message tells the owner *what* to do next; the distinction that matters
    most is between a wrong key (auth), a key with no money behind it
    (no_credit) and a model name the account cannot run (model).
    """
    label = provider.label if provider is not None else "The provider"
    blob = _blob(detail, code, err_type)
    tail = f" ({detail})" if detail else ""

    # --- model name / model access -------------------------------------------
    param_issue = "max_tokens" in blob or "temperature" in blob or "max_completion" in blob
    if status in (400, 404) and not param_issue and _has(blob, MODEL_MARKERS):
        return "model", (
            f"{label} rejected the model name{tail} Your key may not have access to "
            "it, or the name is spelled differently on this provider."
        )

    # --- no credit, or a free-tier quota that simply resets -------------------
    if status == 402 and provider is not None and provider.id == "pollinations":
        # Pollinations answers 402 when the free per-IP slot is busy, not when
        # money is missing — it never asks for payment.
        return "rate_limit", (
            f"{label} is throttling this address{tail} The free endpoint allows "
            "roughly one request per 30 seconds: wait a moment and test again."
        )
    if status == 402 or (status in (400, 401, 403, 429)
                         and (_has(blob, BILLING_MARKERS) or _has(blob, RATE_MARKERS))):
        if status == 402 or _has(blob, BILLING_MARKERS):
            return "no_credit", (
                f"{label}: the key was understood, but the account has no credit left "
                f"or its paid quota is used up{tail}"
            )
        return "rate_limit", (
            f"{label} hit a rate/quota limit{tail} Free tiers cap requests per "
            "minute or per day — this resets on its own, nothing is broken."
        )

    # --- region / availability -----------------------------------------------
    if status in (401, 403) and _has(blob, REGION_MARKERS):
        return "region", (
            f"{label} refused the request because of your country/region{tail} "
            "Another provider will work."
        )

    # --- bad key -------------------------------------------------------------
    if status in (401, 403):
        extra = " Finish the account verification first." \
            if _has(blob, VERIFICATION_MARKERS) else ""
        return "auth", (
            f"{label} rejected this API key (HTTP {status}){tail}{extra}"
        )

    # --- endpoint / URL ------------------------------------------------------
    if status == 404:
        return "bad_request", (
            f"{label} returned 404 — the base URL or the endpoint path is wrong "
            f"(most providers expect the base URL to end in /v1){tail}"
        )

    # --- rate limit ----------------------------------------------------------
    if status == 429:
        return "rate_limit", (
            f"{label} is rate limiting the bot right now{tail} Free tiers cap "
            "requests per minute/day; this resets on its own."
        )

    if status >= 500:
        return "server", (
            f"{label} is having problems (HTTP {status}). Retry in a moment.{tail}"
        )

    return "bad_request", f"{label} rejected the request (HTTP {status}).{tail}"


def hints_for(kind: str, provider=None) -> tuple[str, ...]:
    """Short, actionable bullets for an error kind (owner-facing)."""
    hints: list[str] = []
    provider_id = provider.id if provider is not None else ""
    if kind == "no_credit":
        hints += [
            "This is a billing/quota problem, not a broken key — re-sending the same "
            "key will not help.",
            "Either add credit at the provider's billing page, or switch to a "
            "provider with a real free tier.",
            FREE_HINT,
        ]
    elif kind == "auth":
        hints += [
            "Check the key was copied from THIS provider — a Groq/OpenRouter/Gemini "
            "key never works on another one.",
            "Paste it again with no spaces or line breaks, and make sure it was not "
            "revoked or expired.",
        ]
        if provider is not None and provider.key_url:
            hints.append(f"Create a fresh key: {provider.key_url}")
        hints.append(FREE_HINT)
    elif kind == "model":
        hints += [
            "Open /ai → 🧠 Change model → 🔄 Load models from the provider to see the "
            "exact names this key can run.",
            "Free tiers often allow only some models — pick a smaller/older one.",
        ]
    elif kind == "rate_limit":
        hints += [
            "Wait a minute and run /aitest again; free quotas reset per minute or per "
            "day.",
            "For a bigger free daily quota use Google Gemini, Groq or Cerebras.",
        ]
    elif kind == "region":
        hints = [FREE_HINT]
    elif kind == "bad_request":
        hints = [
            "Check the base URL ends in /v1 and that the model name matches the "
            "provider's docs.",
        ]
    elif kind == "connection":
        hints = ["The server could not be reached — check this machine's internet "
                 "access, DNS and any firewall/proxy."]
    elif kind == "timeout":
        hints = ["The provider took too long. Retry, or pick a faster provider "
                 "(Groq and Cerebras answer in well under a second)."]
    elif kind == "no_key":
        hints = ["Open /ai → 🔑 Add / update API key.", FREE_HINT]

    specific = KEY_HINTS.get(provider_id)
    if specific and specific not in hints:
        hints.insert(0 if kind in ("auth", "no_credit", "model") else len(hints), specific)
    return tuple(dict.fromkeys(hints))


def _error_from_response(response: requests.Response, provider=None) -> AIServiceError:
    detail, code, err_type = _parse_error_body(response)
    kind, message = _classify(response.status_code, detail, code, err_type, provider)
    return AIServiceError(message, kind=kind, hints=hints_for(kind, provider))


def _post_json(url: str, headers: dict, payload: dict, *, timeout, what: str,
               provider=None) -> dict:
    """POST JSON with bounded retries for transient failures."""
    last_error: AIServiceError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout as e:
            last_error = AIServiceError(f"{what} timed out. Try again.", kind="timeout", cause=e,
                                        hints=hints_for("timeout", provider))
        except requests.RequestException as e:
            last_error = AIServiceError(
                f"Could not reach the provider ({type(e).__name__}). Check the network.",
                kind="connection", cause=e, hints=hints_for("connection", provider),
            )
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as e:
                    raise AIServiceError(
                        f"{what}: the provider returned a non-JSON response.", kind="unknown", cause=e
                    )
            error = _error_from_response(response, provider)
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
        body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what,
                          provider=provider)
    except AIServiceError as error:
        if error.kind in ("bad_request", "model"):
            # Some models reject `temperature`, `max_tokens` (or a param name
            # differs). Retry with the most compatible payload before giving up.
            if "max_tokens" in str(error.owner_message):
                payload.pop(token_param, None)
                payload["max_completion_tokens"] = max_tokens or 800
                body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what,
                                  provider=provider)
            elif "temperature" in str(error.owner_message):
                payload.pop("temperature", None)
                body = _post_json(url, headers, payload, timeout=HTTP_TIMEOUT, what=what,
                                  provider=provider)
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
                      timeout=HTTP_TIMEOUT, what=f"{provider.label} chat",
                      provider=provider)
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
                      timeout=HTTP_TIMEOUT, what=f"{provider.label} embeddings",
                      provider=provider)
    data = body.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise AIServiceError("The embeddings endpoint returned an unexpected payload.",
                             kind="unknown")
    return [list(item.get("embedding") or []) for item in data]


# =============================================================================
# Validation / testing (used by the in-Telegram setup flow)
# =============================================================================
# A Telegram bot token ("123456789:AA...") pasted into the AI-key field is one
# of the most common setup mistakes, and it produces a confusing 401 from the AI
# provider. Recognise it and say so in plain words.
BOT_TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


def _clean_key(key: str) -> str:
    """Normalise a pasted key: no quotes, no "Bearer ", no stray whitespace."""
    value = (key or "").strip()
    if value.lower().startswith("bearer "):
        value = value[len("bearer "):].strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"', "`"):
        value = value[1:-1].strip()
    # Keys pasted from a chat often carry hard line breaks.
    return "".join(value.split())


def key_shape_problem(provider, key: str) -> str | None:
    """Return an owner-facing explanation when the *shape* of the key is wrong.

    Catches two mistakes before any HTTP request is made: pasting the Telegram
    bot token into the AI-key field, and pasting another provider's key.
    """
    value = (key or "").strip()
    if not value:
        return None
    if BOT_TOKEN_RE.match(value):
        return (
            "That is your Telegram bot token (from @BotFather), not an AI API key. "
            f"The bot token is already in use — what {provider.label} needs is its own "
            "API key, from that provider's own website."
        )
    matches = providers.key_prefix_matches(value)
    if matches and provider.id not in [m.id for m in matches]:
        names = " or ".join(m.label for m in matches[:2])
        return (
            f"This looks like a key for {names}, but you are adding it to "
            f"{provider.label}. Each provider only accepts its own keys."
        )
    return None


@dataclass(frozen=True)
class KeyCheck:
    """Result of a live key/model check, rich enough to drive the Telegram UI.

    ``hints`` are owner-facing "what to do next" bullets and ``suggestions`` are
    free providers worth switching to when this one cannot be used (no credit,
    rejected key, region block, …).
    """

    ok: bool
    message: str
    kind: str = "ok"
    hints: tuple[str, ...] = ()
    suggestions: tuple = ()          # tuple[providers.Provider, ...]
    elapsed: float | None = None
    model: str = ""


# Error kinds where switching provider is the actual fix (not just "retry").
SWITCHABLE_KINDS = frozenset({"auth", "no_credit", "region", "model", "rate_limit"})


def check_key(provider_id: str, key: str, *, model: str | None = None) -> KeyCheck:
    """Live-check a key against the provider (and that the model name works)."""
    provider = providers.get(provider_id)
    if provider is None:
        return KeyCheck(False, "Unknown provider.", kind="bad_request")
    if not (key or "").strip() and provider.key_required:
        return KeyCheck(
            False,
            f"No API key for {provider.label} yet.",
            kind="no_key",
            hints=(f"Send the key: /ai → 🔑 Add / update API key."
                   + (f" Get one at {provider.key_url}." if provider.key_url else ""),
                   FREE_HINT),
        )
    cleaned = _clean_key(key)
    shape_problem = key_shape_problem(provider, cleaned)
    if shape_problem:
        hints = [
            f"You are adding a key for {provider.label}; get it from "
            + (provider.key_url + "." if provider.key_url else "that provider's console."),
        ]
        if providers.key_prefix_matches(cleaned):
            owner = providers.looks_like_key_of(cleaned)
            if owner is not None and owner.key_url:
                hints.append(f"That key belongs to {owner.label}: {owner.key_url}")
        hints.append(FREE_HINT)
        return KeyCheck(False, shape_problem, kind="auth",
                        hints=tuple(hints),
                        suggestions=tuple(providers.switch_suggestions(provider.id)))
    use_model = (model or active_model(provider.id)).strip()
    started = time.monotonic()
    try:
        text = _probe(provider, cleaned, use_model)
    except AIServiceError as e:
        suggestions = tuple(providers.switch_suggestions(provider.id)) \
            if e.kind in SWITCHABLE_KINDS else ()
        return KeyCheck(False, e.owner_message, kind=e.kind, hints=e.hints,
                        suggestions=suggestions, elapsed=time.monotonic() - started,
                        model=use_model)
    return KeyCheck(
        True,
        f"Connection OK — {provider.label} answered with “{utils.plain_text(text)[:60]}” "
        f"using {use_model} ({time.monotonic() - started:.1f}s).",
        model=use_model, elapsed=time.monotonic() - started,
    )


def validate_key(provider_id: str, key: str, *, model: str | None = None) -> tuple[bool, str]:
    """Backwards-compatible ``(ok, message)`` wrapper around :func:`check_key`."""
    result = check_key(provider_id, key, model=model)
    return result.ok, result.message


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
                          timeout=VALIDATE_TIMEOUT, what="Anthropic test",
                          provider=provider)
        return _extract_anthropic_text(body) or "ok"
    base = (active_base_url(provider.id) or provider.base_url or "").rstrip("/")
    if not base:
        raise AIServiceError("No base URL set for this endpoint.", kind="bad_request")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": model, "messages": messages, "max_tokens": 16}
    body = _post_json(f"{base}/chat/completions", headers, payload,
                      timeout=VALIDATE_TIMEOUT, what=f"{provider.label} test",
                      provider=provider)
    return _extract_openai_text(body) or "ok"


def check_connection(provider_id: str | None = None,
                     key: str | None = None) -> KeyCheck:
    """End-to-end test of a stored configuration (key + model + latency)."""
    provider = providers.get_or_default(provider_id or active_provider_id())
    return check_key(provider.id,
                     key if key is not None else (resolve_api_key(provider.id) or ""))


def test_connection() -> tuple[bool, str]:
    """Backwards-compatible ``(ok, message)`` wrapper around :func:`check_connection`."""
    result = check_connection()
    return result.ok, result.message


# =============================================================================
# Live model catalogue (kills "the model name was wrong" failures)
# =============================================================================
MODEL_LIST_LIMIT = 30
_NON_CHAT_MARKERS = ("embedding", "embed", "tts", "whisper", "speech", "dall-e",
                     "image-gen", "moderation", "rerank", "reranker")
_SMALL_FAST_MARKERS = ("flash", "mini", "small", "lite", "haiku", "instant",
                       "8b", "7b", "3b", "latest", "instruct")


def _extract_model_ids(body) -> list[str]:
    """Model ids from any /models payload shape we have seen in the wild."""
    found: list[str] = []

    def _take(item) -> None:
        if isinstance(item, str):
            if item:
                found.append(item)
            return
        if isinstance(item, dict):
            for field in ("id", "name", "model", "slug", "display_name"):
                value = item.get(field)
                if isinstance(value, str) and value:
                    found.append(value)
                    return

    if isinstance(body, list):
        for item in body:
            _take(item)
    elif isinstance(body, dict):
        for key in ("data", "models", "results", "items"):
            value = body.get(key)
            if isinstance(value, list):
                for item in value:
                    _take(item)
            elif isinstance(value, dict):      # {"models": {"openai": {...}}}
                for name in value:
                    _take(str(name))
    return list(dict.fromkeys(found))


def _rank_models(raw: list[str], provider, limit: int) -> list[str]:
    """Most useful first: the current model, then the registry picks, then the rest."""
    current = active_model(provider.id)
    suggested = list(provider.models)

    def score(name: str) -> tuple:
        lowered = name.lower()
        value = 0
        if name == current:
            value -= 1000
        if name in suggested:
            value -= 500 + suggested.index(name)
        if provider.id == "openrouter" and lowered.endswith(":free"):
            value -= 200
        if any(marker in lowered for marker in _NON_CHAT_MARKERS):
            value += 400
        if any(marker in lowered for marker in _SMALL_FAST_MARKERS):
            value -= 20
        return (value, len(name), name)

    return sorted(set(raw), key=score)[:limit]


def list_models(provider_id: str | None = None, *, key: str | None = None,
                limit: int = MODEL_LIST_LIMIT) -> list[str]:
    """Ask the provider which models this key can actually run.

    Raises :class:`AIServiceError` (with owner-safe hints) when the catalogue
    cannot be fetched — the caller falls back to the registry suggestions.
    """
    provider = providers.get_or_default(provider_id or active_provider_id())
    if provider.kind == "codex":
        return []
    base = (active_base_url(provider.id) or provider.base_url or "").rstrip("/")
    if not base:
        raise AIServiceError("No base URL set for this endpoint.", kind="bad_request",
                             hints=hints_for("bad_request", provider))
    token = (key if key is not None else resolve_api_key(provider.id)) or ""
    headers = {"Content-Type": "application/json"}
    if provider.kind == "anthropic":
        headers["x-api-key"] = token
        headers["anthropic-version"] = "2023-06-01"
    elif token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{base}/models"
    try:
        response = requests.get(url, headers=headers, timeout=VALIDATE_TIMEOUT)
    except requests.Timeout as e:
        raise AIServiceError(f"{provider.label}: fetching the model list timed out.",
                             kind="timeout", cause=e,
                             hints=hints_for("timeout", provider)) from e
    except requests.RequestException as e:
        raise AIServiceError(
            f"Could not reach {provider.label} ({type(e).__name__}).",
            kind="connection", cause=e, hints=hints_for("connection", provider)) from e
    if response.status_code >= 400:
        raise _error_from_response(response, provider)
    try:
        body = response.json()
    except ValueError as e:
        raise AIServiceError(f"{provider.label} returned a non-JSON model list.",
                             kind="unknown", cause=e) from e
    return _rank_models(_extract_model_ids(body), provider, limit)


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
    lines.append(f"Embeddings: {'yes' if supports_embeddings() else 'no (keyword search only)'}")
    lines.append(f"Cost: {cost_label(provider)}")
    return lines


def cost_label(provider=None) -> str:
    """One-line cost summary: free tier, free local model, or paid credit."""
    provider = provider or active_provider()
    if provider.local:
        return "free — runs on your own machine 💻"
    if not provider.key_required:
        return "free — no API key needed 🆓"
    if provider.free_tier:
        return "free tier available 🆓" + (
            " (paid credit needed beyond it)" if providers.needs_credit(provider.id) else "")
    if providers.needs_credit(provider.id):
        return "paid — the account needs credit 💳"
    return "depends on your endpoint"


# Backwards-compatible no-op: the SDK client cache no longer exists.
def invalidate_client() -> None:  # pragma: no cover - compat shim
    return None


_client_lock = threading.Lock()  # kept so older imports do not break

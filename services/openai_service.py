"""Compatibility shim.

The AI layer used to live here and was OpenAI-only. It now lives in
``services/ai_service.py`` (provider-agnostic) and ``services/providers.py``
(the provider registry). This module keeps the old import surface working for
third-party scripts and older tests:

    from services.openai_service import OpenAIServiceError, chat, embed, is_ready

New code should import ``services.ai_service`` directly.
"""

from __future__ import annotations

from services import providers as _providers
from services.ai_service import (  # noqa: F401  (re-exported on purpose)
    AIServiceError,
    OpenAIServiceError,
    _resolve_api_key,
    _resolve_backend,
    _resolve_base_url,
    active_model_label,
    backend_label,
    chat,
    disconnect_api_key,
    embed,
    has_api_key,
    is_ready,
    masked_active_key,
    resolve_api_key,
    store_api_key,
    supports_embeddings,
    using_custom_endpoint,
    validate_key,
)

PROVIDER = "openai"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
GENERIC_CUSTOMER_APOLOGY = (
    "Sorry, I'm having trouble responding right now. Someone will get back to you shortly."
)


def get_client():  # pragma: no cover - compat shim, no SDK client anymore
    """Deprecated: the OpenAI SDK client is no longer used (plain HTTP now)."""
    raise OpenAIServiceError(
        "get_client() is deprecated — set the API key with /ai in Telegram "
        "(or OPENAI_API_KEY in .env); the client is managed by services.ai_service.",
        kind="unknown",
    )


def provider_info() -> dict:
    """Small helper for scripts: which provider/model is active right now."""
    provider = _providers.get_or_default(active_provider_id_safe())
    return {
        "provider": provider.id,
        "label": provider.label,
        "model": active_model_label(),
        "ready": is_ready(),
        "embeddings": supports_embeddings(),
    }


def active_provider_id_safe() -> str:
    try:
        from services import ai_service
        return ai_service.active_provider_id()
    except Exception:
        return _providers.DEFAULT_PROVIDER

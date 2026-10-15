"""AI provider registry.

Every supported AI backend is described by a :class:`Provider` record: how to
reach it, which models to suggest, whether it can embed text (for knowledge-base
retrieval) and a short in-Telegram setup hint. ``services/ai_service`` is the
only module that uses these records to actually make calls.

Transport kinds
---------------
``openai_compat``
    ``POST {base_url}/chat/completions`` with ``Authorization: Bearer <key>``.
    This one code path covers OpenAI itself, Anthropic-compatible gateways,
    Google Gemini (its OpenAI-compatibility endpoint), Groq, OpenRouter,
    DeepSeek, Mistral, xAI, Together, Ollama/LM Studio and any custom endpoint.
``anthropic``
    Native Messages API (``POST {base_url}/messages``) — used for Anthropic so
    we do not depend on their OpenAI-compatibility shim being enabled.
``codex``
    Local Codex CLI (ChatGPT subscription); handled by ``services/codex_service``.

Adding a provider = adding one entry below (plus a test).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    kind: str                        # "openai_compat" | "anthropic" | "codex"
    base_url: str                    # default API base ("" => must be set by owner)
    default_model: str
    models: tuple[str, ...] = ()     # suggested models for the picker
    key_url: str = ""                # where the owner gets an API key
    key_required: bool = True
    embed_model: str = ""            # "" => this provider cannot embed
    docs: str = ""                   # short setup hint shown in Telegram
    free_tier: bool = False          # "no credit card" friendly for new owners
    local: bool = False              # runs on the owner's own machine


PROVIDERS: dict[str, Provider] = {
    # ---------------------------------------------------------------- OpenAI ---
    "openai": Provider(
        id="openai",
        label="OpenAI (ChatGPT API)",
        kind="openai_compat",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        models=("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o", "o4-mini"),
        key_url="https://platform.openai.com/api-keys",
        embed_model="text-embedding-3-small",
        docs="Pay-as-you-go API key from platform.openai.com. Best quality + KB embeddings.",
    ),
    # -------------------------------------------------------------- Anthropic ---
    "anthropic": Provider(
        id="anthropic",
        label="Anthropic (Claude)",
        kind="anthropic",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-3-5-haiku-latest",
        models=("claude-3-5-haiku-latest", "claude-3-7-sonnet-latest",
                "claude-sonnet-4-latest"),
        key_url="https://console.anthropic.com/settings/keys",
        docs="API key from console.anthropic.com. Knowledge base uses keyword search "
             "(Anthropic has no embeddings API).",
    ),
    # --------------------------------------------------------- Google Gemini ---
    "google": Provider(
        id="google",
        label="Google Gemini",
        kind="openai_compat",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.5-flash",
        models=("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"),
        key_url="https://aistudio.google.com/app/apikey",
        embed_model="text-embedding-004",
        free_tier=True,
        docs="Free API key from Google AI Studio (generous free tier).",
    ),
    # ------------------------------------------------------------------ Groq ---
    "groq": Provider(
        id="groq",
        label="Groq (fast, free tier)",
        kind="openai_compat",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"),
        key_url="https://console.groq.com/keys",
        free_tier=True,
        docs="Free API key from console.groq.com — very fast, no credit card. "
             "Knowledge base uses keyword search (no embeddings API).",
    ),
    # ------------------------------------------------------------ OpenRouter ---
    "openrouter": Provider(
        id="openrouter",
        label="OpenRouter (many models, free ones)",
        kind="openai_compat",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        models=("openai/gpt-4o-mini", "anthropic/claude-3.5-haiku",
                "google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct:free"),
        key_url="https://openrouter.ai/keys",
        docs="One key, hundreds of models (there are free models too) — openrouter.ai/keys.",
    ),
    # -------------------------------------------------------------- DeepSeek ---
    "deepseek": Provider(
        id="deepseek",
        label="DeepSeek",
        kind="openai_compat",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=("deepseek-chat", "deepseek-reasoner"),
        key_url="https://platform.deepseek.com/api_keys",
        docs="Very cheap API key from platform.deepseek.com.",
    ),
    # --------------------------------------------------------------- Mistral ---
    "mistral": Provider(
        id="mistral",
        label="Mistral AI",
        kind="openai_compat",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        models=("mistral-small-latest", "mistral-medium-latest", "open-mistral-nemo"),
        key_url="https://console.mistral.ai/api-keys",
        docs="API key from console.mistral.ai (free tier available).",
    ),
    # ------------------------------------------------------------------- xAI ---
    "xai": Provider(
        id="xai",
        label="xAI (Grok)",
        kind="openai_compat",
        base_url="https://api.x.ai/v1",
        default_model="grok-3-mini",
        models=("grok-3-mini", "grok-3", "grok-4"),
        key_url="https://console.x.ai",
        docs="API key from console.x.ai.",
    ),
    # -------------------------------------------------------------- Together ---
    "together": Provider(
        id="together",
        label="Together AI",
        kind="openai_compat",
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        models=("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo"),
        key_url="https://api.together.xyz/settings/api-keys",
        docs="API key from api.together.xyz.",
    ),
    # ---------------------------------------------------------------- Ollama ---
    "ollama": Provider(
        id="ollama",
        label="Ollama (local, free)",
        kind="openai_compat",
        base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        models=("llama3.2", "qwen2.5", "mistral"),
        key_required=False,
        embed_model="nomic-embed-text",
        local=True,
        docs="Runs on your own machine: install Ollama, then `ollama pull llama3.2`. "
             "No API key needed — the bot must run on the same computer.",
    ),
    # -------------------------------------------------------------- LM Studio ---
    "lmstudio": Provider(
        id="lmstudio",
        label="LM Studio (local, free)",
        kind="openai_compat",
        base_url="http://localhost:1234/v1",
        default_model="local-model",
        models=("local-model",),
        key_required=False,
        local=True,
        docs="Load a model in LM Studio and start its local server (port 1234).",
    ),
    # ---------------------------------------------------------------- Custom ---
    "custom": Provider(
        id="custom",
        label="Custom OpenAI-compatible endpoint",
        kind="openai_compat",
        base_url="",
        default_model="",
        models=(),
        docs="Any server exposing /chat/completions (a proxy, a self-hosted model, "
             "an aggregator). Send the base URL and the model name.",
    ),
    # ----------------------------------------------------------------- Codex ---
    "codex": Provider(
        id="codex",
        label="ChatGPT subscription via Codex CLI",
        kind="codex",
        base_url="",
        default_model="",
        models=(),
        key_required=False,
        local=True,
        docs="Uses `codex exec` with your ChatGPT login (install: npm i -g @openai/codex, "
             "then `codex login`). The bot must run on that machine.",
    ),
}

# Order used by the picker: practical free/cheap options first, local last.
PROVIDER_ORDER: tuple[str, ...] = (
    "openai", "google", "groq", "openrouter", "anthropic", "deepseek",
    "mistral", "xai", "together", "custom", "ollama", "lmstudio", "codex",
)

DEFAULT_PROVIDER = "openai"


def get(provider_id: str) -> Provider | None:
    return PROVIDERS.get((provider_id or "").strip().lower())


def get_or_default(provider_id: str) -> Provider:
    return get(provider_id) or PROVIDERS[DEFAULT_PROVIDER]


def ids() -> list[str]:
    return [pid for pid in PROVIDER_ORDER if pid in PROVIDERS]


def ordered() -> list[Provider]:
    return [PROVIDERS[pid] for pid in ids()]


def label_for(provider_id: str) -> str:
    provider = get(provider_id)
    return provider.label if provider else (provider_id or "unknown")


def models_for(provider_id: str) -> list[str]:
    provider = get(provider_id)
    return list(provider.models) if provider else []


def supports_embeddings(provider_id: str) -> bool:
    provider = get(provider_id)
    return bool(provider and provider.embed_model)


def key_env_var(provider_id: str) -> str:
    """Environment variable that can hold this provider's key (terminal setup)."""
    return {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "xai": "XAI_API_KEY",
        "together": "TOGETHER_API_KEY",
        "ollama": "",
        "lmstudio": "",
        "custom": "AI_API_KEY",
        "codex": "",
    }.get(provider_id, "AI_API_KEY")

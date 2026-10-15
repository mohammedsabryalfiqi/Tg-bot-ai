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
    Cerebras, DeepSeek, Mistral, xAI, Together, NVIDIA, SambaNova, Hugging Face,
    Ollama/LM Studio and any custom endpoint.
``anthropic``
    Native Messages API (``POST {base_url}/messages``) — used for Anthropic so
    we do not depend on their OpenAI-compatibility shim being enabled.
``codex``
    Local Codex CLI (ChatGPT subscription); handled by ``services/codex_service``.

Free providers
--------------
Most owners start without a credit card, so the registry marks every backend
that can be used at zero cost:

``free_tier``  a hosted provider with a usable no-card free tier (``free_note``
               carries the one-line limit summary shown by ``/freeai``).
``local``      runs on the owner's own machine — free, no key, no internet.

The picker lists free options first, and ``switch_suggestions()`` powers the
"try a free provider instead" buttons shown when a key is rejected or the
account runs out of credit. Free-tier limits and model names change often: the
``/ai`` menu can load the live model list from the provider itself, so a stale
suggestion here never blocks an owner.

Adding a provider = adding one entry below (plus a test).
"""

from __future__ import annotations

from dataclasses import dataclass


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
    key_prefixes: tuple[str, ...] = ()  # how this provider's keys start
    embed_model: str = ""            # "" => this provider cannot embed
    docs: str = ""                   # short setup hint shown in Telegram
    free_tier: bool = False          # usable at no cost, no credit card
    free_note: str = ""              # one-line free-tier summary for /freeai
    local: bool = False              # runs on the owner's own machine


PROVIDERS: dict[str, Provider] = {
    # =========================================================================
    # Free tiers first — no credit card, no balance top-up.
    # =========================================================================
    # --------------------------------------------------------- Google Gemini ---
    "google": Provider(
        id="google",
        label="Google Gemini",
        kind="openai_compat",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.5-flash",
        models=("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash",
                "gemini-2.5-pro"),
        key_url="https://aistudio.google.com/app/apikey",
        key_prefixes=("AIza", "ya29."),
        embed_model="text-embedding-004",
        free_tier=True,
        free_note="Best free tier: hundreds of free requests/day with any Google "
                  "account — no card, no phone number.",
        docs="Free API key from Google AI Studio: sign in with a Google account, "
             "press “Create API key”, done. Free tier is rate limited per day "
             "(resets at midnight Pacific time) and the newest Pro models need "
             "billing — Flash models are the free ones. Also does KB embeddings.",
    ),
    # ------------------------------------------------------------------ Groq ---
    "groq": Provider(
        id="groq",
        label="Groq (fastest)",
        kind="openai_compat",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gpt-oss-120b",
                "gemma2-9b-it"),
        key_url="https://console.groq.com/keys",
        key_prefixes=("gsk_",),
        free_tier=True,
        free_note="Free forever with an email only: thousands of requests/day on the "
                  "small models, ~30 requests/minute. Replies in milliseconds.",
        docs="Free API key from console.groq.com — sign up with an email (no credit "
             "card), open “API Keys”, create one. Very fast. Knowledge base uses "
             "keyword search (Groq has no embeddings API). If a model name is "
             "rejected, use “Load models” — Groq rotates its free catalogue.",
    ),
    # -------------------------------------------------------------- Cerebras ---
    "cerebras": Provider(
        id="cerebras",
        label="Cerebras (fast, big daily quota)",
        kind="openai_compat",
        base_url="https://api.cerebras.ai/v1",
        default_model="gpt-oss-120b",
        models=("gpt-oss-120b", "qwen-3-32b", "llama-3.3-70b"),
        key_url="https://cloud.cerebras.ai/",
        key_prefixes=("csk-",),
        free_tier=True,
        free_note="About 1M free tokens/day and thousands of free requests/day — "
                  "email or GitHub signup, no credit card.",
        docs="Free key from cloud.cerebras.ai → API Keys (email or GitHub, no card). "
             "The free catalogue changes often, so after connecting press “Load "
             "models” and pick one your key can actually run. Free tier context is "
             "limited (~8K tokens).",
    ),
    # ------------------------------------------------------------ OpenRouter ---
    "openrouter": Provider(
        id="openrouter",
        label="OpenRouter (hundreds of models)",
        kind="openai_compat",
        base_url="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.3-70b-instruct:free",
        models=("meta-llama/llama-3.3-70b-instruct:free",
                "google/gemini-2.0-flash-exp:free",
                "openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"),
        key_url="https://openrouter.ai/keys",
        key_prefixes=("sk-or-",),
        free_tier=True,
        free_note="One free key for hundreds of models. Models whose name ends in "
                  "“:free” cost nothing (~50 free requests/day).",
        docs="Free key from openrouter.ai/keys. Pick a model that ends in “:free” to "
             "stay at zero cost — press “Load models” and the free ones are listed "
             "first. Paid models need credit, so a “no credit” error here means you "
             "picked a non-:free model.",
    ),
    # --------------------------------------------------------------- Mistral ---
    "mistral": Provider(
        id="mistral",
        label="Mistral AI",
        kind="openai_compat",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        models=("mistral-small-latest", "ministral-3b", "mistral-medium-latest",
                "open-mistral-nemo", "codestral-latest"),
        key_url="https://console.mistral.ai/api-keys",
        free_tier=True,
        free_note="Free “Experiment” plan: roughly 1 request/second and a large "
                  "monthly token allowance. No card, but phone verification.",
        docs="Free API key from console.mistral.ai (no credit card; the free plan "
             "asks for phone verification and may use your prompts to improve their "
             "models unless you opt out). Good multilingual quality, ~1 request per "
             "second.",
    ),
    # ----------------------------------------------------------- NVIDIA (NIM) ---
    "nvidia": Provider(
        id="nvidia",
        label="NVIDIA NIM (free signup credits)",
        kind="openai_compat",
        base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.1-8b-instruct",
        models=("meta/llama-3.1-8b-instruct", "meta/llama-3.3-70b-instruct",
                "qwen/qwen2.5-7b-instruct"),
        key_url="https://build.nvidia.com/",
        key_prefixes=("nvapi-",),
        free_tier=True,
        free_note="Free API credits with an NVIDIA account (no card). Credits run out "
                  "instead of refreshing daily.",
        docs="Free key from build.nvidia.com (NVIDIA account, no credit card). Copy "
             "the model name exactly as shown on the model's page — NVIDIA names "
             "include the vendor, e.g. meta/llama-3.1-8b-instruct.",
    ),
    # ------------------------------------------------------------- SambaNova ---
    "sambanova": Provider(
        id="sambanova",
        label="SambaNova",
        kind="openai_compat",
        base_url="https://api.sambanova.ai/v1",
        default_model="Meta-Llama-3.3-70B-Instruct",
        models=("Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct",
                "Qwen3-32B", "DeepSeek-R1-0528"),
        key_url="https://community.sambanova.ai/",
        free_tier=True,
        free_note="Free developer key with generous rate limits on open models — "
                  "email signup, no card.",
        docs="Free key from community.sambanova.ai (developer portal, no card). Fast "
             "open-weight models; use “Load models” for the exact names your key can "
             "run.",
    ),
    # ------------------------------------------------------------ Hugging Face ---
    "huggingface": Provider(
        id="huggingface",
        label="Hugging Face (small allowance)",
        kind="openai_compat",
        base_url="https://router.huggingface.co/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct",
        models=("meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct",
                "mistralai/Mistral-7B-Instruct-v0.3"),
        key_url="https://huggingface.co/settings/tokens",
        key_prefixes=("hf_",),
        free_tier=True,
        free_note="Free with an HF access token (read scope) — a small monthly "
                  "allowance, enough for testing and light traffic.",
        docs="Free token from huggingface.co/settings/tokens (“Read” permission is "
             "enough). Model names are the repo ids, e.g. "
             "meta-llama/Llama-3.3-70B-Instruct. Some models are gated: open their "
             "page once and accept the licence. Small free monthly allowance.",
    ),
    # ---------------------------------------------------------- Pollinations ---
    "pollinations": Provider(
        id="pollinations",
        label="Pollinations (no key needed)",
        kind="openai_compat",
        base_url="https://text.pollinations.ai/openai/v1",
        default_model="openai",
        models=("openai", "openai-fast"),
        key_required=False,
        free_tier=True,
        free_note="Zero signup and zero keys: works the moment you pick it. "
                  "Best effort — roughly one request per 30 seconds per IP.",
        docs="⚠️ Community-run, best-effort endpoint: no signup and no key, but about "
             "one request per 30 seconds per IP and no uptime promise, so it suits "
             "testing rather than a busy shop. Customer messages go to a third "
             "party — switch to Google/Groq/Cerebras for real traffic.",
    ),
    # =========================================================================
    # Paid providers (best quality; need credit or a subscription).
    # =========================================================================
    # ---------------------------------------------------------------- OpenAI ---
    "openai": Provider(
        id="openai",
        label="OpenAI (ChatGPT API)",
        kind="openai_compat",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        models=("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o", "o4-mini"),
        key_url="https://platform.openai.com/api-keys",
        key_prefixes=("sk-",),
        embed_model="text-embedding-3-small",
        docs="Pay-as-you-go API key from platform.openai.com — it needs credit on the "
             "account (a ChatGPT Plus subscription is NOT API credit). Best quality "
             "plus KB embeddings. No card / no credit yet? Use a 🆓 provider.",
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
        key_prefixes=("sk-ant-",),
        docs="API key from console.anthropic.com (needs credit on the account; a "
             "Claude subscription is not API credit). Knowledge base uses keyword "
             "search (Anthropic has no embeddings API).",
    ),
    # -------------------------------------------------------------- DeepSeek ---
    "deepseek": Provider(
        id="deepseek",
        label="DeepSeek (very cheap)",
        kind="openai_compat",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=("deepseek-chat", "deepseek-reasoner"),
        key_url="https://platform.deepseek.com/api_keys",
        key_prefixes=("sk-",),
        docs="Very cheap API key from platform.deepseek.com — the balance must be "
             "topped up before the key works (a few dollars last a long time).",
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
        key_prefixes=("xai-",),
        docs="API key from console.x.ai. New accounts sometimes get a small trial "
             "credit; after that it is pay-as-you-go.",
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
        docs="API key from api.together.xyz — needs a minimum top-up, so use a 🆓 "
             "provider if you do not want to pay yet.",
    ),
    # =========================================================================
    # Custom + local (free, but the owner supplies the endpoint / hardware).
    # =========================================================================
    # ---------------------------------------------------------------- Custom ---
    "custom": Provider(
        id="custom",
        label="Custom OpenAI-compatible endpoint",
        kind="openai_compat",
        base_url="",
        default_model="",
        models=(),
        docs="Any server exposing /chat/completions (a proxy, a self-hosted model, "
             "an aggregator, Cloudflare Workers AI). Send the base URL and the model "
             "name; the key is optional.",
    ),
    # ---------------------------------------------------------------- Ollama ---
    "ollama": Provider(
        id="ollama",
        label="Ollama (local, 100% free)",
        kind="openai_compat",
        base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        models=("llama3.2", "qwen2.5", "mistral"),
        key_required=False,
        embed_model="nomic-embed-text",
        local=True,
        free_tier=True,
        free_note="Completely free and private — the model runs on your own computer. "
                  "Needs ~8 GB RAM for a small model.",
        docs="Runs on your own machine: install Ollama, then `ollama pull llama3.2`. "
             "No API key and no internet needed — but the bot must run on the same "
             "computer (or set the base URL to that computer's address).",
    ),
    # -------------------------------------------------------------- LM Studio ---
    "lmstudio": Provider(
        id="lmstudio",
        label="LM Studio (local, 100% free)",
        kind="openai_compat",
        base_url="http://localhost:1234/v1",
        default_model="local-model",
        models=("local-model",),
        key_required=False,
        local=True,
        free_tier=True,
        free_note="Completely free and private — a local model with a Windows/macOS "
                  "interface.",
        docs="Load a model in LM Studio and start its local server (port 1234), then "
             "test here. No key needed; the bot must run on the same computer.",
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
             "then `codex login`). Reuses a ChatGPT plan you already pay for — no API "
             "key. The bot must run on that machine.",
    ),
}

# Order used by the picker: free hosted first, then paid, then custom/local.
PROVIDER_ORDER: tuple[str, ...] = (
    # free hosted (no credit card)
    "google", "groq", "cerebras", "openrouter", "mistral", "nvidia",
    "sambanova", "huggingface", "pollinations",
    # paid / credit needed
    "openai", "anthropic", "deepseek", "xai", "together",
    # custom + local (free, but you supply the endpoint or the hardware)
    "custom", "ollama", "lmstudio", "codex",
)

DEFAULT_PROVIDER = "openai"

# Free providers offered first when a key fails or the account has no credit:
# reliable, generous and quick to sign up for.
FREE_SUGGESTIONS: tuple[str, ...] = ("google", "groq", "cerebras", "openrouter", "mistral")

_KEY_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "xai": "XAI_API_KEY",
    "together": "TOGETHER_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "sambanova": "SAMBANOVA_API_KEY",
    "huggingface": "HF_TOKEN",
    "ollama": "",
    "lmstudio": "",
    "pollinations": "",
    "custom": "AI_API_KEY",
    "codex": "",
}


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


def key_prefix_matches(key: str) -> list[Provider]:
    """Every provider whose keys start like this one (by their documented prefix).

    Used to catch the classic mistake of adding, say, a Gemini key while Groq is
    the selected provider — long before a request is sent. An empty list means
    "no known shape" (Mistral, Together, SambaNova and custom endpoints do not
    publish a fixed prefix), which is never treated as an error.
    """
    value = (key or "").strip()
    if not value:
        return []
    matches = []
    for provider in ordered():
        if any(value.startswith(prefix) for prefix in provider.key_prefixes):
            matches.append(provider)
    return matches


def looks_like_key_of(key: str) -> Provider | None:
    """Best single guess for a pasted key's owner, or None when ambiguous."""
    matches = key_prefix_matches(key)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    longest = max(len(prefix) for provider in matches for prefix in provider.key_prefixes
                  if (key or "").strip().startswith(prefix))
    best = [provider for provider in matches
            if any((key or "").strip().startswith(prefix) and len(prefix) == longest
                   for prefix in provider.key_prefixes)]
    return best[0] if len(best) == 1 else None


def supports_embeddings(provider_id: str) -> bool:
    provider = get(provider_id)
    return bool(provider and provider.embed_model)


def key_env_var(provider_id: str) -> str:
    """Environment variable that can hold this provider's key (terminal setup)."""
    return _KEY_ENV_VARS.get((provider_id or "").strip().lower(), "AI_API_KEY")


# =============================================================================
# Free-provider helpers (power /freeai and the "try a free one" buttons)
# =============================================================================
def is_free(provider: Provider) -> bool:
    """Zero-cost to run: a hosted free tier, or a local model."""
    return bool(provider.free_tier or provider.local or not provider.key_required)


def free_ids() -> list[str]:
    """Free provider ids in picker order (hosted free tiers first, local last)."""
    hosted, local = [], []
    for pid in ids():
        provider = PROVIDERS[pid]
        if provider.local:
            local.append(pid)
        elif is_free(provider):
            hosted.append(pid)
    return hosted + local


def free() -> list[Provider]:
    return [PROVIDERS[pid] for pid in free_ids()]


def needs_credit(provider_id: str) -> bool:
    """True for providers that only work with paid credit."""
    provider = get(provider_id)
    return bool(provider and not is_free(provider) and provider.id != "custom")


def switch_suggestions(provider_id: str | None = None, limit: int = 3) -> list[Provider]:
    """Free providers to recommend when the current one fails.

    Excludes the provider the owner is already on, prefers the well-known
    generous tiers, and falls back to any remaining free provider.
    """
    current = (provider_id or "").strip().lower()
    ordered_suggestions = [pid for pid in FREE_SUGGESTIONS if pid != current]
    ordered_suggestions += [pid for pid in free_ids()
                            if pid not in ordered_suggestions and pid != current]
    out = [PROVIDERS[pid] for pid in ordered_suggestions if pid in PROVIDERS]
    return out[:max(1, limit)]


def free_menu_lines() -> list[str]:
    """Plain-text lines describing every zero-cost option (used by /freeai)."""
    lines: list[str] = []
    for provider in free():
        tag = "💻" if provider.local else "🆓"
        note = provider.free_note or provider.docs or ""
        lines.append(f"{tag} {provider.label}")
        if note:
            lines.append(f"    {note}")
        if provider.key_url:
            lines.append(f"    Key: {provider.key_url}")
        elif not provider.key_required:
            lines.append("    No API key needed.")
    return lines

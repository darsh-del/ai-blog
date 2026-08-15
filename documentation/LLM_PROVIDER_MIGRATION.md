# LLM Provider Migration — Google Gemini → OpenAI (via LiteLLM)

Article + title generation now routes through [LiteLLM](https://github.com/BerriAI/litellm) instead of the Google GenAI SDK directly. The default provider is OpenAI (`gpt-4o-mini`), but LiteLLM's naming lets you swap to Gemini, Anthropic, or any of the 100+ providers it supports without a code change — just an env var.

**Nothing else in the codebase changed.** `call_llm(prompt, config)` has the same signature; every caller (`agents.py`, `orchestrator.py`, `scraper.py`) works untouched.

## Quickstart

```bash
pip install -r requirements.txt   # litellm is already listed
```

In `.env`:
```
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

That's it. Run as before.

## How the provider is chosen

LiteLLM inspects the model name and picks a provider automatically:

| Model string             | Provider  | Required env var          |
|--------------------------|-----------|---------------------------|
| `gpt-4o-mini`, `gpt-4o`  | OpenAI    | `OPENAI_API_KEY`          |
| `openai/gpt-4o`          | OpenAI    | `OPENAI_API_KEY`          |
| `gemini/gemini-2.0-flash`| Gemini    | `GEMINI_API_KEY` (or `GOOGLE_AI_STUDIO_API_KEY`) |
| `anthropic/claude-sonnet-5` | Anthropic | `ANTHROPIC_API_KEY`      |
| `azure/my-deployment`    | Azure     | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |

Full list: https://docs.litellm.ai/docs/providers

## Env vars

| Var                     | Default            | Purpose |
|-------------------------|--------------------|---------|
| `LLM_MODEL`             | `gpt-4o-mini`      | Text-gen model. Any LiteLLM-compatible name. |
| `LLM_FALLBACK_MODELS`   | `gpt-4o-mini,gpt-4o,gpt-4-turbo` | Comma-separated chain used on rate-limit / failure. |
| `LLM_RPM_LIMIT_FLASH`   | inherits `GEMINI_RPM_LIMIT_FLASH` (15) | Cap for `mini`/`lite`/`haiku`/`flash` tier. |
| `LLM_RPM_LIMIT_PRO`     | inherits `GEMINI_RPM_LIMIT_PRO`   (2) | Cap for `pro`/`o1`/`opus` tier. |
| `LLM_RPM_LIMIT_DEFAULT` | inherits `GEMINI_RPM_LIMIT_DEFAULT` (15) | Cap for anything else. |
| `GEMINI_MAX_RETRIES`    | 5                  | (Legacy name.) Retries per model before falling through. |
| `OPENAI_API_KEY`        | —                  | Required if using OpenAI. |
| `ANTHROPIC_API_KEY`     | —                  | Required if using Anthropic. |
| `GOOGLE_AI_STUDIO_API_KEY` | —               | Required if using Gemini text-gen OR Imagen images. |
| `GEMINI_MODEL`          | `gemini-2.0-flash` | **Still used by [image_client.py](../src/image_client.py)** for Imagen. Leave set if you want images. |
| `IMAGE_MODEL`           | `imagen-4.0-generate-001` | Imagen model id. |
| `IMAGE_GENERATION_RATIO`| `1.0`              | 0.0 = no images. |

## What actually changed

Only three files:

- [src/llm_client.py](../src/llm_client.py) — `call_llm` internals now use `litellm.completion(...)`. Rate limiter, cooldowns, fallback logic, `RateLimitExhaustedError` — all preserved. `ClientManager` (Google GenAI client) still there because [src/image_client.py](../src/image_client.py) uses it for Imagen.
- [src/config.py](../src/config.py) — added `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, generic `LLM_RPM_LIMIT_*` aliases. `validate_api_key()` now detects provider from model name.
- [example.env](../example.env) — reordered LLM keys to lead with `OPENAI_API_KEY` + `LLM_MODEL`.

## What did NOT change

- Every call site of `call_llm(prompt, config)`.
- The `LLMConfig` dataclass in `src/models.py`.
- Image generation (still Google Imagen).
- Weaviate/text2vec (still Google embeddings if enabled).
- Rate-limit + cooldown + circuit-breaker + fallback semantics.
- Cost tracking — now uses `litellm.completion_cost()` which reads LiteLLM's cross-provider pricing DB (no more hardcoded Gemini pricing table to maintain).

## Model-tier notes for the rate limiter

The `get_limiter_for_model` heuristic maps model names to token-bucket caps by matching substrings. This works out-of-the-box for the common patterns:

- Contains `pro` / `o1` / `opus` → **PRO** bucket (low RPM, capacity 1)
- Contains `mini` / `flash` / `lite` / `haiku` → **FLASH** bucket (higher RPM, capacity 2)
- Anything else → **DEFAULT** bucket

If you're on OpenAI's paid tier, the built-in RPM caps (inherited from Gemini defaults, 2/15 RPM) are far too conservative. Bump them:

```
LLM_RPM_LIMIT_FLASH=500
LLM_RPM_LIMIT_PRO=100
LLM_RPM_LIMIT_DEFAULT=200
```

Or disable the app-level limiter entirely and let OpenAI's own rate-limits push back:

```
RATE_LIMIT_ENABLED=False
```

## Cost & pricing

`litellm.completion_cost(completion_response=response)` returns the exact per-call USD cost using LiteLLM's up-to-date pricing DB. This replaces the hand-maintained pricing table that was in the old `_calculate_cost` function. If LiteLLM's DB doesn't know a model (rare, mostly for preview releases), cost falls back to `0.0` and a debug log line is written.

## Switching back to Gemini

```
LLM_MODEL=gemini/gemini-2.0-flash
LLM_FALLBACK_MODELS=gemini/gemini-2.5-flash,gemini/gemini-2.5-flash-lite,gemini/gemini-2.5-pro
GOOGLE_AI_STUDIO_API_KEY=...
```

No code change.

## Sanity check

```bash
python3 -c "
from src.llm_client import call_llm
from src.models import LLMConfig
print(call_llm('Reply with the single word: pong.', LLMConfig(model_name='gpt-4o-mini', max_tokens=10)))
"
```

Expected: `pong` (or a close variant). If you get an auth error, `OPENAI_API_KEY` isn't set. If you get a rate-limit error immediately, drop `LLM_RPM_LIMIT_*` — those caps are gating you.

## Cost expectations (rough, per article)

Article generation prompts land around 4–8k input tokens and produce 2–4k output tokens.

| Model           | Input $/1M | Output $/1M | Cost per article |
|-----------------|------------|-------------|------------------|
| `gpt-4o-mini`   | $0.15      | $0.60       | ~$0.003          |
| `gpt-4o`        | $2.50      | $10.00      | ~$0.05           |
| `gpt-4.1`       | $2.00      | $8.00       | ~$0.04           |
| `gemini-2.0-flash` | $0.075  | $0.30       | ~$0.001          |

For bulk campaign runs (100+ articles), `gpt-4o-mini` is the pragmatic default. Escalate to `gpt-4o` only for articles where the client is paying premium.

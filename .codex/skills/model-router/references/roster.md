# Model roster and pricing

**Updated: 2026-08-22.** Prices are in USD per 1 million tokens (input / output) at publicly listed rates. If considerable time has passed since this date, verify the prices before citing them.

## Contents

- [Anthropic](#anthropic)
- [OpenAI](#openai)
- [Google](#google)
- [Open-weight](#open-weight)
- [Effort scale](#effort-scale)
- [Cost factors](#cost-factors)
- [Sources](#sources)

## Anthropic

| Model | Price | Notes |
|---|---|---|
| Fable 5 | $10 / $50 | Highest tier |
| Mythos 5 | $10 / $50 | Limited release |
| Opus 5 | $5 / $25 | Strongest reasoning among generally available models |
| Opus 4.8 / 4.7 / 4.6 / 4.5 | $5 / $25 | Older versions, still available |
| Sonnet 5 | $2 / $10 | Introductory price, fixed from September 2026 |
| Sonnet 4.6 / 4.5 | $3 / $15 | |
| Haiku 4.5 | $1 / $5 | Fastest and most compact |

The 1M-token context window is available at standard pricing. Models from 4.7 onward use a new tokenizer—the same passage consumes approximately 30% more tokens, so account for this when comparing their prices with older versions.

## OpenAI

| Model | Price | Notes |
|---|---|---|
| gpt-5.6-sol | — | Flagship; the `gpt-5.6` alias points here |
| gpt-5.6-terra | — | Balanced; cheaper than sol |
| gpt-5.6-luna | — | High-volume, cost-efficient workloads |
| GPT-5.5 | $5–10 / $30–45 | Price tier changes at 272K tokens |
| GPT-5.4 | $2.50–5 / $15–22.50 | Price tier changes at 272K tokens |
| GPT-5 | $1.25 / $10 | |
| GPT-5 Mini | $0.25 / $2 | |
| GPT-5 Nano | $0.05 / $0.40 | Cheapest |
| o3-pro | $20 / $80 | Expensive, deep reasoning |
| o3 | $2 / $8 | |
| o4-mini / o3-mini | $1.10 / $4.40 | |

Public pricing for the gpt-5.6 family could not be confirmed from an official page at the time of the update, so the prices are left blank rather than guessed. When estimating gpt-5.6 costs, use GPT-5.5 as an upper bound and clearly state that it is an estimate.

Strengths described in the documentation include sustained reasoning across multiple turns, programmable tool calling, judgment about layout and visual hierarchy, and strong performance with fewer output tokens.

## Google

| Model | Price | Notes |
|---|---|---|
| Gemini 3.7 Flash | $0.75 / $3.75 | Promotional pricing through December 31, 2026; designed for agentic and multimodal work |
| Gemini 3.6 Flash | $0.75 / $3.75 | Promotional pricing through December 31, 2026 |
| Gemini 3.5 Flash | $1.50 / $9 | Limited free tier available |
| Gemini 3.5 Flash-Lite | $0.30 / $2.50 | Cheapest generally available model |

Gemini does not expose discrete effort levels like Claude or OpenAI. Thinking tokens are billed as output, and the model regulates its own reasoning level. Therefore, when recommending Gemini, write `n/a (auto)` in the Effort column instead of inventing a level.

## Open-weight

| Model | Reference price | Strengths |
|---|---|---|
| Kimi K3 | — | General-purpose; reasoning (GPQA Diamond 93.5%) and terminal use (Terminal-Bench 2.1 88.3%) |
| DeepSeek V4 Pro | — | Agentic coding (SWE-bench 80.6%) and large context |
| DeepSeek V4 Flash | $0.14 / $0.28 | Cheapest; still reasonably capable at reasoning |
| GLM 5.2 | $0.95 / $3 | Fast (approximately 347 tokens/s) with balanced pricing |
| MiniMax M3 | — | Consistent across reasoning, coding, and computer use |
| Llama 3.3 70B | $0.59 / $0.70 | Very fast (approximately 2,500 tokens/s); suitable for simple bulk workloads |

Open-weight pricing depends on the inference provider. The figures above are market references, not official list prices.

## Effort scale

**Anthropic** — `low` → `medium` → `high` → `xhigh` → `max`. The default is `high` for Opus 5, Opus 4.8/4.7, Sonnet 5, Sonnet 4.6, and Fable 5.

- `low`: significantly reduces token use
- `medium`: balanced
- `high`: default
- `xhigh`: long-running work (30+ minutes); available on Fable 5, Mythos 5, Opus 5/4.8/4.7, and Sonnet 5
- `max`: unlimited reasoning tokens; available on Fable 5, Mythos 5, Opus 5/4.8, Opus 4.7/4.6, and Sonnet 5/4.6

Set this through `output_config={"effort": "..."}`. It is supported on the Claude API, AWS/Bedrock, Google Cloud, and Microsoft Foundry.

**OpenAI** — `reasoning_effort`: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Supported values vary by model; GPT-5.5 defaults to `medium`. Check the model page before using a high level—not every model accepts all seven levels.

**Google** — no discrete effort-level parameter; see the Google section above.

Rough cross-provider mapping: Anthropic `low`≈OpenAI `low`, `medium`≈`medium`, `high`≈`high`, `xhigh`≈`xhigh`, and `max`≈`max`. This maps names, not actual reasoning-token usage, so do not use it for precise cost comparisons.

## Cost factors

These apply to Anthropic. Other providers have similar mechanisms with different multipliers:

- Prompt caching: writes cost 1.25× (five-minute TTL) or 2× (one-hour TTL); reads cost 0.1×
- Batch API: 50% discount on both input and output
- Data residency (`inference_geo: "us"`): 1.1×

Cached reads at 0.1× are the largest source of savings in a long session: rereading a 100K-token context 20 times costs the same as reading it fresh twice. In a cached session, this means the true cost of **keeping** the same model is much lower than switching models, because switching loses the entire cache. Consider this before recommending repeated model changes between short steps.

## Sources

- [Claude Platform — Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Platform — Effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- [OpenAI — Reasoning models](https://developers.openai.com/api/docs/guides/reasoning)
- [OpenAI — Model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Gemini API — Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Vellum — Open LLM Leaderboard](https://www.vellum.ai/open-llm-leaderboard)

# Model catalog and pricing provenance

LEA keeps routing capabilities and prices in one versioned catalog. The current
snapshot was verified on **2026-09-04** against the providers' own documentation.

```bash
lea models --json
```

The JSON output includes the verification date, every active model's pricing basis,
and the source URL. This makes cost estimates inspectable in CI or downstream tools.

## Official sources

| Provider | Source | Catalog basis |
| --- | --- | --- |
| xAI | [Models and pricing](https://docs.x.ai/developers/pricing) | Standard API token prices |
| Anthropic | [Claude pricing](https://docs.anthropic.com/en/docs/about-claude/pricing) | Global standard API prices |
| OpenAI | [API models](https://platform.openai.com/docs/models) | Standard API token prices |
| Google | [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) | Standard paid tier; current introductory rates where stated |
| DeepSeek | [Models and pricing](https://api-docs.deepseek.com/quick_start/pricing) | Cache-miss input and output prices |
| Moonshot | [Kimi pricing](https://platform.kimi.ai/docs/pricing/chat) | Global API prices |
| Alibaba | [Model Studio pricing](https://help.aliyun.com/zh/model-studio/model-pricing) | Beijing list price converted at 7.18 CNY/USD |
| Ollama | [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) | $0 hosted API token cost; local hardware cost excluded |

## Lifecycle handling

Deprecated aliases remain internally readable so historical cost ledgers and older
configuration files can be explained, but they are excluded from `lea models` and
never selected by the router. Their catalog prices reflect the provider's actual
redirect target, not the former promotional price.

For example, xAI retired `grok-4-fast` and `grok-code-fast-1` in May 2026. LEA now
routes to `grok-4.3` and `grok-build-0.1` respectively. See xAI's
[retirement notice](https://docs.x.ai/developers/migration/may-15-retirement).

## Important limitations

- Prices exclude taxes, tools, storage, priority tiers, batch discounts, and regional
  premiums unless explicitly noted.
- Alibaba prices are currency conversions and may move with exchange rates.
- Promotional rates can expire. The verification date is part of every model entry
  so stale snapshots are visible rather than silent.
- OpenRouter availability and pricing can differ from native provider APIs.
- Ollama models vary in context, quality, and speed; `ollama-local` is an opt-in
  transport placeholder rather than a claim about one specific model.
- The runtime ledger uses reported token usage; preflight checks deliberately use a
  conservative token estimate so the budget guard errs on the safe side.

When changing a model or price, update its source, bump `CATALOG_AS_OF`, run
`lea benchmark --json`, and update the published benchmark table if totals changed.

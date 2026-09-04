<p align="center">
  <img src="assets/lea-terminal.svg" alt="LEA cost-aware multi-model coding agent" width="820">
</p>

<p align="center">
  <strong>Spend intelligence where it matters.</strong><br>
  A budget-native coding agent that plans with strong models, implements with fast models,
  and reviews with an independent provider.
</p>

<p align="center">
  <a href="https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/actions/workflows/ci.yml"><img src="https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-7A5AF8" alt="Apache-2.0"></a>
  <a href="https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/stargazers"><img src="https://img.shields.io/github/stars/charlesenchine-arch/Light-weight-Ensemble-Agent?style=social" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#why-lea">Why LEA</a> ·
  <a href="docs/README.zh-CN.md">简体中文</a>
</p>

---

LEA (**Light-weight Ensemble Agent**) is a local coding agent that treats your API
budget as a first-class constraint. Instead of sending every token to one flagship
model, LEA routes each stage to the model that offers the best value for that job.

```text
$ lea run --budget 10cny "Fix the flaky auth tests and explain the cause"

  plan    → capable reasoning model
  code    → fast coding model
  review  → a different provider
  spend   → tracked and capped before every request
```

> LEA is early-stage software. Use it on version-controlled projects and review
> changes before shipping them to production.

## Quick start

### Install from GitHub

With [pipx](https://pipx.pypa.io/) installed:

```bash
pipx install git+https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent.git
```

Or install for development:

```bash
git clone https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent.git
cd Light-weight-Ensemble-Agent
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add at least one provider key:

```dotenv
XAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=...
# OPENAI_API_KEY=...
# GEMINI_API_KEY=...
# DEEPSEEK_API_KEY=...
```

Then open a terminal in any repository:

```bash
lea
```

Or run one task directly:

```bash
lea run --budget 1usd "Add pagination to the users endpoint"
```

Preview the exact route without calling an API:

```bash
lea run --dry-run --budget 0.25usd "Refactor the payment pipeline"
```

## Why LEA?

Most coding agents optimize for quality or latency. LEA optimizes the whole run:

| Concern | Traditional single-model agent | LEA |
| --- | --- | --- |
| Planning | Same model as every other step | Strong model for high-leverage decisions |
| Implementation | Expensive model consumes most tokens | Fast, cost-efficient coding model |
| Review | Often self-reviews | Different model, preferably another provider |
| Budget | Cost shown after the run | Route fitted before the run; every call guarded |
| Interruption | Wait for the active request | Cancel the HTTP call or local process and steer |
| Provider lock-in | One API | xAI, Anthropic, OpenAI, Gemini, DeepSeek, Kimi, Qwen, OpenRouter |

LEA's default policy is simple:

> **Spend on the plan. Save on the implementation. Diversify the review.**

## How it works

```mermaid
flowchart LR
    U[User task + budget] --> C[Local classification]
    C --> R[Cost-aware router]
    R --> P[Plan]
    P --> D{UI work?}
    D -->|yes| G[Design]
    D -->|no| I[Implement]
    G --> I
    I --> V[Independent review]
    V -->|blocking issues| F[Targeted fix]
    F --> V
    V -->|pass| O[Result + cost ledger]
```

Before each provider call, LEA conservatively estimates the request cost from the
serialized prompt and the selected model's catalog price. It reduces the output
limit when needed and refuses calls that cannot produce a useful answer inside the
remaining budget.

The full architecture is documented in [docs/architecture.md](docs/architecture.md).

## Four operating modes

| Mode | Best for | Behavior |
| --- | --- | --- |
| `fast` | Small, obvious changes | Skip planning and model review |
| `budget` | Large mechanical edits | Cheapest capable route; review hard tasks |
| `balanced` | Everyday development | Strong plan, efficient implementation, independent review |
| `quality` | Architecture and high-risk work | Frontier planning and stronger review |

```bash
lea run -m fast "Rename this field"
lea run -m balanced --budget 2usd "Add OAuth login"
lea run -m quality "Review the concurrency design"
```

## Live steering and interruption

LEA keeps the input box available while a turn is running:

| Action | Key |
| --- | --- |
| Send, or queue while busy | `Enter` |
| Interrupt the current turn and prioritize the new message | `Ctrl+S`, `Ctrl+Enter`, or `Alt+Enter` |
| Interrupt without sending another message | `Esc` or `Ctrl+C` |
| Insert a newline | `Ctrl+J` |
| Revert files changed by the last turn | `/undo` |

Cancellation propagates to streaming model connections, rate-limit waits, and local
commands. Provider-side usage generated before cancellation may still be billed.

## Provider routing

LEA uses only providers for which you supplied a key. Native APIs are preferred;
OpenRouter can be used as a fallback transport.

| Provider | Typical role |
| --- | --- |
| xAI | Routing, research, planning, general coding |
| Anthropic | Planning and independent review |
| OpenAI | Terminal-heavy coding and review |
| Google Gemini | UI design and frontend implementation |
| DeepSeek | Cost-efficient implementation and fixes |
| Moonshot / Kimi | Long-context planning and coding |
| Alibaba / Qwen | Budget coding, planning, and review |

Model prices and capabilities live in one auditable catalog:
[`agentflow/catalog.py`](agentflow/catalog.py). Pin a preferred model with:

```bash
lea models
lea use code deepseek-v4-pro
lea use review claude-sonnet-5
```

## Workspace safety

LEA automatically permits normal file and shell operations inside the selected
workspace. Paths outside it are denied unless explicitly allowlisted. Obviously
destructive system commands are always blocked.

```bash
lea allow list
lea allow add /path/to/shared-library
```

Run LEA in a Git repository whenever possible. `/diff` shows the current patch and
`/undo` restores files touched by the previous turn.

## Configuration

Add `agentflow.yaml` to a project root:

```yaml
mode: balanced
max_cost_usd: 3.0
max_code_review_rounds: 2
human_trial: false
shell_policy: allow
currency: cny
```

See [agentflow.yaml](agentflow.yaml) for every setting and `.env.example` for all
supported provider variables.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers routing, budget enforcement, provider compatibility,
interrupts, workspace boundaries, skills, and the interactive composer.

## Roadmap

- [ ] Per-stage budget reservations and route explanations
- [ ] Recorded terminal demo and benchmark suite
- [ ] Linux/macOS native installer
- [ ] Local-model transport through Ollama
- [ ] MCP tool-server support
- [ ] Signed releases and PyPI trusted publishing

Have an idea? Start a [discussion](https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/discussions)
or read [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).

# LEA launch materials

Prepared 2026-09-05. These drafts have not been posted. The maintainer should approve
the text and choose the publishing account before anyone sends them externally.

## Chinese project introduction

Suggested venue: V2EX's [分享创造](https://www.v2ex.com/go/create) node, or the
maintainer's own Chinese developer channel.

Title: LEA：按 API 预算分配规划、编程和审核模型的开源 Agent

LEA 是一个本地运行的编程 Agent，想解决的问题是：如果一次任务只有几毛钱或几块钱
的 API 预算，规划、实现和审核应该怎样分配给不同模型？

它按阶段选择模型，默认倾向于把推理能力用于规划，把高 token 用量的实现交给低成本
模型，再尽可能选择另一家供应商进行审核。你可以指定预算，也可以固定某个角色的模型。
实际路线取决于已配置的供应商、任务和预算。

项目：https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent

不用安装就能试的成本计算器：
https://charlesenchine-arch.github.io/Light-weight-Ensemble-Agent/

计算器允许切换场景和单模型基线，也会显示 LEA 更贵的情况。它使用固定 token 假设，
预算输入只计算能覆盖几次固定路线，不会执行 Agent 或根据预算重新选模型。

安装后可以先看路线，再决定是否调用 API：

```bash
lea init
# 在项目的 .env 中配置你使用的供应商 API Key
lea route --budget 1usd "Add pagination to the users API"
lea run --budget 1usd "Add pagination to the users API"
```

`lea route` 不调用模型；`lea run` 会调用模型并可能修改项目文件，适合先在有版本管理
的小项目中试用。运行中可以继续输入：Enter 排队，Ctrl+S 打断并优先执行新消息，
Esc 只打断。也支持 Ollama 本地模型和明确授权的 stdio MCP 工具。

目前是早期版本。仓库里的成本基准不测任务完成质量，README 动图也只是功能示意。
取消请求不能撤销供应商已经产生的费用；本地模型的硬件、电费不计入 API 账本。

最希望收到两类反馈：你用哪些供应商、什么预算完成了什么任务；或者在哪一步停住了，
比如安装、模型选择、工具调用、打断。这样能用实际案例改进调度策略。

安装说明：https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/blob/main/docs/install.md

## English introduction for an owned channel

Title: LEA: a coding agent that allocates models around an API budget

LEA is an open-source, local coding agent built around a question: how should a small
API budget be divided between planning, implementation, and review?

It selects a model for each stage, checks estimated affordability before each model
request, and prefers a different provider for review when one is available. The route
depends on your configured providers, task, and budget. You can also pin role models,
use Ollama locally, and connect explicitly trusted stdio MCP tools.

Repository: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent

Try the cost calculator without an account or API key:
https://charlesenchine-arch.github.io/Light-weight-Ensemble-Agent/

The calculator compares fixed token assumptions across four scenarios. Choose a
cheaper baseline and it will show when LEA costs more. The budget input counts how many
fixed routes fit; it does not run an agent or recalculate model selection.

After installation and provider configuration, `lea route --budget 1usd "Add pagination
to the users API"` previews your route without calling a model. `lea run` executes it.
The interactive shell accepts follow-ups while a turn runs: Enter queues them, Ctrl+S
interrupts and prioritizes the new message, and Esc interrupts without submitting.

This is early-stage software. The published benchmark estimates catalog cost, not
coding quality, and the README animation is an illustration rather than a live
recording. Cancellation cannot undo provider charges already incurred. Local hardware
and power costs are outside the hosted API ledger.

Concrete reports are especially useful: the task, configured providers, budget,
whether the result passed your tests, and where the workflow got stuck. Please leave
API keys and private code out of reports.

Install: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/blob/main/docs/install.md

## Hacker News: maintainer-written submission only

The [HN guidelines](https://news.ycombinator.com/newsguidelines.html) prohibit generated
or AI-edited text. Do not paste either draft above into HN, or use it as an AI-written
comment there. The maintainer needs to write the submission and discussion personally.

The [Show HN guidelines](https://news.ycombinator.com/showhn.html) call for work people
can try, explain, and discuss with its maker. Link to the working repository; the
calculator can be a secondary example. A landing page alone is not the product.
Do not solicit votes or coordinate supportive comments.

Facts available for the maintainer's own writing:

- The intended problem is model allocation under a user-specified API budget.
- The actual agent is a Python 3.11+ CLI under Apache-2.0.
- Budget fitting, request guards, live steering, local models, and MCP are separate
  capabilities. Avoid presenting the price calculator as an agent run.
- Personal motivation, actual usage stories, and live quality results need to come
  from the maintainer. No such story is supplied or invented here.

## Evidence and boundaries

| Claim | Inspect or reproduce | Boundary |
| --- | --- | --- |
| Catalog cost comparison | `lea benchmark --json`; [method](../benchmarks/README.md) | Fixed role token counts, all hosted providers assumed available; no quality evaluation |
| Route preview | `lea route --budget 1usd "Add pagination to the users API"` | Uses configured providers and local classification; does not prove an actual run will finish |
| Budget checks | [architecture](architecture.md), `tests/test_budget_money.py`, `tests/test_workflow.py` | Estimates depend on prices and usage; not an invoice guarantee |
| Follow-ups and interruption | [Chinese usage guide](README.zh-CN.md#连续对话和中断), `tests/test_turn_queue.py`, `tests/test_composer.py`, `tests/test_retry.py` | Automated cancellation coverage is not a live provider recording |
| Local models | [architecture](architecture.md#model-independence), `tests/test_ollama.py` | Zero hosted token price does not imply zero total cost |
| MCP | [MCP guide](mcp.md), `tests/test_mcp.py` | Optional dependency, explicit trust; third-party servers are not sandboxed |
| Installation | [installer guide](install.md), pinned [v0.3.0 release](https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/releases/tag/v0.3.0) | GitHub wheel install; do not advertise `pip install lea-agent` before PyPI publication |
| Demonstration | [open recording task](https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/issues/6) | Existing GIF is drawn; the requested live recording is still outstanding |

## First launch and evaluation

The [V2EX FAQ](https://www.v2ex.com/faq) welcomes new works and discourages repetitive
link promotion. Start with one substantive post in an appropriate community, with the
maintainer available to answer questions. Confirm the venue's current rules before posting.

Record the actual post URL and publication time after posting; there are no external
launch URLs yet. Before the launch, capture GitHub stars, forks, traffic, and release
download counts. Record validation downloads separately from user downloads.

At 24 hours and seven days, compare those measures and group feedback into installation,
routing, task quality, cost, and interruption. GitHub traffic alone cannot reliably
attribute stars to a particular post. A star increase is evidence of interest; reports
of completed tasks provide stronger evidence of usefulness.

If readers visit but cannot install, fix the first-run problem before another launch.
If installs work but results fail, publish the failing fixture and improve the agent.
If there is little exposure, revise the explanation using real feedback before choosing
another relevant venue. Avoid identical repeat posts and invented testimonials.

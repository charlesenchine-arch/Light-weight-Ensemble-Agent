# Architecture

LEA is a synchronous, local-first agent runtime with a persistent interactive shell.
Its core design goal is to maximize useful work per unit of model spend while keeping
the routing decision visible and overridable.

## Runtime path

1. **Classify locally.** A deterministic classifier derives intent, complexity, and
   domains. Quality mode can opt into LLM classification.
2. **Fit the budget.** The budget planner selects an operating mode and may remove
   optional design, review, or skill-harvesting stages.
3. **Build the route.** Each role is matched against reachable models, requested
   strengths, model pins, health, and cross-provider review constraints.
4. **Run the role loop.** The selected model receives a role-specific system prompt,
   a compact workspace snapshot, relevant artifacts, and the minimum tool set.
5. **Review and fix.** Blocking review findings trigger a targeted fix role followed
   by another independent review, up to the configured limit.
6. **Record evidence.** Tokens, estimated cost, models, artifacts, touched files, and
   loaded skills are written to `.agentflow/sessions/`.

## Budget enforcement

Budgeting happens at two levels:

- **Route fitting** uses typical stage token counts and catalog prices to decide which
  workflow is affordable.
- **Request guarding** serializes the real prompt and tool schemas, estimates input
  tokens conservatively from UTF-8 bytes, and derives the maximum affordable output
  from the selected model price and remaining ledger balance.

If fewer than 256 useful output tokens can be funded, LEA does not send the request.
The catalog is deliberately centralized in `agentflow/catalog.py` so price changes
are reviewable.

## Model independence

All providers return the same internal `ChatResult` and `Usage` types. Native provider
credentials are preferred, while OpenRouter can transport catalog models that declare
an OpenRouter identifier.

Ollama is an opt-in OpenAI-compatible local transport. The configured local model is
eligible for every text role and has zero hosted API token price in the ledger. This
does not mean zero total cost: hardware, power, and remote Ollama hosting remain outside
LEA's API budget model.

The reviewer avoids the coding model and then the coding provider whenever another
reachable option exists. This is an error-diversity measure, not a claim that model
agreement proves correctness.

## Tools and workspace boundary

Agents receive one of three tool levels: `none`, `read`, or `all`. Every path is
resolved through `Workspace` and `Policy`; escaping the workspace or an explicit
allowlisted root is rejected. Shell commands pass through the same policy before a
process is created.

Write and edit tools retain an in-memory before-image for `/undo`. This is a convenience
feature, not a replacement for Git.

## Cancellation

The interactive prompt runs separately from the active turn. A normal message can be
queued; a steered message is inserted at the front and raises the shared cancellation
signal. Registered HTTP clients are closed, retry waits wake, and spawned commands are
terminated. The next turn clears the cancellation signal only after the previous worker
has released the queue lock.

## Extension points

- Add models and prices in `agentflow/catalog.py`.
- Add OpenAI-compatible base URLs in `agentflow/providers/openai_compat.py`.
- Add role prompts in `agentflow/agent/prompts.py`.
- Add guarded tools in `agentflow/tools.py`.
- Add routing policy in `agentflow/router.py` and `agentflow/budget.py`.

Any new provider or tool should include unit tests that do not require live credentials.

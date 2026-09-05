# Contributing to LEA

Thanks for helping make cost-aware coding agents practical.

## Before opening a change

- Search existing issues and discussions first.
- For a large feature or provider integration, open an issue describing the use case,
  expected behavior, and budget implications.
- Keep provider-specific behavior behind the common `ChatResult` interface.
- Never include API keys, local `.env` files, or captured private prompts.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
ruff check agentflow tests
python -m build
```

## Pull requests

A good pull request:

1. Explains the user-facing problem and why the change belongs in LEA.
2. Includes tests for routing, cost, policy, or provider behavior as appropriate.
3. Updates the English and Chinese docs when commands or key behavior change.
4. Avoids unrelated formatting or refactors.
5. Reports the commands used to verify the change.

Model catalog updates should cite the provider pricing page and date in the pull request.
Do not silently replace model IDs or prices.

For project introductions, see the [launch drafts and evidence notes](docs/launch.md).
They distinguish verified behavior from estimates and identify channel-specific rules.

## Design principles

- Budget is a constraint, not just a dashboard number.
- Expensive reasoning belongs at high-leverage decision points.
- Review should introduce model and provider diversity.
- Local actions stay inside a clear workspace boundary.
- Users must be able to inspect, interrupt, and override the route.

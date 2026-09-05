# Changelog

All notable changes to this project will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and releases use semantic
versioning.

## [Unreleased]

### Fixed

- Corrected the cost lab's illustrated stage prices to match its backend benchmark,
  and clarified fixed-route budget calculations and the README animation's provenance.

### Added

- A no-tracking, interactive GitHub Pages cost lab generated from the same
  deterministic model catalog as `lea benchmark`.
- Checksum-verified, one-command installers for macOS, Linux, and Windows using
  isolated `uv` tool environments.

## [0.3.0] - 2026-09-05

### Added

- A compact, reproducible terminal walkthrough for the README and social sharing.
- Optional stdio MCP tools with explicit tool selection, per-workspace configuration
  trust, budget-aware schemas, bounded results, and cancellation.
- A tokenless, approval-gated PyPI trusted-publishing workflow.

## [0.2.0] - 2026-09-04

### Added

- Opt-in Ollama transport for local implementation and fixes with zero hosted API
  token cost.

## [0.1.1] - 2026-09-04

### Added

- Machine-readable `lea models --json` catalog with official pricing sources and
  verification dates.
- Machine-readable `lea route --budget ... --json` reports for CI and editor tooling.
- Gemini 3.8 Flash as the current Google coding and design default.

### Changed

- Migrated default routes away from retired xAI aliases and corrected their redirect
  pricing for historical ledgers.
- Updated OpenAI GPT-5.6 pricing and context windows, plus current DeepSeek and Qwen
  cache pricing.

## [0.1.0] - 2026-09-04

### Added

- Cost-aware model routing across planning, design, implementation, review, and fixes.
- Pre-request budget guard that limits model output before a call is sent.
- Independent review routing with targeted fix rounds.
- Live steering that can interrupt model connections, retry waits, and local commands.
- Multi-provider support for xAI, Anthropic, OpenAI, Gemini, DeepSeek, Kimi, Qwen, and
  OpenRouter.
- Workspace boundary policy, reversible file edits, session ledgers, and reusable skills.

[Unreleased]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/releases/tag/v0.1.0

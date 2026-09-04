# Changelog

All notable changes to this project will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and releases use semantic
versioning.

## [Unreleased]

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

[Unreleased]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/releases/tag/v0.1.0

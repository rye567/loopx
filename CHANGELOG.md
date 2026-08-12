# Changelog

All notable changes to LoopX are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Repair write-lock deadlock**: `can-write --kind business` rejected writes whenever any stage was `CHANGES_REQUIRED`, including the stage the developer was supposed to fix — the repair path deadlocked itself. Now a `CHANGES_REQUIRED` stage no longer locks business writes when the run is at `development` with an open repair ticket whose `return_to=development` (and solution/test reviews are satisfied). `BLOCKED` still always locks writes, and ticket-less `CHANGES_REQUIRED` still blocks out-of-band writes.
- `workflow.md` write-protection section documents the repair-write contract.

## [0.1.0] - 2026-08-07

First public release of the cross-tool quality gate skill package for Codex and Claude Code.

### Added

- Stage-based workflow from requirement intake through release readiness, with shared `loopx/` skill source.
- Local controller (`loopx/tools/loopx_controller*.py`) persisting run state under `docs/loopx/runs/<run_id>/`.
- Strict validation (`validate --strict`, `gate`) over state, worklist, stage results and required artifacts.
- Human confirmation gates for requirement interview and solution review (`NEED_HUMAN` -> `confirm-stage` -> `PASS`).
- Risk-based mode selection (LIGHT / STANDARD / FULL) driven by `risk.yml`.
- Repair loop: `fail-review` / `claim-stage` / `close-repair` with per-stage auto-repair limit (`max_auto_repair`, default 2) that blocks the stage on exhaustion.
- Legal SKIPPED stages for LIGHT mode via `MODE_SKIPPABLE_STAGES` (single source of truth in `loopx_controller_contracts.py`); STANDARD/FULL reject SKIPPED.
- Compound Capture: record reusable learnings or skip decisions before close.
- Optional provider hooks (`before_init`, `after_stage`, `before_close`) with an integration result contract.
- JSON schemas for state, stage results, tracking, mode selection, specs, and interviews.
- Package harness check (`loopx_check.py package`) and project harness check (`loopx_check.py project`).
- 71 regression tests across controller, skill package, and standardization.

### Changed

- `cmd_next` and `cmd_advance` unified behind a single advancement path; `advance` now keeps the worklist `current_stage` in sync with `state.json`.
- `fail-review` counts repair attempts per stage instead of per item.
- Removed dead state fields (`confirmation_policy`, `transition_policy`, `interview.required/can_skip/mode`, `spec.required`, `tracking.show_on_every_update`) and their schemas.
- Consolidated duplicate helpers (`yaml_string`, `slugify`) into single sources.
- `workflow.md` and `SKILL.md` de-duplicated; SKIPPED rules documented with a single source of truth.

### Fixed

- `SKIPPED` could be recorded but never allowed advancement (documented contract was a dead letter).
- `max_auto_repair` was declared but never enforced; the 3rd auto repair failure now records `BLOCKED`.
- `spec.gate_result` schema did not accept `SKIPPED`, failing strict validation after a legal skip.
- `final_report` close check required `release_readiness PASS`, deadlocking LIGHT runs that legally skip it.
- `cmd_mode` and `can-write` rejected legal SKIPPED review gates in LIGHT mode.
- `fail-review` left `worklist.stages` out of sync with `state.stages`.
- `close-repair` now resets the stage repair counter so a fixed stage can retry with a fresh limit.

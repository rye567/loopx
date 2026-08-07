# LoopX v0.1.0 Release Notes

LoopX v0.1.0 is the first public release of the cross-tool quality gate skill package for Codex and Claude Code.

## Highlights

- Shared `loopx/` skill source for Codex and Claude Code.
- Stage-based workflow from requirement intake through release readiness.
- Local controller for persistent run state under `docs/loopx/runs/<run_id>/`.
- Strict validation (`validate --strict`, `gate`) with human confirmation gates for interview and solution review.
- Risk-based mode selection (LIGHT / STANDARD / FULL); LIGHT mode supports legal SKIPPED review gates via `MODE_SKIPPABLE_STAGES`.
- Repair loop with per-stage auto-repair limit: the 3rd failed auto repair records `BLOCKED`.
- JSON schemas for state, stage results, tracking, mode selection, specs, and interviews.
- Role instructions for requirement, design, review, testing, implementation, validation, and release stages.
- Templates for staged artifacts and final reports.
- 71 regression tests for the controller and package structure.

## Install

Plugin marketplace (recommended):

```bash
plugin marketplace add https://github.com/rye567/loopx
plugin install loopx
```

Manual:

```bash
git clone git@github.com:rye567/loopx.git
cd loopx
ln -s "$PWD/loopx" "$HOME/.claude/skills/loopx"
ln -s "$PWD/loopx" "$HOME/.codex/skills/loopx"
```

## Suggested Announcement

```text
I built LoopX: quality gates for AI coding agents.

It is a Codex / Claude Code skill package that forces risky AI coding work through requirement interview, spec, review gates, test design, implementation, validation, and release readiness before claiming done.

Useful when agents touch API contracts, permissions, tenant boundaries, state machines, SQL/MQ flows, or cross-module changes.

Repo: https://github.com/rye567/loopx
```

## Suggested GitHub Topics

`codex`, `claude-code`, `ai-agents`, `agent-workflow`, `quality-gate`, `developer-tools`, `automation`, `python`, `prompt-engineering`

# LoopX Kit v0.1.0 Release Notes

LoopX Kit v0.1.0 is the first public release of the cross-tool quality gate skill package for Codex and Claude Code.

## Highlights

- Shared `loopx/` skill source for Codex and Claude Code.
- Stage-based workflow from requirement intake through release readiness.
- Local controller for persistent run state under `docs/loopx/runs/<run_id>/`.
- JSON schemas for state, stage results, tracking, mode selection, specs, and interviews.
- Role instructions for requirement, design, review, testing, implementation, validation, and release stages.
- Templates for staged artifacts and final reports.
- Regression tests for the controller and package structure.

## Install

```bash
git clone git@github.com:rye567/loopx-kit.git
cd loopx-kit
```

Link or copy `loopx/` into your tool skills directory as `loopx`.

## Suggested Announcement

```text
I built LoopX: quality gates for AI coding agents.

It is a Codex / Claude Code skill package that forces risky AI coding work through requirement interview, spec, review gates, test design, implementation, validation, and release readiness before claiming done.

Useful when agents touch API contracts, permissions, tenant boundaries, state machines, SQL/MQ flows, or cross-module changes.

Repo: https://github.com/rye567/loopx-kit
```

## Suggested GitHub Topics

`codex`, `claude-code`, `ai-agents`, `agent-workflow`, `quality-gate`, `developer-tools`, `automation`, `python`, `prompt-engineering`

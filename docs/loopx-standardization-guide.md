# LoopX Agent / Skill / Harness Standardization Guide

This guide maps LoopX into a production-style delivery track.

## Core Model

```text
Standards = rules and pass criteria
Skills    = reusable capabilities
Agents    = stage owners
Harness   = objective checks and evidence gates
Controller = state and progression owner
```

## Recommended Stage Track

```text
Requirement Intake
  -> Environment Check
  -> Project Assignment
  -> Solution Design
  -> Solution Review
  -> Test Design
  -> Test Review
  -> Development
  -> Quality Audit
  -> Code Review
  -> Test Execution
  -> Health Gate
  -> Release Readiness
  -> Final Report
```

## Minimal Production Loop

Start with a small loop before adding more agents:

1. Requirement Manager produces testable scope.
2. Solution Designer produces bounded write scope.
3. Test Designer maps acceptance criteria to test cases.
4. Development Orchestrator implements only approved scope.
5. Quality Gate Auditor checks evidence, worklist and stage results.
6. Release Manager prepares rollback, monitoring and approval evidence.

## Gate Discipline

Every gate must return one of:

- `PASS`
- `CHANGES_REQUIRED`
- `BLOCKED`
- `SKIPPED`
- `ACCEPTED_RISK`

Every non-pass result needs a `return_to` stage and required actions. This keeps multi-agent collaboration from becoming untraceable conversation.

## Harness Strategy

Use `python loopx/tools/loopx_check.py kit --root .` inside this repository to verify the LoopX kit assets.

Use `python ~/.loopx/tools/loopx_check.py project --root <project>` in a target project to check local LoopX run structure and common delivery evidence.

The harness intentionally uses only Python standard library so it can run before third-party tooling is installed.

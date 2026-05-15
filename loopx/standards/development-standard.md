# Development Standard

## Purpose

Keep implementation minimal, reviewable and aligned with approved requirements and design.

## Required Inputs

- Passed requirement artifact.
- Passed design artifact or explicit `LIGHT` plan.
- Passed test design artifact, unless the run is explicitly `LIGHT` and the skipped gate is documented.
- Project harness, module discovery and write scope.

## Implementation Rules

- Make the smallest change that satisfies the accepted scope.
- Preserve existing user changes; never revert unrelated work without approval.
- Respect module boundaries, API contracts and project-specific style.
- Do not introduce new frameworks, services or broad refactors without a design gate.
- Do not weaken assertions, delete tests, swallow exceptions or hide failures to pass a gate.
- Keep secrets, tenant ids, production endpoints and credentials out of code and logs.
- Prefer explicit error handling and observable failure signals over silent fallback.

## Write Scope Contract

Every development task must declare:

```yaml
write_scope:
  allowed_paths: []
  forbidden_paths: []
  expected_files: []
  concurrency_conflicts: []
```

If the required change exceeds `allowed_paths`, the agent must stop and return to design or project assignment.

## Pass Criteria

- Diff is limited to the approved scope.
- Implementation maps to acceptance criteria and worklist items.
- Tests are added or updated for changed behavior.
- Validation commands are run or marked as environment-blocked with evidence.
- Remaining risks are explicit and not hidden in generic language.

## Fail / Return Rules

- Scope expansion: return to solution design.
- Missing tests: return to development or test design, based on cause.
- Build/test failure: stay in development unless the evidence shows environment blockage.
- Unknown module boundary: return to project assignment.

## Evidence

Record changed files, commands run, command outputs or failure summaries, and mapping from acceptance criteria to code/test changes.

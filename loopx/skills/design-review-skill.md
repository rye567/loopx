# Design Review Skill

## Purpose

Review a proposed solution before implementation begins.

## Inputs

- Requirement artifact.
- Solution design artifact.
- Project harness.
- Risk and quality standards.

## Procedure

1. Check requirement-to-design coverage.
2. Check module boundaries, write scope and dependency impact.
3. Check testability and validation feasibility.
4. Check security, permission, data, compatibility and rollback risks.
5. Produce an explicit gate result and return target.

## Output

```yaml
result: PASS|CHANGES_REQUIRED|BLOCKED|SKIPPED|ACCEPTED_RISK
blocking_issues: []
non_blocking_issues: []
required_actions: []
return_to: solution_design
next_action: test_design
```

## Pass Criteria

- No unresolved blocking issues.
- Design covers acceptance criteria.
- Validation plan can produce evidence.
- Write scope is bounded.

## Failure Handling

`CHANGES_REQUIRED` returns to solution design. `BLOCKED` waits for user or environment decision.

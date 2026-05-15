# Quality Standard

## Purpose

Define objective gates that stop weak or incomplete agent output before the next stage.

## Gate Result Contract

Every gate returns exactly one of:

- `PASS`
- `CHANGES_REQUIRED`
- `BLOCKED`
- `SKIPPED`
- `ACCEPTED_RISK`

Every non-pass result must include:

```yaml
return_to: ""
blocking_issues: []
required_actions: []
evidence: []
user_confirmation_required: false
```

## Core Checks

- Required artifacts exist for the selected mode.
- Worklist items are resolved or intentionally blocked.
- Stage result has valid status, return target, next action and evidence.
- Implementation diff matches approved write scope.
- Test evidence maps back to acceptance criteria.
- Cleanup is verified for data created during tests.
- CI or remote validation gaps are declared.

## Code Quality Defaults

Projects may override these defaults in their project harness.

- Large file warning: source file over 500 lines.
- Large function warning: function or method over 60 lines.
- No committed debug prints, temporary sleeps or test-only backdoors.
- No hard-coded secrets, tokens, tenant ids, passwords or production endpoints.
- No broad dependency additions without design approval.

## Pass Criteria

A quality gate passes only when there is hard evidence for required checks. LLM review text alone is not sufficient proof.

## Fail / Return Rules

- Requirement gap: return to requirement stage or block for clarification.
- Design gap: return to solution design.
- Test design gap: return to test design.
- Implementation gap: return to development.
- Validation gap: return to test execution or Health Gate.

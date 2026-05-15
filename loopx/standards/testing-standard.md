# Testing Standard

## Purpose

Make testing executable, reproducible and tied to acceptance criteria.

## Required Inputs

- Requirement artifact with acceptance criteria.
- Design artifact with interfaces, data flow and risks.
- Project profile with available validation commands.
- Environment limits and dependency availability.

## Test Case Contract

Each test case must include:

```yaml
id: TC-001
covers: []
risk_tags: []
preconditions: []
data_setup:
  run_id_strategy: ""
  records: []
execution:
  command_or_entrypoint: ""
  steps: []
assertions: []
cleanup:
  steps: []
  verification: []
expected_result: ""
```

## Required Coverage

- Happy path.
- Boundary values.
- Invalid input and failure path.
- Permission, tenant or ownership checks when relevant.
- Regression checks around changed contracts.
- Cleanup verification for created test data.

## Pass Criteria

- Every acceptance criterion maps to one or more test cases.
- Tests include data setup, execution entrypoint, assertions, cleanup and cleanup verification.
- Environment gaps are separated from product failures.
- Manual verification is marked as manual and not counted as automated proof.
- CI-only checks are explicitly marked `CI_REQUIRED`.

## Fail / Return Rules

- Missing acceptance criterion mapping: return to test design.
- Missing cleanup verification: return to test design.
- Test cannot run due environment: mark `BLOCKED` or `CI_REQUIRED`, not `PASS`.
- Product defect discovered: return to development.

## Evidence

Record test case file, executed commands, result status, relevant output summary and cleanup verification result.

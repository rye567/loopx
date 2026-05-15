# Test Design Skill

## Purpose

Design executable test cases that prove acceptance criteria and risk mitigations.

## Inputs

- Requirement artifact.
- Solution design artifact.
- Testing standard.
- Project profile commands and environment constraints.

## Procedure

1. Map every acceptance criterion to test cases.
2. Add boundary, invalid, permission and regression cases where relevant.
3. Define data setup with unique `runId` or prefix.
4. Define execution entrypoint and commands.
5. Define assertions, cleanup steps and cleanup verification.
6. Mark local, CI-required and manual checks separately.

## Output

- Test case artifact.
- Coverage matrix.
- Environment gaps.
- `stage_result` evidence.

## Pass Criteria

- No acceptance criterion is unmapped.
- Each test has setup, execution, assertions, cleanup and cleanup verification.
- CI-required checks are explicit and not counted as local pass.

## Failure Handling

Return to requirement or solution design when criteria are untestable. Return to test design for missing coverage or cleanup.

# Quality Scan Skill

## Purpose

Convert review expectations into objective checks that can stop unsafe progression.

## Inputs

- Stage artifacts.
- Worklist.
- Changed files or planned write scope.
- Test and validation evidence.
- Quality standard and project harness.

## Procedure

1. Verify required artifacts for the selected mode.
2. Verify stage results use allowed statuses and return targets.
3. Verify worklist items are resolved, blocked or accepted by the user.
4. Compare diff against write scope.
5. Check evidence for build/test/cleanup/CI gaps.
6. Flag forbidden implementation patterns and missing proof.

## Output

- Quality report.
- Gate result.
- Required actions with `return_to` target.

## Pass Criteria

- Required evidence exists.
- No unresolved worklist item is hidden.
- No required local validation is missing.
- CI gaps are declared.

## Failure Handling

Return to the owning stage: requirement, design, test design, development, test execution or Health Gate.

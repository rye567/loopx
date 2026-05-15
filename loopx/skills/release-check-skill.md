# Release Check Skill

## Purpose

Prepare release evidence without performing unsafe publishing actions automatically.

## Inputs

- Passed quality report.
- Test report.
- Changed file summary.
- Release standard.
- Project deployment or CI conventions when available.

## Procedure

1. Identify config, database, compatibility and external dependency changes.
2. Define deploy and rollback steps.
3. Define monitoring and observation points.
4. Separate local validation, CI-required validation and manual verification.
5. Require human approval for commit, push, deployment or production-impacting actions.

## Output

- Release readiness artifact.
- Residual risk list.
- Human approval requirement.

## Pass Criteria

- Rollback and observation are defined or not applicable with reason.
- Validation gaps are not hidden.
- Release actions do not execute without explicit approval.

## Failure Handling

Return to solution design for missing impact analysis, test execution for missing evidence, or block for human decision.

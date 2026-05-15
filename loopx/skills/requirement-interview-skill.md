# Requirement Interview Skill

## Purpose

Convert a fuzzy request into a requirement artifact that can pass `requirement-standard.md`.

## Inputs

- User request.
- Existing issue, README, project harness or context if available.
- Known constraints and non-goals.

## Procedure

1. Identify actor, workflow, current problem and desired result.
2. Separate scope from non-scope.
3. Convert expected behavior into testable acceptance criteria.
4. Detect ambiguity using risk tags such as `ambiguous_requirement`, `api_contract`, `auth`, `tenant_scope`, `db_schema`, `external_side_effect`.
5. Produce open questions only when the answer changes scope, risk or acceptance criteria.

## Output

- Requirement artifact.
- Risk tags.
- Suggested mode: `LIGHT`, `STANDARD` or `FULL`.
- `stage_result` with evidence and next action.

## Pass Criteria

- Acceptance criteria are observable.
- Scope and out-of-scope are both explicit.
- Open questions are empty or intentionally blocking.
- Risk tags are sufficient for mode selection.

## Failure Handling

Return `CHANGES_REQUIRED` when the artifact can be repaired by asking or rewriting. Return `BLOCKED` when a human decision is required.

# Requirement Standard

## Purpose

Make every user request executable before design, code or test work begins.

## Required Inputs

- User request or issue description.
- Target project and module, if known.
- Known business goal, user role or workflow.
- Constraints, deadlines, dependencies or non-goals already stated by the user.

## Required Output

A requirement artifact must include:

| Field | Requirement |
| --- | --- |
| `id` | Stable requirement id, for example `REQ-20260515-001`. |
| `title` | Short action-oriented title. |
| `background` | Why this change is needed. |
| `users` | Who uses or is affected by it. |
| `problem` | Current pain, defect or missing capability. |
| `goals` | Desired observable outcomes. |
| `in_scope` | What will be changed. |
| `out_of_scope` | What will not be changed. |
| `acceptance_criteria` | Verifiable criteria written as observable behavior. |
| `edge_cases` | Boundary, empty, invalid, concurrency or permission cases. |
| `non_functional_requirements` | Performance, security, compatibility, observability and reliability needs. |
| `risks` | Requirement ambiguity, data, security, integration and release risks. |
| `dependencies` | Systems, teams, configs, data or tools needed. |
| `open_questions` | Anything that must be clarified before the next gate. |

## Pass Criteria

A requirement gate can pass only when:

- Acceptance criteria are testable without interpreting intent.
- Scope and non-scope are both explicit.
- The affected user or workflow is named.
- Edge cases and failure paths are listed or intentionally marked not applicable.
- Open questions are empty, non-blocking, or assigned to `NEED_HUMAN`.
- Risk tags are available for mode selection: `LIGHT`, `STANDARD` or `FULL`.

## Fail / Return Rules

- Missing user goal: return to requirement interview.
- Missing acceptance criteria: return to acceptance criteria drafting.
- Ambiguous scope: return to scope boundary analysis.
- Security, permission, data migration or external side effect uncertainty: block or upgrade to `FULL`.

## Evidence

The agent must write the requirement artifact path, unresolved questions, selected risk tags and gate result into the stage result.

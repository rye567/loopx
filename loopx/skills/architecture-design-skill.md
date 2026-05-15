# Architecture Design Skill

## Purpose

Create a minimal technical plan that maps requirement criteria to implementation boundaries.

## Inputs

- Passed requirement artifact.
- Project discovery result.
- Project harness and development standard.
- Risk tags and selected mode.

## Procedure

1. Identify affected modules, contracts, data, configs and dependencies.
2. Describe the target behavior and data/control flow.
3. Define write scope and read scope.
4. List alternatives considered for non-trivial changes.
5. Define compatibility, rollback, observability and validation strategy.
6. Tie each design decision back to acceptance criteria or risk tags.

## Output

- Solution design artifact.
- Write scope contract.
- Validation plan.
- Residual risks and assumptions.

## Pass Criteria

- Impact scope is explicit.
- The plan is implementable with available project tools.
- Risks have mitigations or are escalated.
- Test strategy is specific enough for test design.

## Failure Handling

Return to requirement interview for missing scope; return to project discovery for unknown module boundaries; block for unapproved high-risk changes.

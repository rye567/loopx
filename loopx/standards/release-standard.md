# Release Standard

## Purpose

Ensure finished work can be safely shipped, rolled back and observed.

## Required Inputs

- Passed quality gate.
- Passed test execution or documented CI requirement.
- Final diff summary.
- Known environment, config, data and operational impacts.

## Release Readiness Contract

```yaml
release:
  id: REL-YYYYMMDD-001
  requirement_id: ""
  risk_level: LIGHT|STANDARD|FULL
  changed_files: []
  config_changes: []
  database_changes: []
  compatibility_notes: []
  deploy_steps: []
  rollback_plan: []
  monitoring:
    metrics: []
    logs: []
    alerts: []
  validation:
    local: []
    ci_required: []
    manual: []
  residual_risks: []
```

## Pass Criteria

- Rollback path is defined or explicitly not applicable.
- Config, database and compatibility impacts are declared.
- Monitoring or observation points are listed for non-trivial changes.
- Local versus CI coverage is clearly separated.
- Human approval is required for release, push or production-impacting steps.

## Fail / Return Rules

- No rollback plan for risky change: return to release planning.
- Undeclared config/data impact: return to solution design.
- Missing validation evidence: return to test execution or Health Gate.
- Unaccepted residual risk: block for human decision.

# 11 Release Readiness

## Release Identity

```yaml
release:
  id: REL-YYYYMMDD-001
  requirement_id: ""
  risk_level: LIGHT|STANDARD|FULL
```

## Change Summary

- Changed files:
- Behavior changed:
- User impact:

## Operational Impact

```yaml
config_changes: []
database_changes: []
api_contract_changes: []
external_dependencies: []
compatibility_notes: []
```

## Validation Coverage

```yaml
local_validation: []
ci_required: []
manual_validation: []
not_covered: []
```

## Rollback Plan

-

## Monitoring / Observation

```yaml
metrics: []
logs: []
alerts: []
post_release_checks: []
```

## Residual Risks

-

## Stage Result

```yaml
stage_result:
  stage: release_readiness
  status: PASS|CHANGES_REQUIRED|BLOCKED|ACCEPTED_RISK
  return_to: release_readiness
  next_action: final_report
  affected_work_items: []
  evidence: []
  user_confirmation_required: true
  blocked_reason: ""
```

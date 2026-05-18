# 11 发布就绪

## 发布标识

```yaml
release:
  id: REL-YYYYMMDD-001
  requirement_id: ""
  risk_level: LIGHT|STANDARD|FULL
```

## 变更摘要

- 变更文件：
- 行为变化：
- 用户影响：

## 运行影响

```yaml
config_changes: []
database_changes: []
api_contract_changes: []
external_dependencies: []
compatibility_notes: []
```

## 验证覆盖

```yaml
local_validation: []
ci_required: []
manual_validation: []
not_covered: []
```

## 回滚计划

-

## 监控 / 观测

```yaml
metrics: []
logs: []
alerts: []
post_release_checks: []
```

## 剩余风险

-

## 人工确认

本阶段用于承接测试执行和健康门之后的最终人工采纳确认。agent 判断可发布时记录为 `NEED_HUMAN`；用户确认后通过 `confirm-stage --stage release_readiness` 变为 `PASS`，再进入最终报告。

## 阶段结果

```yaml
stage_result:
  stage: release_readiness
  status: NEED_HUMAN|CHANGES_REQUIRED|BLOCKED|ACCEPTED_RISK
  return_to: release_readiness
  next_action: confirm-stage --stage release_readiness
  affected_work_items: []
  evidence: []
  user_confirmation_required: true
  blocked_reason: ""
```

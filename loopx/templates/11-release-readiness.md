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

## 自动推进

本阶段用于承接测试执行和健康检查之后的发布就绪检查。agent 判断可发布时记录为 `PASS`，自动进入最终报告；高风险发布动作仍须按项目权限单独获得用户确认。

## 阶段结果

```yaml
stage_result:
  stage: release_readiness
  status: PASS|CHANGES_REQUIRED|BLOCKED|ACCEPTED_RISK
  return_to: release_readiness
  next_action: final_report
  affected_work_items: []
  evidence: []
  user_confirmation_required: false
  blocked_reason: ""
```

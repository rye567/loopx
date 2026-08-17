# 发布标准

## 目的

确保完成的工作可以安全发布、回滚和观测。

## 必需输入

- 已通过的质量检查。
- 已通过的测试执行，或记录清楚的 CI 要求。
- 最终 diff 摘要。
- 已知环境、配置、数据和运行影响。

## 发布就绪契约

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

## 通过标准

- 回滚路径已定义，或明确说明不适用。
- 配置、数据库和兼容性影响已声明。
- 非平凡变更列出监控或观测点。
- 本地覆盖与 CI 覆盖清晰分离。
- 健康检查报告区分本地通过、CI 未覆盖、可选跳过和阻塞，不能用汇总结论隐藏未执行项。
- 规则快照、结构化阶段产物和证据路径在发布前仍可复核。
- 发布、push 或生产影响步骤需要人工批准。

## 失败 / 返回规则

- 高风险变更没有回滚计划：返回发布规划。
- 配置/数据影响未声明：返回方案设计。
- 验证证据缺失：返回测试执行或健康检查。
- 剩余风险未被接受：阻塞等待人工决策。

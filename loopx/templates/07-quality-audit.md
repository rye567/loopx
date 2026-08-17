# 07 通用质量审计

- 状态：
- 写入范围检查：
- 阶段证据完整性：
- 工作项状态：
- 适用规则及结果：
- 安全检查结果：
- 性能检查结果：
- 可靠性和可观测性结果：
- 方案/实现/验证一致性：
- 设计缺陷：
- 实现缺陷：
- 验证缺陷：
- 需求阻塞：
- 回退阶段：
- CI 未覆盖：
- 已接受风险及确认记录：
- 结构化产物：`quality-result.schema.json`，按风险补充 `security-result.schema.json` 和 `performance-result.schema.json`
- 下一阶段：

## stage_result

```yaml
stage_result:
  stage: quality_audit
  status:
  return_to:
  next_action:
  affected_work_items: []
  evidence: []
  user_confirmation_required:
  blocked_reason:
```

## 证据

| 类型 | 命令/文件 | 结果 | 说明 |
|---|---|---|---|

# 05 用例审核

- 状态：NEED_HUMAN（agent 审核通过后等待用户确认）
- 覆盖结论：
- 缺口：
- 清理策略审核：
- 剩余风险：
- 回退阶段：
- 下一阶段：

## stage_result

```yaml
stage_result:
  stage: "05 测试用例审核"
  status: NEED_HUMAN
  return_to:
  next_action: confirm-stage --stage test_review
  affected_work_items: []
  evidence: []
  user_confirmation_required: true
  blocked_reason:
```

## Evidence

| 类型 | 命令/文件 | 结果 | 说明 |
|---|---|---|---|

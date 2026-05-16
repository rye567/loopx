# 规格审核技能

## 目的

作为只读质量门审查 `spec.md`，确认需求是否完整、清晰、可测试，且足以进入方案设计。

## 输入

- `spec.md`。
- `interview.md`。
- 执行等级和风险标签。
- 项目 harness、接口契约和相关模板。

## 步骤

1. 检查摘要、期望行为、验收标准、范围、边界情况和测试策略是否存在。
2. 查找模糊词、未确认假设和互相矛盾的规则。
3. 检查前端、后端、数据和外部 API 契约是否足够明确。
4. 判断是否存在阻塞性开放问题。
5. 输出 `spec_gate` 和 `stage_result`，不得直接修改实现代码。

## 输出

- `spec_gate.result`：`PASS`、`CHANGES_REQUIRED`、`BLOCKED` 或 `NEED_HUMAN`。
- 必填字段逐项结论。
- 需要回到 `spec_draft` 的修正清单。
- 带证据和下一步动作的 `stage_result`。

## 通过标准

- 规格必填字段全部满足。
- 验收标准能映射到测试。
- 关键业务规则无歧义。
- 执行等级决策有风险理由。

## 失败处理

规格可修复时返回 `CHANGES_REQUIRED` 且 `return_to: spec_draft`。业务决策缺失时返回 `NEED_HUMAN`。风险超出当前等级时返回 `CHANGES_REQUIRED` 并要求重新执行 `mode_selection`。

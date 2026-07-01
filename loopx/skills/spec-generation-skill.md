# 规格生成技能

## 目的

把 `interview.md` 中的事实、开放问题和风险信号转成可测试的 `spec.md`。

## 输入

- 用户需求、访谈记录、风险标签、执行等级建议、项目约束和测试入口。
- 已确认的 `requirement_interview PASS` 状态；若仍为 `NEED_HUMAN`，不得生成规格。

## 步骤

1. 先检查 `requirement_interview` 是否已经用户确认并转为 `PASS`；否则返回阻塞。
2. 提取已确认事实，禁止把假设写成事实。
3. 写明摘要、当前/期望行为、范围内/外。
4. 将业务规则转成可观察验收标准。
5. 写明前后端、持久化、外部 API、测试、发布和回滚影响。
6. 输出 `spec.md` 和 `stage_result`。

## 输出

- `docs/loopx/runs/<run_id>/artifacts/spec.md`、规格检查初始结论和阶段结果。

## 通过标准

- 验收标准可测试；范围明确；边界和错误处理已列出；测试策略能证明核心行为。

## 失败处理

缺少验收标准、范围、测试策略或关键规则时返回 `CHANGES_REQUIRED`；采访未确认、需要业务决策或仍有阻塞问题时返回 `BLOCKED` 或 `NEED_HUMAN`。

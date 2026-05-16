# 需求访谈技能

## 目的

把模糊请求转成能通过 `requirement-standard.md` 的需求产物。

## 输入

- 用户请求。
- 已有 issue、README、项目 harness 或上下文。
- 已知约束和非目标。

## 步骤

1. 识别用户角色、业务流程、当前问题和期望结果。
2. 区分范围和非范围。
3. 把期望行为转成可测试的验收标准。
4. 用 `ambiguous_requirement`、`api_contract`、`auth`、`tenant_scope`、`db_schema`、`external_side_effect` 等风险标签识别不确定性。
5. 根据执行等级选择采访深度：`LIGHT` 至少确认最终行为、验收标准和范围外；`STANDARD` 还要确认当前行为、影响用户、边界情况和测试证明；`FULL` 还要确认权限/套餐/数据/API/发布回滚/监控等高风险规则。
6. 把问题分为 blocking 和 non-blocking，只有答案会改变范围、风险或验收标准时才提出开放问题。
7. 输出 `.loopx/runs/<run_id>/artifacts/interview.md`，不得直接进入实现。

## 输出

- 需求产物。
- `interview.md`。
- 风险标签。
- 建议执行深度：`LIGHT`、`STANDARD` 或 `FULL`。
- 带证据和下一步动作的 `stage_result`。

## 通过标准

- 验收标准可观察。
- 范围和非范围都明确。
- 开放问题为空，或被明确标记为阻塞。
- 风险标签足以用于执行深度选择。

## 失败处理

产物可通过追问或重写修复时返回 `CHANGES_REQUIRED`。需要人工决策时返回 `BLOCKED`。

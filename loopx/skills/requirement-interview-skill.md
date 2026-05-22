# 需求访谈技能

## 目的

把模糊请求转成满足 `requirement-standard.md` 的需求产物。

## 输入

- 用户请求、已有 issue、README、项目 harness、上下文、约束和非目标。

## 步骤

1. 识别角色、业务流程、当前问题和期望结果。
2. 区分范围/非范围，并把期望行为转成验收标准。
3. 标记 `api_contract`、`auth`、`tenant_scope`、`db_schema` 等风险。
4. 按 `LIGHT|STANDARD|FULL` 选择采访深度。
5. 只提出会改变范围、风险或验收标准的开放问题，并把问题直接展示给用户回答。
6. 将用户回答写入 `interview.md`；不得把未回答、假设或模板占位当成已确认事实。
7. 输出 `interview.md` 和 `stage_result`，不得直接实现。
8. 采访满足放行条件时记录 `PASS` 只会落为 `NEED_HUMAN`；必须等待用户 `confirm-stage --stage requirement_interview` 后才能进入规格生成。

## 输出

- 需求产物、已填写用户回答的 `interview.md`、风险标签、建议执行深度和阶段结果；可放行时阶段结果为等待用户确认的 `NEED_HUMAN`。

## 通过标准

- 验收标准可观察；范围/非范围明确；开放问题为空或被标记为阻塞；风险标签足以分级。

## 失败处理

可修复时返回 `CHANGES_REQUIRED`；需要人工决策时返回 `BLOCKED`；未收到用户回答和确认前不得生成 `spec.md`。

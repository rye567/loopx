# 01 需求采访

需求采访不是生成模板文件；必须先把阻塞规格生成的问题展示给用户，并把用户回答写入本文件。

## 上下文

- 运行 ID：
- 执行等级：
- 原始需求：
- 当前阶段：requirement_interview

## 已确认事实

- 确认事实：
- 假设：
- 证据来源：

## 采访问题

| 优先级 | 问题 | 为什么需要 | 阻塞阶段 |
|---|---|---|---|
| P0 |  |  | spec_draft |

## 回答记录

- 问题：
  回答：待用户回答
  状态：未回答 | 已确认 | 假设

## 开放问题

- 阻塞问题：
- 非阻塞问题：

## 风险信号

- 风险标签：
- 推荐执行等级：
- 推荐原因：

## 采访检查

仍含“待用户回答”“未回答”或“待确认”时，不得记录 `PASS`。

```yaml
stage_result:
  stage: requirement_interview
  status: NEED_HUMAN
  return_to: ""
  next_action: confirm-stage --stage requirement_interview
  affected_work_items: []
  evidence: []
  user_confirmation_required: true
  blocked_reason: ""
```

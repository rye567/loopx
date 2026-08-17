# 阶段追踪技能

## 目的

把 `state.json`、`worklist.yml` 和阶段结果统一展示为 LoopX 追踪。

## 输入

- `docs/loopx/runs/<run_id>/state.json`、`worklist.yml`、`stage-results/*.json`、当前阶段和阻塞项。

## 步骤

1. 读取 run、mode、spec 状态和 current stage。
2. 按 00-16 阶段展示完成、当前、待办状态。
3. 汇总阻塞问题、已接受风险和下一步动作。
4. 在 `stage_result.tracking_snapshot` 中保存快照。

## 输出

- 追踪文本、`tracking_snapshot`、当前阻塞项和下一步动作。

## 通过标准

- 阶段顺序完整；当前阶段和 state 一致；PASS 阶段有 evidence；阻塞项不隐藏。

## 失败处理

状态文件缺失或不一致返回 `BLOCKED`；worklist 或 tracking snapshot 缺失返回 `CHANGES_REQUIRED`。
